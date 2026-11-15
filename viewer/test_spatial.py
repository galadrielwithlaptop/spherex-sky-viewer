import base64,json,math,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode,parse_qs
import store
from archive import query_url
from catalogue import query,discover,APIError
from geometry import footprint,intersects,vector,RAD

def row(name,region,ra=0,dec=0,detector=1,collection='spherex_dr1',mjd=60000):
    return {'obs_id':name,'access_url':f'https://irsa.ipac.caltech.edu/ibe/data/spherex/{collection}/{name}-D{detector}.fits','s_ra':str(ra),'s_dec':str(dec),'t_min':str(mjd),'t_max':str(mjd+.01),'t_exptime':'100','energy_bandpassname':f'SPHEREx-D{detector}','obs_collection':collection,'s_region':region,'em_min':'1e-6','em_max':'2e-6'}

def votable(rows,overflow=False):
    import xml.etree.ElementTree as E
    root=E.Element('VOTABLE',xmlns='http://www.ivoa.net/xml/VOTable/v1.3');resource=E.SubElement(root,'RESOURCE');E.SubElement(resource,'INFO',name='QUERY_STATUS',value='OVERFLOW' if overflow else 'OK');table=E.SubElement(resource,'TABLE')
    names=list(rows[0]) if rows else list(row('empty','CIRCLE ICRS 0 0 1'))
    for n in names:E.SubElement(table,'FIELD',name=n,datatype='char',arraysize='*')
    data=E.SubElement(E.SubElement(table,'DATA'),'TABLEDATA')
    for r in rows:
        tr=E.SubElement(data,'TR')
        for n in names:E.SubElement(tr,'TD').text=str(r.get(n,''))
    return E.tostring(root)

class GeometryTests(unittest.TestCase):
    def test_wrap_and_edge_intersection(self):
        p=footprint('POLYGON ICRS 359 -1 1 -1 1 1 359 1 359 -1')
        self.assertTrue(p['supported']);self.assertTrue(intersects(p,vector(0,0),0))
        self.assertTrue(intersects(p,vector(1.05,0),.06*RAD))
        self.assertFalse(intersects(p,vector(2,0),.1*RAD))
    def test_pole_and_reversed_winding(self):
        for coords in ['0 88 90 88 180 88 270 88','270 88 180 88 90 88 0 88']:
            p=footprint('POLYGON ICRS '+coords)
            self.assertTrue(p['supported']);self.assertTrue(intersects(p,vector(123,90),0));self.assertFalse(intersects(p,vector(123,80),RAD))
    def test_circle_and_unknown_are_conservative(self):
        p=footprint('CIRCLE ICRS 359.9 0 .2')
        self.assertTrue(intersects(p,vector(.1,0),.001*RAD));self.assertFalse(intersects(p,vector(5,0),RAD))
        self.assertTrue(intersects(footprint('unsupported'),vector(90,0),0))

