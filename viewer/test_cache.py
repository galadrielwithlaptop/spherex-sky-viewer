import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import store
from archive import parse_votable, query_url
from server import search_collection

class CatalogueTests(unittest.TestCase):
    def test_repeat_search_needs_no_archive_request_and_keeps_ids(self):
        result=parse_votable((Path(__file__).parent/'evidence/wise0855-spherex_dr1.xml').read_bytes())
        url=query_url(133.7951291667,-7.2451472222,5,'spherex_dr1')
        with tempfile.TemporaryDirectory() as d,patch.object(store,'DB',Path(d)/'test.sqlite'):
            store.put_query(url,result)
            with patch('server.text',side_effect=AssertionError('Repeated search must use saved metadata')):
                cached=search_collection(url,'spherex_dr1')
            self.assertTrue(cached['cached']);self.assertFalse(cached['stale'])
            self.assertEqual(len(cached['rows']),258)
            self.assertEqual(store.exposure(cached['rows'][0]['id'])['obs_id'],cached['rows'][0]['obs_id'])
            with patch('server.text',side_effect=RuntimeError('Offline')):
                stale=search_collection(url,'spherex_dr1',refresh=True)
            self.assertTrue(stale['stale']);self.assertEqual(len(stale['rows']),258)

if __name__=='__main__':unittest.main()
