import tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch
import overlays
from catalogue import APIError


class OverlayOutageTests(unittest.TestCase):
    def test_outage_has_clear_message_without_a_cached_catalogue(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(overlays,'CACHE',Path(directory)),patch.object(overlays,'text',side_effect=RuntimeError('HTTP 502')):
            with self.assertRaises(APIError) as caught:overlays.catalogue(133,-7,5,'wise')
            self.assertEqual(caught.exception.status,502);self.assertEqual(caught.exception.code,'irsa_unavailable')
            self.assertIn('IRSA is unavailable',str(caught.exception))
    def test_outage_retains_older_cached_catalogue(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(overlays,'CACHE',Path(directory)):
            with patch.object(overlays,'text',return_value='metadata'),patch.object(overlays,'parse_votable',return_value={'rows':[{'ra':'133','dec':'-7','designation':'test'}],'truncated':False}):
                original=overlays.catalogue(133,-7,5,'wise')
            for path in (Path(directory)/'overlays').glob('*.json'):os.utime(path,(0,0))
            with patch.object(overlays,'text',side_effect=RuntimeError('HTTP 502')):
                found=overlays.catalogue(133,-7,5,'wise')
            self.assertEqual(found['rows'],original['rows']);self.assertTrue(found['stale']);self.assertTrue(found['archive_unavailable'])


if __name__=='__main__':unittest.main()
