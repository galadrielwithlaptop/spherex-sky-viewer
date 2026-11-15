"""HTTP contract tests on an isolated loopback server; all remote transfers denied."""
import gzip,json,threading,tempfile,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
import server,store
from archive import query_url
from test_spatial import row

class PublicAPITests(unittest.TestCase):
    def test_metadata_sync_error_keeps_progress_fields(self):
        path=self.root/'allsky-sync.json'
        path.write_text(json.dumps({'status':'upstream_failed','error':'archive timeout','returned_records':12,'pixel_downloads':0}))
        try:
            status,_,body=self.json('/api/v1/catalogue-sync')
            self.assertEqual(status,200);self.assertEqual(body['returned_records'],12)
            self.assertEqual(body['status'],'upstream_failed');self.assertEqual(body['error'],'archive timeout')
        finally:path.unlink()
    @classmethod
    def setUpClass(cls):
        cls.stack=ExitStack();cls.tmp=cls.stack.enter_context(tempfile.TemporaryDirectory());cls.root=Path(cls.tmp)
        cls.stack.enter_context(patch.object(store,'DB',cls.root/'catalogue.sqlite'))
        cls.products=cls.root/'products';cls.products.mkdir();(cls.root/'images').mkdir()
        cls.stack.enter_context(patch.object(server,'PRODUCTS',cls.products));cls.stack.enter_context(patch.object(server,'CACHE',cls.root));cls.stack.enter_context(patch.object(server,'JOBS',{}))
        cls.stack.enter_context(patch('server.Handler.log_message',lambda *a:None))
        cls.no_network=cls.stack.enter_context(patch('network.download',side_effect=AssertionError('HTTP tests must not fetch archive bytes')))
        cls.no_worker=cls.stack.enter_context(patch.object(server.EXECUTOR,'submit',side_effect=AssertionError('HTTP tests must not start image workers')))
        rows=[row(str(i),'CIRCLE ICRS 0 0 1',detector=1+i%2,mjd=60000+i/10) for i in range(12)]
        store.put_query(query_url(0,0,30,'spherex_dr1'),{'rows':rows,'truncated':False});cls.rows=rows
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base=f'http://127.0.0.1:{cls.http.server_port}';cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.stack.close()
    def request(self,path,method='GET',body=None,headers=None):
        data=json.dumps(body).encode() if body is not None else None
        h=dict(headers or {})
        if body is not None:h.setdefault('Content-Type','application/json')
        req=urllib.request.Request(self.base+path,data=data,headers=h,method=method)
        try:r=urllib.request.urlopen(req,timeout=10)
        except urllib.error.HTTPError as e:r=e
        raw=r.read();status=r.status;head=dict(r.headers)
        if head.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
        return status,head,raw
    def json(self,*args,**kwargs):
        status,headers,raw=self.request(*args,**kwargs);return status,headers,json.loads(raw)
    def test_metadata_query_cors_timing_and_zero_pixel_fetch(self):
        status,h,p=self.json('/api/v1/observations?ra=0&dec=0&collections=spherex_dr1&mode=cache_only&limit=3',headers={'Origin':'https://caller.example'})
        self.assertEqual(status,200);self.assertEqual(h['Access-Control-Allow-Origin'],'*');self.assertIn('Server-Timing',h);self.assertEqual(h['X-Request-ID'],p['request_id']);self.assertEqual(len(p['observations']),3);self.assertEqual(p['provenance']['pixel_downloads'],0)
        self.assertIn('next_cursor',p['pagination']);self.assertEqual(self.no_network.call_count,0)
    def test_normalized_detail_and_unknown_id(self):
        status,h,p=self.json('/api/v1/observations/'+self.rows[0]['id']);self.assertEqual(status,200);self.assertEqual(p['observation']['detector'],1)
        status,h,p=self.json('/api/v1/observations/'+'f'*24);self.assertEqual(status,404);self.assertEqual(p['error']['code'],'not_found')
    def test_invalid_input_is_structured(self):
        for query in ['ra=nan&dec=0','ra=0&dec=91','ra=0&dec=0&detector=7','ra=0&dec=0&limit=999','ra=0&ra=1&dec=0','ra=0&dec=0&typo=1']:
            status,h,p=self.json('/api/v1/observations?'+query);self.assertEqual(status,400);self.assertIsInstance(p['error']['message'],str);self.assertIn('request_id',p)
    def test_unindexed_cache_only_is_explicit(self):
        status,h,p=self.json('/api/v1/observations?ra=120&dec=50&mode=cache_only');self.assertEqual(status,200);self.assertFalse(p['coverage']['complete_for_requested_collections']);self.assertEqual(p['observations'],[]);self.assertIn('not established',p['notice'])
    def test_coverage_status_targets_options_and_schema(self):
        for path in ['/api/v1/coverage?ra=0&dec=0&mode=cache_only','/api/v1/status','/api/v1/targets','/api/v1/options','/api/openapi.json']:
            status,h,p=self.json(path);self.assertEqual(status,200)
        status,h,p=self.json('/api/openapi.json');self.assertEqual(p['openapi'],'3.1.0');self.assertIn('/api/v1/sequences',p['paths'])
        status,h,raw=self.request('/api/docs');self.assertEqual(status,200);self.assertIn(b'METADATA FIRST',raw)
    def test_json_compression(self):
        status,h,p=self.json('/api/v1/observations?ra=0&dec=0&collections=spherex_dr1&mode=cache_only',headers={'Accept-Encoding':'gzip'})
        self.assertEqual(status,200);self.assertEqual(h['Content-Encoding'],'gzip');self.assertEqual(len(p['observations']),12)
        status,h,p=self.json('/api/v1/observations?ra=0&dec=0&mode=cache_only',headers={'Accept-Encoding':'gzip;q=0'});self.assertNotIn('Content-Encoding',h)
        status,h,p=self.json('/api/v1/observations?ra=0&dec=0&mode=cache_only',headers={'Accept-Encoding':'gzip;q=0.5'});self.assertEqual(h['Content-Encoding'],'gzip')
    def test_sequence_post_is_explicit_and_cached_only_cannot_download(self):
        p={'ra':0,'dec':0,'fov_arcmin':5,'observation_ids':[self.rows[0]['id'],self.rows[2]['id']],'match_wavelengths':True,'cached_only':True}
        status,h,r=self.json('/api/v1/sequences','POST',p);self.assertEqual(status,409);self.assertEqual(r['error']['code'],'not_prepared');self.assertEqual(self.no_worker.call_count,0)
        for update in [{'ra':float('nan')},{'observation_ids':['a'*24]},{'match_wavelengths':'yes'},{'observation_ids':[self.rows[0]['id']]*25},{'ra':100}]:
            status,h,r=self.json('/api/v1/sequences','POST',dict(p,**update));self.assertIn(status,(400,404));self.assertIn('error',r)
        status,h,r=self.json('/api/v1/sequences','POST',p,headers={'Content-Type':'text/plain'});self.assertEqual(status,415)
    def test_sequence_read_never_resumes_downloads(self):
        key='b'*24;p=self.products/key;p.mkdir(exist_ok=True);(p/'request.json').write_text('{}')
        status,h,r=self.json('/api/v1/sequences/'+key);self.assertEqual(status,200);self.assertEqual(r['state'],'interrupted');self.assertEqual(self.no_worker.call_count,0)
    def test_cached_products_and_etag(self):
        key='c'*24;p=self.products/key;p.mkdir(exist_ok=True);raw=b'test-only artifact';(p/'0.png').write_bytes(raw)
        status,h,data=self.request('/api/v1/products/'+key+'/0.png');self.assertEqual(status,200);self.assertEqual(data,raw)
        status,h2,data=self.request('/api/v1/products/'+key+'/0.png',headers={'If-None-Match':h['ETag']});self.assertEqual(status,304);self.assertEqual(data,b'')
        status,h,p=self.json('/api/v1/products/../../server.py');self.assertEqual(status,404)
    def test_preflight_origin_and_host_controls(self):
        status,h,raw=self.request('/api/v1/observations','OPTIONS',headers={'Origin':'https://caller.example'});self.assertEqual(status,204);self.assertEqual(h['Access-Control-Allow-Origin'],'*')
        status,h,p=self.json('/api/v1/sequences','OPTIONS',headers={'Origin':'https://caller.example'});self.assertEqual(status,403)
        status,h,p=self.json('/api/v1/status',headers={'Host':'unapproved.example'});self.assertEqual(status,403)
        with patch.dict('os.environ',{'SPHEREX_ALLOWED_ORIGINS':'https://caller.example'}):
            status,h,raw=self.request('/api/v1/sequences','OPTIONS',headers={'Origin':'https://caller.example'});self.assertEqual(status,204);self.assertEqual(h['Access-Control-Allow-Origin'],'https://caller.example')
    def test_method_and_missing_routes(self):
        status,h,p=self.json('/api/v1/status','DELETE');self.assertEqual(status,405)
        status,h,p=self.json('/api/v1/unknown');self.assertEqual(status,404)
        status,h,raw=self.request('/api/v1/status','HEAD');self.assertEqual(status,405);self.assertEqual(raw,b'')

    def test_field_audit_and_sync_status_are_reachable(self):
        status,_,body=self.json('/api/v1/field-audit?ra=0&dec=0&fov_arcmin=5')
        self.assertEqual(status,200);self.assertEqual(body['total'],12);self.assertEqual(body['pixel_downloads'],0)
        status,_,body=self.json('/api/v1/catalogue-sync')
        self.assertEqual(status,200);self.assertEqual(body['status'],'not_started')

    def test_mosaic_request_is_explicit_and_cached_only(self):
        ids=[r['id'] for r in self.rows if r['energy_bandpassname']=='SPHEREx-D1'][:2]
        status,_,body=self.json('/api/v1/mosaics','POST',{'ra':0,'dec':0,'fov_arcmin':5,'observation_ids':ids,'cached_only':True})
        self.assertEqual(status,409);self.assertEqual(body['error']['code'],'not_prepared')

    def test_assembly_never_fetches_missing_source(self):
        status,_,body=self.json('/api/v1/assemblies','POST',{'job_ids':['a'*24]})
        self.assertEqual(status,409);self.assertEqual(body['error']['code'],'not_prepared')

    def test_field_jobs_reject_invalid_requests_without_worker(self):
        status,_,body=self.json('/api/v1/field-downloads','POST',{'ra':0,'dec':0,'fov_arcmin':5,'observation_ids':[]})
        self.assertEqual(status,400)
        status,_,body=self.json('/api/v1/field-downloads/not-an-id')
        self.assertEqual(status,400)
