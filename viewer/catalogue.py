"""Metadata-first discovery and a stable public observation-query contract."""
import base64, hashlib, json, math, threading, time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from archive import COLLECTIONS,AVAILABLE_COLLECTIONS,query_url,parse_votable
from store import coverage,spatial_rows,put_query,initialize_index
from network import text

_locks={};_guard=threading.Lock();_failures={}
def region_discovery(ra,dec,fov,collection,mode='auto',refresh=False):
    radius=fov/120
    state=coverage(ra,dec,radius,collection)
    if mode=='cache_only' or (state['complete'] and state['fresh'] and not refresh):return dict(state,collection=collection,source='local_index')
    # A modest expanded *metadata* cone enables nearby-query reuse.
    expanded=max(radius,.125)
    url=query_url(ra,dec,expanded*120,collection)
    with _guard:lock=_locks.setdefault(url,threading.Lock())
    with lock:
        state=coverage(ra,dec,radius,collection)
        if state['complete'] and state['fresh'] and not refresh:return dict(state,collection=collection,source='local_index')
        failed=_failures.get(url)
        if failed and not refresh and time.monotonic()-failed[0]<60:
            return dict(state,collection=collection,source='local_index',error=failed[1],retry_after_seconds=max(1,math.ceil(60-(time.monotonic()-failed[0]))))
        try:
            result=parse_votable(text(url));put_query(url,result)
            if result['truncated'] and expanded>radius:
                url=query_url(ra,dec,fov,collection);result=parse_votable(text(url));put_query(url,result)
            _failures.pop(url,None)
            return dict(coverage(ra,dec,radius,collection),collection=collection,source='archive_metadata',truncated=result['truncated'])
        except Exception as e:
            if len(_failures)>512:_failures.clear()
            _failures[query_url(ra,dec,expanded*120,collection)]=(time.monotonic(),str(e))
            return dict(state,collection=collection,source='local_index',error=str(e),retry_after_seconds=60)

def discover(ra,dec,fov,collections=COLLECTIONS,mode='auto',refresh=False):
    if mode not in ('auto','cache_only'):raise ValueError('mode must be auto or cache_only')
    if mode=='cache_only' and refresh:raise ValueError('refresh cannot be combined with cache_only')
    for c in collections:query_url(ra,dec,fov,c)
    local=[dict(coverage(ra,dec,fov/120,c),collection=c,source='local_index') for c in collections]
    if mode=='cache_only' or (not refresh and all(s['complete'] and s['fresh'] for s in local)):return local
    with ThreadPoolExecutor(max_workers=2) as pool:
        states=list(pool.map(lambda c:region_discovery(ra,dec,fov,c,mode,refresh),collections))
    return states

def utc(mjd):return (datetime(1858,11,17,tzinfo=timezone.utc)+timedelta(days=float(mjd))).isoformat(timespec='milliseconds').replace('+00:00','Z')

def observation(row):
    return {'id':row['id'],'observation_id':row['obs_id'],'collection':row['obs_collection'],'detector':int(row['energy_bandpassname'][-1]),'time_start_mjd':float(row['t_min']),'time_end_mjd':float(row['t_max']),'time_start_utc':utc(row['t_min']),'time_end_utc':utc(row['t_max']),'exposure_seconds':float(row['t_exptime']) if row.get('t_exptime') else None,'image_center_icrs_deg':[float(row['s_ra']),float(row['s_dec'])],'footprint':row.get('s_region'),'footprint_match':row.get('footprint_match','archive_record'),'index_membership':row.get('index_membership','not_queried'),'quality_status':'Pixel quality/contamination flags are not loaded by a metadata query','wavelength_bounds_um':[float(row['em_min'])*1e6,float(row['em_max'])*1e6],'wavelength_semantics':'Detector-wide bounds, not the wavelength at the requested coordinate','source_url':row['access_url'],'source_format':row.get('access_format'),'estimated_source_size_kbyte':int(row['access_estsize']) if row.get('access_estsize') else None,'links':{'self':f"/api/v1/observations/{row['id']}"}}

class APIError(Exception):
    def __init__(self,message,status=400,code='invalid_request'):
        self.status=status;self.code=code;super().__init__(message)

def one(q,key,default=None):
    values=q.get(key)
    if values is None:return default
    if len(values)!=1:raise APIError(f'{key} must be supplied once')
    return values[0]

def boolean(value,name):
    if str(value).lower() in ('1','true'):return True
    if str(value).lower() in ('0','false'):return False
    raise APIError(name+' must be true or false')

