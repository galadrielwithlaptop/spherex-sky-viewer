"""Resumable all-sky *metadata-only* ingestion. No science/header requests.

Split overflowing SIA time partitions until each response is complete. An
interrupted or failed partition stays pending; never claim an incomplete index
is all-sky-complete. Four current spectral-image collections are included.
"""
import argparse,hashlib,json,time,uuid,os,shutil
from datetime import datetime,timezone
from urllib.parse import urlencode
from archive import AVAILABLE_COLLECTIONS,parse_votable
from store import CACHE,DB,connection,index_row,initialize_index
from network import text

STATE=CACHE/'allsky-sync.json'
FIELDS=('s_ra','s_dec','s_region','t_min','t_max','obs_id','obs_collection','energy_bandpassname','access_url','access_estsize','access_format','t_exptime','em_min','em_max','s_resolution','s_pixel_scale','s_xel1','s_xel2','obs_release_date','obs_publisher_did')

def ingest(rows,generation=None):
    with connection() as c:
        for original in rows:
            row={k:original.get(k,'') for k in FIELDS};key=hashlib.sha256(row['access_url'].encode()).hexdigest()[:24];row['id']=key
            old=c.execute('SELECT rowid,payload FROM exposures WHERE id=?',(key,)).fetchone()
            # Preserve richer existing records rather than replace them with compact ones.
            if old:row={**json.loads(old['payload']),**row}
            payload=json.dumps(row)
            c.execute('INSERT INTO exposures VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET ra=excluded.ra,dec=excluded.dec,mjd=excluded.mjd,detector=excluded.detector,payload=excluded.payload',(key,float(row['s_ra']),float(row['s_dec']),float(row['t_min']),row['energy_bandpassname'],payload))
            rowid=c.execute('SELECT rowid FROM exposures WHERE id=?',(key,)).fetchone()[0]
            if old is None or old['payload']!=payload:index_row(c,rowid,row)
            if generation:c.execute('INSERT OR IGNORE INTO global_members VALUES (?,?)',(generation,key))
        c.execute("UPDATE index_state SET value=value+1 WHERE name='revision'")

def register_generation(state):
    with connection() as c:c.execute('INSERT OR IGNORE INTO global_generations VALUES (?,?,?,?,?,?)',(state['generation'],'running',None,state['start_mjd'],state['end_mjd'],json.dumps(list(AVAILABLE_COLLECTIONS))))

def finish_generation(state):
    with connection() as c:
        c.execute("UPDATE global_generations SET status='complete',completed=? WHERE generation=?",(time.time(),state['generation']))
        c.execute("UPDATE index_state SET value=value+1 WHERE name='revision'")

def save(state):
    state['updated_utc']=datetime.now(timezone.utc).isoformat();temp=STATE.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2),encoding='utf-8');temp.replace(STATE)

def run(max_requests=0,split_failures=False):
    initialize_index()
    if STATE.exists():state=json.loads(STATE.read_text())
    else:
        end=datetime.now(timezone.utc).timestamp()/86400+40587
        state={'status':'pending','scope':'All-sky spectral-image metadata, DR1/QR3 wide and deep; time partitioned','start_mjd':60676,'end_mjd':end,'pending':[[c,60676,end] for c in AVAILABLE_COLLECTIONS],'completed_partitions':0,'returned_records':0,'requests':0,'pixel_downloads':0,'header_downloads':0}
    state.setdefault('generation',uuid.uuid4().hex);register_generation(state)
    attempted=0;state['status']='running';state.pop('error',None);save(state)
    while state['pending'] and (not max_requests or attempted<max_requests):
        collection,start,end=state['pending'][-1]
        budget=float(os.environ.get('SPHEREX_METADATA_MAX_GIB','4'))*1024**3
        if DB.stat().st_size+sum(p.stat().st_size for p in DB.parent.glob(DB.name+'-*'))>budget or shutil.disk_usage(DB.parent).free<4*1024**3:
            state.update(status='storage_limit',error='Metadata budget or 4 GiB free-disk reserve reached; pending partitions retained');break
        url='https://irsa.ipac.caltech.edu/SIA?'+urlencode({'COLLECTION':collection,'TIME':f'{start:.9f} {end:.9f}','MAXREC':2000})
        attempted+=1;state['requests']+=1;save(state)
        try:result=parse_votable(text(url))
        except Exception as e:
            state.update(status='upstream_failed',error=str(e),failed_query=url)
            if split_failures and end-start>1/24:
                # Broad all-sky time queries may time out before emitting OVERFLOW.
                # Smaller partitions remain pending; no response is called complete.
                mid=(start+end)/2;state['pending'].pop();state['pending'].extend([[collection,mid,end],[collection,start,mid]])
                state['status']='retrying_smaller_partition'
            elif split_failures:
                # Let other collections advance while retaining this failed interval.
                state['pending'].insert(0,state['pending'].pop())
            save(state);return state
        if result['truncated']:
            if end-start<1/86400:state.update(status='partition_overflow',error='Overflow remains at a one-second partition; no completeness claim');break
            mid=(start+end)/2;state['pending'].pop();state['pending'].extend([[collection,mid,end],[collection,start,mid]])
        else:
            ingest(result['rows'],state['generation']);state['pending'].pop();state['completed_partitions']+=1;state['returned_records']+=len(result['rows'])
        save(state);time.sleep(.2)
    if not state['pending']:
        state['status']='complete_for_time_interval';finish_generation(state)
    elif state['status']=='running':state['status']='paused_at_request_limit'
    save(state);return state

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-requests',type=int,default=0,help='0 means run until complete, archive failure or storage limit')
    parser.add_argument('--watch',action='store_true',help='Resume pending metadata partitions after transient failures; exits on completion/storage limit')
    parser.add_argument('--retry-seconds',type=int,default=300)
    args=parser.parse_args()
    if args.max_requests<0 or args.retry_seconds<10:parser.error('Use max-requests >= 0 and retry-seconds >= 10')
    # Separate from the viewer process; only one metadata importer owns this journal.
    lock=open(CACHE/'allsky-sync.lock','a+b')
    if os.name=='nt':
        import msvcrt
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    while True:
        result=run(args.max_requests,split_failures=args.watch)
        print(json.dumps({k:v for k,v in result.items() if k!='pending'},indent=2),flush=True)
        if not args.watch or result['status'] in ('complete_for_time_interval','storage_limit','partition_overflow'):break
        time.sleep(10 if result['status']=='retrying_smaller_partition' else args.retry_seconds)
