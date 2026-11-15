"""Versioned read interfaces; metadata endpoints never import the image worker."""
import json
from pathlib import Path
from catalogue import query,options,discover,observation,APIError,one,boolean
from store import exposure,stats,coverage,spatial_rows
from archive import AVAILABLE_COLLECTIONS,COLLECTIONS,query_url

ROOT=Path(__file__).resolve().parent

def get(path,q):
    if path=='/api/v1/observations':return query(q)
    if path.startswith('/api/v1/observations/'):
        key=path.rsplit('/',1)[-1]
        if len(key)!=24 or not all(c in '0123456789abcdef' for c in key):raise APIError('Invalid observation ID')
        try:r=exposure(key)
        except ValueError:raise APIError('Observation not indexed; query its field first',404,'not_found')
        return {'api_version':'1.0','observation':observation(r),'provenance':{'pixel_downloads':0}},{}
    if path=='/api/v1/coverage':
        p=options(q)
        if p['refresh']:raise APIError('Coverage inspection is local-only; refresh /observations instead')
        found=spatial_rows(p['ra'],p['dec'],p['fov']/120,p['collections'],p['detector'],p['start'],p['end'])
        states=[dict(coverage(p['ra'],p['dec'],p['fov']/120,c),collection=c) for c in p['collections']]
        return {'api_version':'1.0','collections':states,'complete':all(s['complete'] for s in states),'fresh':all(s['fresh'] for s in states),'indexed_overlaps':len(found['rows']),'unverified_footprints':found['unverified_footprints'],'pixel_downloads':0,'archive_queries':0},{}
    if path=='/api/v1/status':
        from metrics import snapshot
        return {'api_version':'1.0','catalogue':stats(),'deployment':'local development; public hosting not enabled','metadata_only_by_default':True,'telemetry':snapshot()},{}
    if path=='/api/v1/options':
        return {'api_version':'1.0','collections':AVAILABLE_COLLECTIONS,'detectors':list(range(1,7)),'fov_arcmin':{'minimum':1,'maximum':60,'geometry':'circular diameter'},'modes':['auto','cache_only'],'sort':['asc','desc'],'maximum_page_size':500,'maximum_sequence_images':24,'image_fetching':'Only explicit POST /api/v1/sequences can request pixel preparation','viewer_options':['coordinates','field_of_view','detector','date_range','sample_size','wavelength_matching','play_pause','speed','previous_next','timeline','wavelength_group','coadd','difference','gaia_overlay','wise_overlay','display_brightness','metadata_export','gif_export','fits_export','coordinate_url','job_resume']},{}
    if path=='/api/v1/targets':
        rows=[{'name':'WISE0855','ra':133.7951291667,'dec':-7.2451472222,'provenance':'Coordinates supplied in the challenge','proper_motion_applied':False}]
        for r in json.loads((ROOT/'evidence/target-coverage.json').read_text()):
            rows.append({'name':r['name'],'ra':r['ra'],'dec':r['dec'],'provenance':'CDS Sesame/SIMBAD catalogue position checked 2026-11-14','proper_motion_applied':False})
        return {'api_version':'1.0','targets':rows},{}
    raise APIError('Unknown API endpoint',404,'not_found')
