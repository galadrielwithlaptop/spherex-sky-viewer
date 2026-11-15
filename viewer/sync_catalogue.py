"""Resumable all-sky *metadata-only* ingestion. No science/header requests.

Split overflowing SIA time partitions until each response is complete. An
interrupted or failed partition stays pending; never claim an incomplete index
is all-sky-complete. Four current spectral-image collections are included.
"""
import argparse,hashlib,json,time,uuid
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

def run(max_requests=0):
    initialize_index()
    if STATE.exists():state=json.loads(STATE.read_text())
    else:
        end=datetime.now(timezone.utc).timestamp()/86400+40587
        state={'status':'pending','scope':'All-sky spectral-image metadata, DR1/QR3 wide and deep; time partitioned','start_mjd':60676,'end_mjd':end,'pending':[[c,60676,end] for c in AVAILABLE_COLLECTIONS],'completed_partitions':0,'returned_records':0,'requests':0,'pixel_downloads':0,'header_downloads':0}
    state.setdefault('generation',uuid.uuid4().hex);register_generation(state)
    attempted=0;state['status']='running';state.pop('error',None);save(state)
    while state['pending'] and (not max_requests or attempted<max_requests):
        collection,start,end=state['pending'][-1]
        if DB.stat().st_size+sum(p.stat().st_size for p in DB.parent.glob(DB.name+'-*'))>4*1024**3:
            state.update(status='storage_limit',error='4 GiB metadata database budget reached; pending partitions retained');break
        url='https://irsa.ipac.caltech.edu/SIA?'+urlencode({'COLLECTION':collection,'TIME':f'{start:.9f} {end:.9f}','MAXREC':2000})
        attempted+=1;state['requests']+=1
        try:result=parse_votable(text(url))
        except Exception as e:state.update(status='upstream_failed',error=str(e),failed_query=url);save(state);return state
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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--max-requests',type=int,default=0,help='0 means run until complete, archive failure or storage limit');args=parser.parse_args()
    print(json.dumps(run(args.max_requests),indent=2))
