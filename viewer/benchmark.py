"""Repeatable local API/latency audit. Default mode forbids archive transfers.

--cold-metadata permits one bounded new metadata cone (never image pixels).
Reports distinguish metadata, cached products, and unmeasured cold image paths.
"""
import argparse,csv,gzip,json,statistics,threading,time,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
import server,store

ROOT=Path(__file__).resolve().parent
def percentile(values,p):
    v=sorted(values);at=(len(v)-1)*p;lo=int(at);hi=min(lo+1,len(v)-1)
    return v[lo]+(v[hi]-v[lo])*(at-lo)

def run(repetitions=20,cold_metadata=False):
    store.initialize_index();cases=[];samples=[]
    targets=[{'name':'WISE0855','ra':133.7951291667,'dec':-7.2451472222}]+json.loads((ROOT/'evidence/target-coverage.json').read_text())
    def add(name,path,category='local_metadata',body=None,headers=None):cases.append(dict(name=name,path=path,category=category,body=body,headers=headers or {}))
    from urllib.parse import urlencode
    def obs(**kw):return '/api/v1/observations?'+urlencode(dict(ra=targets[0]['ra'],dec=targets[0]['dec'],fov_arcmin=5,mode='cache_only',**kw))
    for t in targets:add('target '+t['name'],'/api/v1/observations?'+urlencode(dict(ra=t['ra'],dec=t['dec'],fov_arcmin=5,mode='cache_only')))
    for d in range(1,7):add(f'detector {d}',obs(detector=d))
    for fov in (1,10,30,60):add(f'FOV {fov} arcmin','/api/v1/observations?'+urlencode(dict(ra=targets[0]['ra'],dec=targets[0]['dec'],fov_arcmin=fov,mode='cache_only')))
    add('date interval',obs(start_mjd=60800,end_mjd=61000));add('descending order',obs(sort='desc'))
    for c in ('spherex_dr1','spherex_qr3','spherex_dr1_deep','spherex_qr3_deep'):add('collection '+c,obs(collections=c))
    for size in (1,500):add(f'page size {size}',obs(limit=size))
    add('gzip metadata',obs(),headers={'Accept-Encoding':'gzip'})
    add('unknown indexed region','/api/v1/observations?ra=200&dec=-80&mode=cache_only')
    for p in ('status','options','targets'):add(p,'/api/v1/'+p)
    add('known coverage','/api/v1/coverage?'+urlencode(dict(ra=targets[0]['ra'],dec=targets[0]['dec'],fov_arcmin=5)))
    add('OpenAPI contract','/api/openapi.json');add('API documentation','/api/docs')
    for name in ('gaia','wise'):add(name+' overlay metadata','/api/v1/overlays/'+name+'?'+urlencode(dict(ra=targets[0]['ra'],dec=targets[0]['dec'],fov_arcmin=5,mode='cache_only')),'cached_catalogue_overlay')
    source=server.PRODUCTS/'32a51c0385db27101ce8fb1d'/'manifest.json'
    if source.exists():
        m=json.loads(source.read_text());key=source.parent.name
        add('cached sequence acceptance','/api/v1/sequences','cached_sequence_control',body=dict(ra=m['parameters']['ra'],dec=m['parameters']['dec'],fov_arcmin=m['parameters']['fov'],observation_ids=[f['id'] for f in m['frames']],match_wavelengths=True,cached_only=True))
        add('cached sequence status',f'/api/v1/sequences/{key}','cached_sequence_control')
        for filename in ['manifest.json','0.png','coadd-0.png','difference-0.png','blink-0.gif','aligned.npz']:add('cached '+filename,f'/api/v1/products/{key}/{filename}','cached_image_product')
        add('cached native FITS','/api/v1/cutouts/'+m['frames'][0]['fits_key'],'cached_image_product')
    else:m=None
    def request(base,case):
        data=json.dumps(case['body']).encode() if case['body'] is not None else None
        headers=dict(case['headers']);headers.update({'Content-Type':'application/json'} if data else {})
        start=time.perf_counter();req=urllib.request.Request(base+case['path'],data=data,headers=headers)
        try:response=urllib.request.urlopen(req,timeout=120)
        except urllib.error.HTTPError as e:response=e
        with response:
            raw=response.read();duration=(time.perf_counter()-start)*1000;wire=len(raw);status=response.status;h=dict(response.headers)
        if h.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
        payload=json.loads(raw) if h.get('Content-Type','').startswith('application/json') else None
        return {'elapsed_ms':duration,'wire_bytes':wire,'decoded_bytes':len(raw),'status':status,'server_timing':h.get('Server-Timing'),'cache':h.get('X-Cache-Source'),'coverage_complete':payload.get('coverage',{}).get('complete_for_requested_collections') if payload else None},payload
    with ExitStack() as stack:
        stack.enter_context(patch('server.Handler.log_message',lambda *a:None))
        no_images=stack.enter_context(patch.object(server.EXECUTOR,'submit',side_effect=AssertionError('Benchmark cannot start an image worker')))
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{http.server_port}'
        try:
            # This phase is intentionally outside the archive-transfer prohibition.
            cold=[]
            if cold_metadata:
                c=dict(name='new nearby metadata cone',path='/api/v1/observations?'+urlencode(dict(ra=133.8751291667,dec=-7.2451472222,fov_arcmin=1,mode='auto')),category='archive_metadata_only',body=None,headers={})
                for phase in ('initial_request','repeat_request'):
                    measured,payload=request(base,c);cold.append(dict(measured,phase=phase,collection_sources=[x['source'] for x in payload.get('coverage',{}).get('collections',[])],archive_errors=[x.get('error') for x in payload.get('coverage',{}).get('collections',[]) if x.get('error')],retry_after_seconds=[x.get('retry_after_seconds') for x in payload.get('coverage',{}).get('collections',[])],pixel_downloads=payload.get('provenance',{}).get('pixel_downloads')))
            denied=stack.enter_context(patch('network.download',side_effect=AssertionError('Warm benchmark must not contact external archives')))
            for case in cases:
                request(base,case) # warm interpreter, serializer and filesystem caches
                values=[]
                for i in range(repetitions):
                    measured,payload=request(base,case);values.append(measured['elapsed_ms']);samples.append(dict(case=case['name'],category=case['category'],iteration=i,**measured))
                latest=samples[-1]
                case.update(samples=repetitions,p50_ms=statistics.median(values),p95_ms=percentile(values,.95),maximum_ms=max(values),wire_bytes=latest['wire_bytes'],decoded_bytes=latest['decoded_bytes'],status=latest['status'],coverage_complete=latest['coverage_complete'])
                print(f"{case['name']}: p50={case['p50_ms']:.2f} ms p95={case['p95_ms']:.2f} ms status={case['status']}",flush=True)
            assert denied.call_count==0,'A warm regression attempted external archive access'
            assert no_images.call_count==0,'A regression attempted image preparation'
        finally:http.shutdown();http.server_close();thread.join()
    report={'generated_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'method':'Monotonic end-to-end local HTTP request through complete response read; 1 warmup per route; no concurrent load','repetitions':repetitions,'index':store.stats(),'archive_image_downloads':0,'warm_external_requests':0,'cold_metadata_requests':cold,'cases':cases,'not_measured':['New image cutout transfer, alignment and first-time sequence preparation (not run: metadata-first/no bulk image fetch scope)','Internet-hosted service latency and multi-user load (no public deployment authorized)','Scientific identification, calibrated variability significance and full-response validation']}
    (ROOT/'latency-results.json').write_text(json.dumps(report,indent=2))
    with (ROOT/'latency-samples.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
    lines=['# Regression latency report','',report['method']+'.','',f"{repetitions} measured requests per case; all image artifacts were already cached. No new archive images were requested.",'','| Case | Status | p50 ms | p95 ms | Bytes sent | Coverage complete |','| --- | ---: | ---: | ---: | ---: | --- |']
    for c in cases:lines.append(f"| {c['name']} | {c['status']} | {c['p50_ms']:.2f} | {c['p95_ms']:.2f} | {c['wire_bytes']} | {c['coverage_complete']} |")
    lines+=['','## Cold metadata comparison','',json.dumps(cold,indent=2),'','## Unmeasured','']+['- '+x for x in report['not_measured']]
    (ROOT/'LATENCY_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    baseline_path=ROOT/'latency-baseline.json'
    if baseline_path.exists():
        old=json.loads(baseline_path.read_text());before={x['name']:x for x in old['cases']}
        comparisons=[{'case':c['name'],'baseline_p50_ms':before[c['name']]['p50_ms'],'current_p50_ms':c['p50_ms'],'baseline_p95_ms':before[c['name']]['p95_ms'],'current_p95_ms':c['p95_ms']} for c in cases if c['name'] in before]
        (ROOT/'latency-comparison.json').write_text(json.dumps({'baseline_generated_utc':old['generated_utc'],'current_generated_utc':report['generated_utc'],'caveat':'Sequential local runs, not a controlled internet/load study. Current payload includes additional provenance fields. Archive availability is not an application speed guarantee.','cases':comparisons,'baseline_archive_metadata':old['cold_metadata_requests'],'current_archive_metadata':cold},indent=2))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repetitions',type=int,default=20);parser.add_argument('--cold-metadata',action='store_true');args=parser.parse_args()
    if not 3<=args.repetitions<=100:parser.error('Use 3–100 repetitions')
    run(args.repetitions,args.cold_metadata)
