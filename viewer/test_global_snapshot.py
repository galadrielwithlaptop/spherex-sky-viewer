import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import store,sync_catalogue as sync
from archive import query_url
from test_spatial import row

class GlobalSnapshotTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.patch=patch.object(store,'DB',Path(self.tmp.name)/'catalogue.sqlite');self.patch.start();store.initialize_index()
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def test_completed_allsky_records_are_not_hidden_by_older_regional_snapshot(self):
  a=row('a','CIRCLE ICRS 0 0 1');b=row('b','CIRCLE ICRS 0 0 1')
  store.put_query(query_url(0,0,5,'spherex_dr1'),{'rows':[a],'truncated':False})
  state={'generation':'generation1','start_mjd':50000,'end_mjd':70000};sync.register_generation(state);sync.ingest([a,b],state['generation'])
  self.assertEqual(len(store.spatial_rows(0,0,.01,['spherex_dr1'])['rows']),1)
  self.assertFalse(store.coverage(0,0,.01,'spherex_qr3')['complete'])
  sync.finish_generation(state)
  found=store.spatial_rows(0,0,.01,['spherex_dr1'])['rows'];self.assertEqual(len(found),2);self.assertTrue(all(r['index_membership']=='complete_allsky_snapshot' for r in found))
  scope=store.coverage(0,0,.01,'spherex_qr3');self.assertTrue(scope['complete']);self.assertEqual(scope['scope'],'all_sky_time_interval')
 def test_new_global_snapshot_retains_history_but_does_not_resurrect_retired_products(self):
  a=row('a','CIRCLE ICRS 0 0 1');b=row('b','CIRCLE ICRS 0 0 1')
  state={'generation':'generation1','start_mjd':50000,'end_mjd':70000};sync.register_generation(state);sync.ingest([a,b],state['generation']);sync.finish_generation(state)
  old=store.spatial_rows(0,0,.01,['spherex_dr1'])['rows'];old_id=next(r['id'] for r in old if r['obs_id']=='a')
  state['generation']='generation2';sync.register_generation(state);sync.ingest([b],state['generation']);sync.finish_generation(state)
  self.assertEqual([r['obs_id'] for r in store.spatial_rows(0,0,.01,['spherex_dr1'])['rows']],['b']);self.assertEqual(store.exposure(old_id)['obs_id'],'a')