def options(q):
    try:
        allowed={'ra','dec','fov','fov_arcmin','collections','detector','start_mjd','end_mjd','sort','limit','mode','refresh','cursor'}
        if set(q)-allowed:raise ValueError('Unknown parameter: '+','.join(sorted(set(q)-allowed)))
        ra,dec,fov=map(float,(one(q,'ra'),one(q,'dec'),one(q,'fov_arcmin',one(q,'fov','5'))))
        query_url(ra,dec,fov,COLLECTIONS[0])
        collections=tuple(one(q,'collections',','.join(COLLECTIONS)).split(','))
        if not collections or len(set(collections))!=len(collections) or any(c not in AVAILABLE_COLLECTIONS for c in collections):raise ValueError('Unsupported or duplicate collection')
        detector=one(q,'detector');detector=int(detector) if detector is not None else None
        if detector is not None and detector not in range(1,7):raise ValueError('detector must be 1–6')
        start=one(q,'start_mjd');end=one(q,'end_mjd')
        start=float(start) if start is not None else None;end=float(end) if end is not None else None
        if any(x is not None and not math.isfinite(x) for x in (start,end)):raise ValueError('Dates must be finite MJD values')
        if start is not None and end is not None and start>end:raise ValueError('start_mjd must not exceed end_mjd')
        sort=one(q,'sort','asc');limit=int(one(q,'limit','100'));mode=one(q,'mode','auto')
        if sort not in ('asc','desc') or not 1<=limit<=500:raise ValueError('Use sort asc/desc and limit 1–500')
        if mode not in ('auto','cache_only'):raise ValueError('mode must be auto or cache_only')
        refresh=boolean(one(q,'refresh','false'),'refresh')
        if mode=='cache_only' and refresh:raise ValueError('cache_only cannot refresh the archive')
        return dict(ra=ra,dec=dec,fov=fov,collections=collections,detector=detector,start=start,end=end,sort=sort,limit=limit,mode=mode,refresh=refresh,cursor=one(q,'cursor'))
    except (TypeError,ValueError) as e:raise APIError(str(e))

def query(q):
    begin=time.perf_counter();p=options(q)
    states=discover(p['ra'],p['dec'],p['fov'],p['collections'],p['mode'],p['refresh'])
    found=spatial_rows(p['ra'],p['dec'],p['fov']/120,p['collections'],p['detector'],p['start'],p['end'])
    rows=found['rows'];rows.sort(key=lambda r:(float(r['t_min']),r['id']),reverse=p['sort']=='desc')
    total=len(rows)
    fingerprint=hashlib.sha256(json.dumps({k:v for k,v in p.items() if k not in ('cursor','refresh','mode','limit')},sort_keys=True).encode()).hexdigest()[:20]
    if p['cursor']:
        try:
            if len(p['cursor'])>1024:raise ValueError()
            cursor=json.loads(base64.urlsafe_b64decode(p['cursor']+'='*(-len(p['cursor'])%4)))
            if cursor['query']!=fingerprint:raise APIError('Cursor does not match these query filters')
            if cursor['revision']!=found['revision']:raise APIError('Catalogue changed; restart pagination',409,'catalogue_changed')
            boundary=(float(cursor['last'][0]),str(cursor['last'][1]))
            rows=[r for r in rows if ((float(r['t_min']),r['id'])>boundary if p['sort']=='asc' else (float(r['t_min']),r['id'])<boundary)]
        except (ValueError,TypeError,KeyError,IndexError,UnicodeDecodeError,json.JSONDecodeError):raise APIError('Invalid pagination cursor')
    page=rows[:p['limit']];next_cursor=None
    if len(rows)>len(page):
        last=page[-1];next_cursor=base64.urlsafe_b64encode(json.dumps({'query':fingerprint,'revision':found['revision'],'last':[float(last['t_min']),last['id']]},separators=(',',':')).encode()).decode().rstrip('=')
    complete=all(s['complete'] for s in states)
    fresh=all(s['fresh'] for s in states)
    payload={'api_version':'1.0','query':{k:v for k,v in p.items() if k not in ('cursor','refresh')},'observations':[observation(r) for r in page],'pagination':{'returned':len(page),'total_indexed_matches':total,'next_cursor':next_cursor,'index_revision':found['revision']},'coverage':{'complete_for_requested_collections':complete,'fresh':fresh,'collections':states,'unverified_footprints':found['unverified_footprints'],'interpretation':'Archive footprint overlaps, not source detections or independent same-wavelength epochs'},'provenance':{'pixel_downloads':0,'index_candidate_count':found['candidates'],'selection':'3D spherical-cap R-tree candidates plus spherical S_REGION intersection','fov_semantics':'Circular diameter in arcminutes','time_filter':'Exposure intervals overlap inclusive MJD bounds','wavelength_caveat':'Target-position responses require separately requested wavelength-header inspection'},'links':{'documentation':'/api/docs','openapi':'/api/openapi.json'}}
    if not complete and not rows:payload['notice']='Coverage is not established for this field; an empty local result does not imply no public observations.'
    return payload,{'elapsed_ms':(time.perf_counter()-begin)*1000,'candidate_count':found['candidates'],'selected_count':total,'cache':'local_index' if all(s['source']=='local_index' for s in states) else 'archive_metadata'}
