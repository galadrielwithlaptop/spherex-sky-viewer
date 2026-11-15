"""Local SPHEREx catalogue, bounded image preparation and viewer."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

from urllib.parse import urlsplit, parse_qs

from concurrent.futures import ThreadPoolExecutor

import hashlib, json, time, threading, traceback, os, uuid, gzip

from archive import COLLECTIONS, query_url, parse_votable

from network import text

from store import CACHE, get_query, put_query, exposure, stats,initialize_index,spatial_rows

from catalogue import discover,APIError,one,boolean

ROOT=Path(__file__).parent.resolve()

PRODUCTS=CACHE/'products'; PRODUCTS.mkdir(exist_ok=True)

JOBS={}; EXECUTOR=ThreadPoolExecutor(max_workers=1); SEARCH_LOCK=threading.Lock()



def accepts_gzip(header):

    for part in header.split(','):

        pieces=[x.strip() for x in part.split(';')]

        if pieces[0]!='gzip':continue

        try:

            q=next((float(x.split('=',1)[1]) for x in pieces[1:] if x.startswith('q=')),1)

            if 0<q<=1:return True

        except ValueError:continue

    return False



def search_collection(url,collection,refresh=False):

    with SEARCH_LOCK:

        cached=get_query(url)

        if cached and not refresh and time.time()-cached['fetched']<86400:

            return dict(cached,collection=collection,query_url=url,cached=True,stale=False)

        try:

            result=parse_votable(text(url)); put_query(url,result)

            return dict(result,collection=collection,query_url=url,cached=False,stale=False,fetched=time.time())

        except Exception as e:

            if cached: return dict(cached,collection=collection,query_url=url,cached=True,stale=True,warning=str(e))

            return {'collection':collection,'query_url':url,'error':str(e)}



def run_job(job,rows,params,dest,match=False,mosaic=False):

    try:

        job['state']='running'

        from imaging import build

        build(job,rows,params,dest,match=match,mosaic=mosaic)

    except Exception as e:

        job.update(state='failed',error=str(e));traceback.print_exc()



def run_assembly(job,ids,params,dest):
    try:
        import numpy as np
        from imaging import build
        job['state']='running';sources={}
        for key in ids:
            directory=PRODUCTS/key;m=json.loads((directory/'manifest.json').read_text())
            for i,frame in enumerate(m['frames']):sources.setdefault(frame['id'],(directory,i,frame))
        rows=sorted([{'id':k,'t_min':v[2]['mjd']} for k,v in sources.items()],key=lambda r:r['t_min'])
        def load(row,**kw):
            directory,i,metadata=sources[row['id']]
            with np.load(directory/'aligned.npz') as data:array=data[str(i)].copy()
            return array,dict(metadata)
        build(job,rows,params,dest,loader=load)
    except Exception as e:job.update(state='failed',error=str(e));traceback.print_exc()

def ready_sequence(params,detector,match=True,start=None,end=None):

    """Reuse only complete products for the requested field and filters."""

    from datetime import datetime, timezone

    def boundary(value):

        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()/86400+40587 if value else None

    low,high=boundary(start),boundary(end)

    candidates=[]

    for path in PRODUCTS.glob('*/manifest.json'):

        try:

            m=json.loads(path.read_text());p=m['parameters'];frames=m['frames']

            if any(abs(float(p[k])-float(params[k]))>1e-9 for k in ('ra','dec','fov')):continue

            if not frames or any(f['detector']!=detector for f in frames):continue

            if low is not None and any(f['mjd']<low for f in frames):continue

            if high is not None and any(f['mjd']>=high+1 for f in frames):continue

            if match and not any(len(g['indices'])>=2 for g in m['groups']):continue

            if any(not (path.parent/f"{i}.png").is_file() for i in range(len(frames))):continue

            candidates.append((max(f['mjd'] for f in frames)-min(f['mjd'] for f in frames),len(frames),path.stat().st_mtime,path.parent.name))

        except (ValueError,KeyError,OSError):continue

    return max(candidates)[-1] if candidates else None



class Handler(SimpleHTTPRequestHandler):

    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'web'),**kwargs)

    def begin_request(self):

        self.started=time.perf_counter();self.request_id=uuid.uuid4().hex[:16]

        self.versioned=urlsplit(self.path).path.startswith('/api/v1/')

        self.response_bytes=0;self.cache_source=None

    def host_allowed(self):

        host=urlsplit('//'+self.headers.get('Host','')).hostname

        allowed=os.environ.get('SPHEREX_ALLOWED_HOSTS','127.0.0.1,localhost').split(',')

        return host in [x.strip() for x in allowed]

    def origin_allowed(self):

        origin=self.headers.get('Origin')

        allowed=[f'http://{self.headers.get("Host","")}',f'https://{self.headers.get("Host","")}']+os.environ.get('SPHEREX_ALLOWED_ORIGINS','').split(',')

        return not origin or origin in allowed

    def json(self,value,status=200):

        if getattr(self,'versioned',False):

            if status>=400 and isinstance(value.get('error'),str):value={'error':{'code':'invalid_request' if status==400 else 'request_failed','message':value['error']}}

            value=dict(value,request_id=self.request_id)

        raw=json.dumps(value,allow_nan=False).encode()

        compressed=len(raw)>4096 and accepts_gzip(self.headers.get('Accept-Encoding',''))

        if compressed:raw=gzip.compress(raw,compresslevel=5,mtime=0)

        self.response_bytes=len(raw)

        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)))

        self.send_header('Vary','Accept-Encoding')

        if compressed:self.send_header('Content-Encoding','gzip')

        self.end_headers();self.wfile.write(raw)

    def do_GET(self):

        self.begin_request()

        if not self.host_allowed():return self.json({'error':'Host is not enabled for this deployment'},403)

        u=urlsplit(self.path);q=parse_qs(u.query)

        try:

            if u.path=='/api/openapi.json':

                from api_schema import schema

                return self.json(schema())

            if u.path=='/api/docs':

                self.path='/api.html';return super().do_GET()

            if u.path.startswith('/api/v1/sequences/'):

                key=u.path.rsplit('/',1)[-1]

                if len(key)!=24 or not all(x in '0123456789abcdef' for x in key):raise APIError('Invalid sequence ID')

                if key in JOBS:state=dict(JOBS[key])

                elif (PRODUCTS/key/'manifest.json').is_file():state={'state':'complete','manifest':json.loads((PRODUCTS/key/'manifest.json').read_text())}

                elif (PRODUCTS/key/'request.json').is_file():state={'state':'interrupted','message':'Resubmit the original sequence POST to resume; GET never starts image downloads'}

                else:raise APIError('Sequence not found',404,'not_found')

                return self.json(dict(state,api_version='1.0',job_id=key,links={'viewer':f'/?job={key}','manifest':f'/api/v1/products/{key}/manifest.json'}))

            if u.path.startswith('/api/v1/products/'):

                return self.serve_product(u.path.removeprefix('/api/v1/products/'))

            if u.path.startswith('/api/v1/cutouts/'):

                return self.serve_cutout(u.path.rsplit('/',1)[-1])

            if u.path.startswith('/api/v1/overlays/'):

                from overlays import catalogue

                mode=one(q,'mode','auto')

                if mode not in ('auto','cache_only'):raise APIError('mode must be auto or cache_only')

                return self.json(catalogue(q['ra'][0],q['dec'][0],one(q,'fov_arcmin','5'),u.path.rsplit('/',1)[-1],cache_only=mode=='cache_only'))

            if u.path.startswith('/api/v1/field-downloads/'):
                from field_jobs import status as field_status
                return self.json(field_status(u.path.rsplit('/',1)[-1]))
            if u.path=='/api/v1/field-audit':
                from field_audit import audit
                return self.json(audit(float(one(q,'ra')),float(one(q,'dec')),float(one(q,'fov_arcmin','5'))))
            if u.path=='/api/v1/catalogue-sync':
                path=CACHE/'allsky-sync.json'
                return self.json(json.loads(path.read_text()) if path.exists() else {'status':'not_started','complete':False})
            if u.path.startswith('/api/v1/'):

                from public_api import get

                payload,metrics=get(u.path,q);self.cache_source=metrics.get('cache')

                return self.json(payload)

            if u.path=='/api/health': return self.json({'ok':True,'catalogue':stats(),'version':2})

            if u.path=='/api/ready':

                params={k:float(q[k][0]) for k in ('ra','dec','fov')}

                query_url(**params,collection=COLLECTIONS[0])

                return self.json({'job':ready_sequence(params,q.get('detector',['SPHEREx-D4'])[0],q.get('match',['1'])[0]=='1',q.get('from',[None])[0],q.get('through',[None])[0])})

            if u.path in ('/app.js','/style.css','/'):

                self._dynamic_assets=True

            if u.path=='/api/overlay':

                from overlays import catalogue

                return self.json(catalogue(q['ra'][0],q['dec'][0],q['fov'][0],q['catalogue'][0]))

            if u.path=='/api/search':

                ra,dec,fov=map(float,(q['ra'][0],q['dec'][0],q['fov'][0]))

                states=discover(ra,dec,fov,refresh=q.get('refresh',['0'])[0]=='1')

                results=[]

                for state in states:

                    c=state['collection'];found=spatial_rows(ra,dec,fov/120,[c])

                    result=dict(state,rows=found['rows'],query_url=state.get('source_query',query_url(ra,dec,fov,c)),cached=state['source']=='local_index',stale=not state['fresh'],truncated=state.get('truncated',False))

                    results.append(result)

                self.cache_source='local_index' if all(s['source']=='local_index' for s in states) else 'archive_metadata'

                return self.json({'collections':results,'catalogue':stats()})

            if u.path.startswith('/api/jobs/'):

                key=u.path.rsplit('/',1)[-1]

                if len(key)!=24 or not key.isalnum():raise ValueError('Invalid job ID')

                if key in JOBS:return self.json(JOBS[key])

                manifest=PRODUCTS/key/'manifest.json'

                if manifest.is_file():return self.json({'state':'complete','manifest':json.loads(manifest.read_text())})

                request=PRODUCTS/key/'request.json'

                if request.is_file():

                    p=json.loads(request.read_text());JOBS[key]={'state':'queued','progress':'Resuming from cached cutouts','errors':[]}

                    EXECUTOR.submit(run_job,JOBS[key],p['rows'],p['params'],PRODUCTS/key,p.get('match',False),p.get('mosaic',False))

                    return self.json(JOBS[key])

                return self.json({'error':'Unknown job'},404)

            if u.path.startswith('/products/'):

                return self.serve_product(u.path.removeprefix('/products/'))

            if u.path.startswith('/cutouts/'):

                return self.serve_cutout(u.path.rsplit('/',1)[-1])

            if u.path=='/api/resolve':

                from urllib.parse import quote

                import xml.etree.ElementTree as ET

                name=q.get('name',[''])[0]

                if name not in ["Barnard's Star",'eps Ind B','RW Aur','R Dra']:raise ValueError('Select a supported target')

                saved=ROOT/'evidence'/'target-coverage.json'

                if saved.exists():

                    record=next((r for r in json.loads(saved.read_text()) if r['name']==name),None)

                    if record:return self.json({'ra':record['ra'],'dec':record['dec'],'name':name,'provenance':'Saved CDS Sesame/SIMBAD position, checked 14 Nov 2026; proper motion not propagated'})

                raw=text('https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?'+quote(name))

                root=ET.fromstring(raw);ra=root.findtext('.//jradeg');dec=root.findtext('.//jdedeg')

                if ra is None or dec is None:raise ValueError('Name resolver returned no coordinates')

                return self.json({'ra':float(ra),'dec':float(dec),'name':name,'provenance':'CDS Sesame/SIMBAD; catalogue position, proper motion not propagated'})

            if u.path.startswith('/api/'):return self.json({'error':'Unknown API'},404)

            return super().do_GET()

        except APIError as e:return self.json({'error':{'code':e.code,'message':str(e)}},e.status)

        except (ValueError,KeyError) as e:return self.json({'error':str(e)},400)

        except Exception as e:return self.json({'error':str(e)},502)

    def do_POST(self):

        self.begin_request()

        if not self.host_allowed():return self.json({'error':'Host is not enabled for this deployment'},403)

        if not self.origin_allowed():return self.json({'error':'Origin is not enabled for image preparation'},403)

        if self.path not in ('/api/prepare','/api/v1/sequences','/api/v1/mosaics','/api/v1/assemblies','/api/v1/field-downloads') and not (self.path.startswith('/api/v1/field-downloads/') and self.path.endswith('/stop')):return self.json({'error':'Unknown API'},404)

        try:

            length=int(self.headers.get('Content-Length','0'))

            if not 0<length<=16384:raise ValueError('Use a nonempty JSON body no larger than 16 KiB')

            if self.versioned and self.headers.get('Content-Type','').split(';')[0]!='application/json':raise APIError('Content-Type must be application/json',415,'unsupported_media_type')

            p=json.loads(self.rfile.read(length))

            if self.path=='/api/v1/field-downloads':
                from field_jobs import start
                return self.json(start(p,EXECUTOR,PRODUCTS,JOBS,run_job,run_assembly),202)
            if self.path.startswith('/api/v1/field-downloads/') and self.path.endswith('/stop'):
                from field_jobs import stop
                if p!={}:raise APIError('Stop request body must be an empty object')
                return self.json(stop(self.path.split('/')[-2]),202)
            if self.path=='/api/v1/assemblies':return self.assemble(p)
            mosaic=self.path=='/api/v1/mosaics'
            cached_only=False

            if self.versioned:

                if not isinstance(p,dict):raise APIError('Request body must be an object')

                if set(p)-{'ra','dec','fov_arcmin','observation_ids','match_wavelengths','cached_only'}:raise APIError('Unknown sequence parameter')

                for name in ('match_wavelengths','cached_only'):

                    if name in p and not isinstance(p[name],bool):raise APIError(name+' must be a JSON boolean')

                cached_only=p.get('cached_only',False)

                p={'ra':p['ra'],'dec':p['dec'],'fov':p.get('fov_arcmin',5),'ids':p['observation_ids'],'match':p.get('match_wavelengths',True)}

            params={k:float(p[k]) for k in ('ra','dec','fov')}

            query_url(**params,collection=COLLECTIONS[0]);ids=p['ids']

            if not isinstance(ids,list) or not 1<=len(ids)<=24:raise ValueError('Choose 1â€“24 image records')

            try:rows=sorted([exposure(k) for k in dict.fromkeys(ids)],key=lambda r:float(r['t_min']))

            except ValueError:

                if self.versioned:raise APIError('An observation ID is not indexed; query its field first',404,'not_found')

                raise

            if self.versioned:

                from geometry import footprint,intersects,vector,RAD

                center=vector(params['ra'],params['dec'])

                if any(not intersects(footprint(r.get('s_region','')),center,params['fov']/120*RAD) for r in rows):raise APIError('Selected observation does not overlap the requested field')

            if mosaic and (len({r['energy_bandpassname'] for r in rows})!=1 or len({r['obs_collection'] for r in rows})!=1):raise APIError('For a spatial mosaic select one detector and one release; different epochs/wavelengths remain explicitly exploratory')
            selection=None

            key=hashlib.sha256(json.dumps({'params':params,'ids':[r['id'] for r in rows],'version':7,'mosaic':mosaic,'match':bool(p.get('match',False))},sort_keys=True).encode()).hexdigest()[:24]

            if cached_only and not (PRODUCTS/key/'manifest.json').is_file():raise APIError('This exact sequence is not prepared; cached_only forbids image fetching',409,'not_prepared')

            if key not in JOBS or JOBS[key]['state']=='failed':

                manifest=PRODUCTS/key/'manifest.json'

                if manifest.is_file():JOBS[key]={'state':'complete','manifest':json.loads(manifest.read_text())}

                else:

                    if sum(j['state'] in ('queued','running') for j in JOBS.values())>=2:raise ValueError('Two image tasks already queued; wait for completion')

                    if sum(f.stat().st_size for f in PRODUCTS.rglob('*') if f.is_file())>int(os.environ.get('SPHEREX_PRODUCT_CACHE_MIB','512'))*1024*1024:raise ValueError('Derived-product cache reached its configured capacity. Existing sequences remain accessible; operator storage allocation is required.')

                    directory=PRODUCTS/key;directory.mkdir(exist_ok=True)

                    (directory/'request.json').write_text(json.dumps({'rows':rows,'params':params,'match':bool(p.get('match',False)),'mosaic':mosaic}))

                    JOBS[key]={'state':'queued','progress':'Waiting for image worker','errors':[]}

                    EXECUTOR.submit(run_job,JOBS[key],rows,params,PRODUCTS/key,bool(p.get('match',False)),mosaic)

            if self.versioned:return self.json({'api_version':'1.0','job_id':key,'state':JOBS[key]['state'],'links':{'status':f'/api/v1/sequences/{key}','viewer':f'/?job={key}'}},200 if JOBS[key]['state']=='complete' else 202)

            return self.json({'job':key,'selection':selection},202)

        except APIError as e:return self.json({'error':{'code':e.code,'message':str(e)}},e.status)

        except Exception as e:return self.json({'error':str(e)},400)

    def assemble(self,p):
        if not isinstance(p,dict) or set(p)!={'job_ids'}:raise APIError('Supply job_ids only')
        ids=p['job_ids']
        if not isinstance(ids,list) or not 1<=len(ids)<=500 or any(not isinstance(k,str) or len(k)!=24 or any(c not in '0123456789abcdef' for c in k) for k in ids):raise APIError('Choose 1–500 prepared job IDs')
        ids=list(dict.fromkeys(ids))
        manifests=[]
        for key in ids:
            path=PRODUCTS/key/'manifest.json'
            if not path.exists():raise APIError('Every assembly source must already be prepared',409,'not_prepared')
            manifests.append(json.loads(path.read_text()))
        params=manifests[0]['parameters']
        if any(m['parameters']!=params for m in manifests):raise APIError('Assembly sources must use the same coordinate grid and diameter')
        key=hashlib.sha256(json.dumps({'assembly':ids,'version':1}).encode()).hexdigest()[:24];dest=PRODUCTS/key
        if (dest/'manifest.json').exists():JOBS[key]={'state':'complete','manifest':json.loads((dest/'manifest.json').read_text())}
        elif key not in JOBS or JOBS[key]['state']=='failed':
            if sum(j['state'] in ('queued','running') for j in JOBS.values())>=2:raise APIError('Image queue is busy; retry after current tasks finish',429,'queue_full')
            dest.mkdir(exist_ok=True);(dest/'assembly.json').write_text(json.dumps({'job_ids':ids,'params':params}))
            JOBS[key]={'state':'queued','progress':'Combining prepared arrays without archive downloads','errors':[]};EXECUTOR.submit(run_assembly,JOBS[key],ids,params,dest)
        return self.json({'job_id':key,'state':JOBS[key]['state']},200 if JOBS[key]['state']=='complete' else 202)

    def serve_product(self,relative):

        path=(PRODUCTS/relative).resolve()

        if not path.is_relative_to(PRODUCTS) or not path.is_file():return self.json({'error':'Product not found'},404)

        mime={'.png':'image/png','.gif':'image/gif','.json':'application/json','.npz':'application/octet-stream','.fits':'application/fits'}.get(path.suffix)

        if mime is None:return self.json({'error':'Unsupported product'},404)

        return self.serve_bytes(path.read_bytes(),mime)

    def serve_cutout(self,key):

        if len(key)!=24 or not all(x in '0123456789abcdef' for x in key):raise ValueError('Invalid cutout ID')

        path=CACHE/'images'/(key+'.fits')

        if not path.is_file():return self.json({'error':'Cutout evicted; prepare the sequence again'},404)

        return self.serve_bytes(path.read_bytes(),'application/fits',f'{key}.fits')

    def serve_bytes(self,raw,mime,filename=None):

        etag='"'+hashlib.sha256(raw).hexdigest()+'"'

        if self.headers.get('If-None-Match')==etag:

            self.send_response(304);self.send_header('ETag',etag);self.end_headers();return

        self.response_bytes=len(raw);self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('ETag',etag);self.send_header('Cache-Control','public,max-age=60')

        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')

        self.end_headers();self.wfile.write(raw)

    def do_OPTIONS(self):

        self.begin_request()

        if not self.host_allowed():return self.json({'error':'Host is not enabled'},403)

        if self.path=='/api/v1/sequences' and not self.origin_allowed():return self.json({'error':'Origin is not enabled for image preparation'},403)

        self.send_response(204);self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS' if self.path=='/api/v1/sequences' else 'GET,OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type,If-None-Match');self.send_header('Access-Control-Max-Age','600');self.end_headers()

    def do_HEAD(self):

        self.begin_request();self.send_response(405);self.send_header('Allow','GET,POST,OPTIONS');self.send_header('Content-Length','0');self.end_headers()

    def do_PUT(self):

        self.begin_request();return self.json({'error':'Method not allowed'},405)

    do_DELETE=do_PUT

    def send_response(self,code,message=None):

        self.response_status=code;super().send_response(code,message)

    def end_headers(self):

        if getattr(self,'_dynamic_assets',False):self.send_header('Cache-Control','no-cache')

        if getattr(self,'versioned',False) or self.path in ('/api/openapi.json','/api/docs'):

            if self.command in ('GET','OPTIONS') and self.path!='/api/v1/sequences':self.send_header('Access-Control-Allow-Origin','*')

            elif self.origin_allowed() and self.headers.get('Origin'):self.send_header('Access-Control-Allow-Origin',self.headers['Origin']);self.send_header('Vary','Origin')

            self.send_header('Access-Control-Expose-Headers','Server-Timing,X-Request-ID,ETag,X-Cache-Source')

        if hasattr(self,'started'):

            elapsed=(time.perf_counter()-self.started)*1000;self.send_header('Server-Timing',f'app;dur={elapsed:.3f}');self.send_header('X-Request-ID',self.request_id)

            if self.cache_source:self.send_header('X-Cache-Source',self.cache_source)

            from metrics import record

            record({'method':self.command,'path':urlsplit(self.path).path,'status':getattr(self,'response_status',0),'headers_ready_ms':elapsed,'bytes':self.response_bytes,'cache':self.cache_source})

        super().end_headers()

if __name__=='__main__':

    initialize_index()

    def raw_display_worker():
        from raw_previews import watch
        watch()
    threading.Thread(target=raw_display_worker,daemon=True).start()
    print('SPHEREx viewer: http://127.0.0.1:8765',flush=True)

    ThreadingHTTPServer((os.environ.get('SPHEREX_BIND','127.0.0.1'),int(os.environ.get('SPHEREX_PORT','8765'))),Handler).serve_forever()