class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(store,'DB',Path(self.temp.name)/'index.sqlite');self.patch.start()
        self.failures=patch('catalogue._failures',{});self.failures.start()
    def tearDown(self):self.failures.stop();self.patch.stop();self.temp.cleanup()
    def add(self,rows,ra=0,dec=0,fov=30,collection='spherex_dr1',truncated=False):
        result={'rows':rows,'truncated':truncated};store.put_query(query_url(ra,dec,fov,collection),result);return result
    def test_index_matches_footprint_instead_of_image_center(self):
        self.add([row('wrap','POLYGON ICRS 359 -1 1 -1 1 1 359 1',ra=50,dec=20),row('away','CIRCLE ICRS 30 0 .5',ra=0)])
        r=store.spatial_rows(0,0,.01,['spherex_dr1'])
        self.assertEqual([x['obs_id'] for x in r['rows']],['wrap']);self.assertEqual(r['unverified_footprints'],0)
    def test_upsert_keeps_spatial_entries_consistent(self):
        rows=[row('one','CIRCLE ICRS 0 0 1')];self.add(rows);self.add(rows)
        with store.connection() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM footprint_index').fetchone()[0],1)
        rows[0]['s_region']='CIRCLE ICRS 30 0 1';self.add(rows)
        self.assertEqual(len(store.spatial_rows(0,0,.01)['rows']),0)
        self.assertEqual(len(store.spatial_rows(30,0,.01)['rows']),1)
    def test_refreshed_snapshot_does_not_resurrect_retired_products(self):
        a=row('a','CIRCLE ICRS 0 0 1');b=row('b','CIRCLE ICRS 0 0 1')
        self.add([a,b]);self.add([b])
        self.assertEqual([r['obs_id'] for r in store.spatial_rows(0,0,.01)['rows']],['b'])
        self.assertEqual(store.stats()['exposures'],2)
    def test_membership_only_refresh_invalidates_pagination(self):
        a=row('a','CIRCLE ICRS 0 0 1');b=row('b','CIRCLE ICRS 0 0 1')
        self.add([a,b]);q={'ra':['0'],'dec':['0'],'collections':['spherex_dr1'],'mode':['cache_only'],'limit':['1']}
        first,_=query(q);self.add([b])
        with self.assertRaises(APIError) as e:query(dict(q,cursor=[first['pagination']['next_cursor']]))
        self.assertEqual(e.exception.status,409)
    def test_filters_and_inclusive_time_interval(self):
        self.add([row('a','CIRCLE ICRS 0 0 1',detector=1,mjd=60000),row('b','CIRCLE ICRS 0 0 1',detector=2,mjd=60001)])
        self.assertEqual([r['obs_id'] for r in store.spatial_rows(0,0,.01,detector=1,start=60000.01,end=60000.01)['rows']],['a'])
        self.assertEqual(store.spatial_rows(0,0,.01,['spherex_qr3'])['rows'],[])
    def test_coverage_contains_nested_query_and_tracks_staleness(self):
        self.add([],fov=30)
        self.assertTrue(store.coverage(.05,0,.01,'spherex_dr1')['complete'])
        self.assertFalse(store.coverage(1,0,.01,'spherex_dr1')['complete'])
        with patch('store.time.time',return_value=time.time()+90000):self.assertFalse(store.coverage(0,0,.01,'spherex_dr1')['fresh'])
    def test_overflow_does_not_claim_complete_coverage(self):
        self.add([row('a','CIRCLE ICRS 0 0 1')],truncated=True)
        self.assertFalse(store.coverage(0,0,.01,'spherex_dr1')['complete'])
    def test_pagination_sort_and_cursor_contract(self):
        self.add([row(str(i),'CIRCLE ICRS 0 0 1',mjd=60000+i//2) for i in range(7)])
        q={'ra':['0'],'dec':['0'],'fov_arcmin':['5'],'collections':['spherex_dr1'],'mode':['cache_only'],'limit':['2']}
        ids=[];cursor=None
        while True:
            page,_=query(dict(q,**({'cursor':[cursor]} if cursor else {})));ids += [r['id'] for r in page['observations']];cursor=page['pagination']['next_cursor']
            if not cursor:break
        self.assertEqual(len(ids),7);self.assertEqual(len(set(ids)),7)
        descending,_=query(dict(q,sort=['desc'],limit=['500']))
        self.assertEqual([r['id'] for r in descending['observations']],ids[::-1])
        first,_=query(q);cursor=first['pagination']['next_cursor']
        with self.assertRaises(APIError):query(dict(q,cursor=[cursor],detector=['2']))
        self.add([row('new','CIRCLE ICRS 0 0 1',mjd=60010)])
        with self.assertRaises(APIError) as e:query(dict(q,cursor=[cursor]))
        self.assertEqual(e.exception.status,409)
    def test_invalid_queries_and_cursors(self):
        base={'ra':['0'],'dec':['0'],'mode':['cache_only']}
        for extra in [{'ra':['nan']},{'dec':['91']},{'detector':['7']},{'limit':['0']},{'sort':['bad']},{'start_mjd':['5'],'end_mjd':['4']},{'typo':['1']},{'cursor':['%%%']},{'cursor':[base64.urlsafe_b64encode(b'{"query":1}').decode()]}]:
            with self.subTest(extra=extra),self.assertRaises(APIError):query(dict(base,**extra))
    def test_cache_only_unknown_region_is_not_no_coverage(self):
        with patch('catalogue.text',side_effect=AssertionError('No network permitted')):
            page,_=query({'ra':['0'],'dec':['0'],'mode':['cache_only']})
        self.assertFalse(page['coverage']['complete_for_requested_collections']);self.assertIn('not established',page['notice']);self.assertEqual(page['provenance']['pixel_downloads'],0)
    def test_broader_metadata_query_enables_nearby_reuse(self):
        calls=[]
        def fetch(url):calls.append(url);return votable([row('a','CIRCLE ICRS 0 0 1')])
        with patch('catalogue.text',side_effect=fetch):
            a=discover(0,0,5,['spherex_dr1']);b=discover(.05,0,1,['spherex_dr1'])
        self.assertEqual(len(calls),1);self.assertEqual(a[0]['source'],'archive_metadata');self.assertEqual(b[0]['source'],'local_index')
    def test_expanded_overflow_falls_back_to_requested_cone(self):
        with patch('catalogue.text',side_effect=[votable([row('a','CIRCLE ICRS 0 0 1')],True),votable([row('a','CIRCLE ICRS 0 0 1')])]) as fetch:
            state=discover(0,0,5,['spherex_dr1'])[0]
        self.assertEqual(fetch.call_count,2);self.assertTrue(state['complete'])
        self.assertFalse(store.coverage(.1,0,.01,'spherex_dr1')['complete'])
    def test_metadata_outage_preserves_incomplete_or_stale_state(self):
        self.add([row('a','CIRCLE ICRS 0 0 1')])
        with patch('catalogue.text',side_effect=RuntimeError('offline')):
            state=discover(0,0,5,['spherex_dr1'],refresh=True)[0]
        self.assertEqual(state['error'],'offline');self.assertEqual(len(store.spatial_rows(0,0,.01)['rows']),1)
    def test_archive_failure_cooldown_avoids_repeated_stalls(self):
        with patch('catalogue.text',side_effect=RuntimeError('offline')) as fetch:
            a=discover(100,50,5,['spherex_dr1'])[0];b=discover(100,50,5,['spherex_dr1'])[0]
        self.assertEqual(fetch.call_count,1);self.assertIn('retry_after_seconds',b);self.assertFalse(b['complete'])

if __name__=='__main__':unittest.main()
