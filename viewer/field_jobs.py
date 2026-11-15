"""Durable field-scoped downloads; never download the all-sky image archive."""
import hashlib,json,threading,time
from pathlib import Path
from archive import query_url,COLLECTIONS
from geometry import footprint,intersects,vector,RAD
from store import CACHE,exposure

_guard=threading.Lock();_io=threading.RLock();_active={}

def directory():
    path=CACHE/'field-jobs';path.mkdir(exist_ok=True);return path

def valid_id(key):return isinstance(key,str) and len(key)==24 and all(c in '0123456789abcdef' for c in key)

def save(state):
    with _io:
        state['updated_unix']=time.time();path=directory()/(state['id']+'.json');tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state),encoding='utf-8')
        for attempt in range(20):
            try:tmp.replace(path);break
            except PermissionError:
                if attempt==19:raise
                time.sleep(.01)

def status(key):
    if not valid_id(key):raise ValueError('Invalid field job ID')
    path=directory()/(key+'.json')
    if not path.exists():raise ValueError('Unknown field job')
    with _io:state=json.loads(path.read_text())
    if state['state'] in ('running','queued') and not _active.get(key,False):state['state']='interrupted'
    state['counts']={s:sum(r['state']==s for r in state['records']) for s in ['pending','loading','prepared','failed']}
    return state

def stop(key):
    state=status(key);(directory()/(key+'.stop')).touch();return {'id':key,'state':'stop_requested','message':'The current cutout finishes; no subsequent observation will be requested.'}

def start(payload,executor,products,registry,run_job,run_assembly):
    if not isinstance(payload,dict) or set(payload)-{'ra','dec','fov_arcmin','observation_ids'}:raise ValueError('Use coordinates, fov_arcmin and observation_ids only')
    params={k:float(payload[k if k!='fov' else 'fov_arcmin']) for k in ['ra','dec','fov']};query_url(**params,collection=COLLECTIONS[0])
    ids=payload['observation_ids']
    if not isinstance(ids,list) or not 1<=len(ids)<=500 or any(not valid_id(k) for k in ids):raise ValueError('Choose 1–500 indexed observation IDs for this field')
    ids=list(dict.fromkeys(ids));rows=sorted([exposure(k) for k in ids],key=lambda r:(float(r['t_min']),r['id']))
    if any(not intersects(footprint(r.get('s_region','')),vector(params['ra'],params['dec']),params['fov']/120*RAD) for r in rows):raise ValueError('A selected observation does not overlap the requested field')
    key=hashlib.sha256(json.dumps({'params':params,'ids':sorted(ids),'version':1},sort_keys=True).encode()).hexdigest()[:24]
    with _guard:
        if _active.get(key):return status(key)
        if any(_active.values()):raise ValueError('Another field download is active. Stop it or wait before starting another field.')
        path=directory()/(key+'.json')
        if path.exists():state=json.loads(path.read_text())
        else:state={'id':key,'parameters':params,'state':'queued','records':[{'id':r['id'],'observation':r['obs_id'],'detector':r['energy_bandpassname'],'state':'pending'} for r in rows],'sequence_id':None,'requested':len(rows)}
        (directory()/(key+'.stop')).unlink(missing_ok=True);state['state']='running';save(state);_active[key]=True
        thread=threading.Thread(target=run,args=(state,rows,executor,products,registry,run_job,run_assembly),daemon=True);thread.start()
    return status(key)

def run(state,rows,executor,products,registry,run_job,run_assembly):
    key=state['id'];params=state['parameters'];results={r['id']:r for r in state['records']};sources=[];assembled=0;consecutive_failures=0
    # Prefer already prepared cutouts for a fast first useful display. Final
    # assemblies sort all source observations chronologically.
    warm=set()
    for path in products.glob('*/manifest.json'):
        try:
            m=json.loads(path.read_text())
            if m['parameters']==params:warm.update(f['id'] for f in m['frames'])
        except (ValueError,KeyError,OSError):pass
    rows=sorted(rows,key=lambda r:(r['id'] not in warm,float(r['t_min']),r['id']))
    def assemble():
        nonlocal assembled
        if not sources:return
        if len(sources)==1:state['sequence_id']=sources[0];assembled=1;save(state);return
        target=hashlib.sha256(json.dumps({'assembly':sources,'version':1}).encode()).hexdigest()[:24];dest=products/target
        if not (dest/'manifest.json').exists():
            work={'state':'queued','errors':[]};registry[target]=work;executor.submit(run_assembly,work,sources,params,dest).result()
            if work['state']!='complete':raise RuntimeError(work.get('error','Cached assembly failed'))
        state['sequence_id']=target;assembled=len(sources);save(state)
    try:
        for row in rows:
            if (directory()/(key+'.stop')).exists():state['state']='stopped';break
            item=results[row['id']]
            digest=hashlib.sha256(json.dumps({'params':params,'ids':[row['id']],'version':7,'mosaic':False,'match':False},sort_keys=True).encode()).hexdigest()[:24];dest=products/digest
            item.update(state='loading',job_id=digest);state['current_observation']=row['obs_id'];save(state)
            if not (dest/'manifest.json').exists():
                if sum(p.stat().st_size for p in products.rglob('*') if p.is_file())>512*1024**2:raise RuntimeError('Field product cache capacity reached; existing results remain available')
                dest.mkdir(exist_ok=True);(dest/'request.json').write_text(json.dumps({'rows':[row],'params':params,'match':False,'mosaic':False}))
                work={'state':'queued','errors':[]};registry[digest]=work;executor.submit(run_job,work,[row],params,dest,False).result()
            else:work={'state':'complete'}
            if work['state']=='complete':
                item.update(state='prepared');item.pop('error',None);sources.append(digest);consecutive_failures=0
                n=len(sources)
                if n<=3 or n&(n-1)==0:assemble()
            else:
                item.update(state='failed',error=work.get('error','Image preparation failed'),details=work.get('errors',[]));consecutive_failures+=1
            save(state)
            if consecutive_failures>=3:state['state']='paused_after_failures';state['error']='Three consecutive image failures; explicit resume retries failed/pending records.';break
        else:state['state']='complete_with_failures' if any(r['state']=='failed' for r in state['records']) else 'complete'
        if len(sources)>assembled:assemble()
    except Exception as e:state.update(state='failed',error=str(e))
    finally:
        try:save(state)
        finally:_active[key]=False
