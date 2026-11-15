import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import sync_catalogue as sync

class CatalogueSyncTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  database=Path(self.tmp.name)/'catalogue.sqlite';database.touch()
  self.db_patch=patch.object(sync,'DB',database);self.db_patch.start();self.addCleanup(self.db_patch.stop)
 def test_overflow_retains_pending_partitions(self):
  with tempfile.TemporaryDirectory() as d,patch.object(sync,'STATE',Path(d)/'state.json'),patch.object(sync,'initialize_index'),patch.object(sync,'register_generation'),patch.object(sync,'text',return_value='metadata'),patch.object(sync,'parse_votable',return_value={'rows':[],'truncated':True}),patch.object(sync,'ingest') as ingest:
   result=sync.run(1);self.assertEqual(result['status'],'paused_at_request_limit');self.assertEqual(len(result['pending']),5);self.assertEqual(result['completed_partitions'],0);ingest.assert_not_called();self.assertEqual(result['pixel_downloads'],0)
 def test_upstream_failure_never_claims_complete(self):
  with tempfile.TemporaryDirectory() as d,patch.object(sync,'STATE',Path(d)/'state.json'),patch.object(sync,'initialize_index'),patch.object(sync,'register_generation'),patch.object(sync,'text',side_effect=RuntimeError('502')),patch.object(sync,'ingest') as ingest:
   result=sync.run(1);self.assertEqual(result['status'],'upstream_failed');self.assertEqual(len(result['pending']),4);ingest.assert_not_called();self.assertEqual(result['header_downloads'],0)
 def test_timeout_splits_pending_interval_without_importing_or_claiming_complete(self):
  with tempfile.TemporaryDirectory() as d,patch.object(sync,'STATE',Path(d)/'state.json'),patch.object(sync,'initialize_index'),patch.object(sync,'register_generation'),patch.object(sync,'text',side_effect=RuntimeError('timeout')),patch.object(sync,'ingest') as ingest:
   result=sync.run(1,split_failures=True);self.assertEqual(result['status'],'retrying_smaller_partition');self.assertEqual(len(result['pending']),5);self.assertEqual(result['completed_partitions'],0);ingest.assert_not_called()
