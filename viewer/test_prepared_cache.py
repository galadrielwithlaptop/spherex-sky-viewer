import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from prepared_cache import find


class PreparedCacheTests(unittest.TestCase):
    def test_cache_uses_existing_pixels_and_honours_field_and_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            products=Path(directory);key='a'*24;dest=products/key;raw=dest/'raw';raw.mkdir(parents=True)
            params={'ra':133.0,'dec':-7.0,'fov':5}
            frames=[{'id':str(i),'detector':'SPHEREx-D4','mjd':60000+i,'image':f'/products/{key}/raw/{i}.png'} for i in range(3)]
            (dest/'manifest.json').write_text(json.dumps({'parameters':params,'frames':frames,'groups':[]}))
            (raw/'manifest.json').write_text(json.dumps({'frames':frames}))
            (raw/'0.png').write_bytes(b'cached');(raw/'1.png').write_bytes(b'cached')
            with patch('network.download',side_effect=AssertionError('Cache lookup must not fetch archive data')):
                found=find(products,params)
                self.assertEqual(found['cached_frames'],2);self.assertEqual(len(found['manifest']['frames']),2)
                self.assertEqual(found['pixel_downloads'],0)
                self.assertIsNone(find(products,{**params,'fov':10})['job_id'])
                self.assertIsNone(find(products,params,'SPHEREx-D1')['job_id'])
                self.assertIsNone(find(products,params,start='2026-01-01')['job_id'])


if __name__=='__main__':unittest.main()
