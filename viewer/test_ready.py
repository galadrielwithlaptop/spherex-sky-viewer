import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from server import ready_sequence

class ReadySequenceTests(unittest.TestCase):
    def test_saved_sequence_requires_matching_field_array_dates_and_products(self):
        with tempfile.TemporaryDirectory() as d,patch('server.PRODUCTS',Path(d)):
            p=Path(d)/('a'*24);p.mkdir()
            manifest={'parameters':{'ra':133.,'dec':-7.,'fov':5.},'frames':[{'detector':'SPHEREx-D4','mjd':60800.},{'detector':'SPHEREx-D4','mjd':60980.}],'groups':[{'indices':[0,1]}]}
            (p/'manifest.json').write_text(json.dumps(manifest))
            params=manifest['parameters']
            self.assertIsNone(ready_sequence(params,'SPHEREx-D4'))
            for i in range(2):(p/f'{i}.png').touch()
            self.assertEqual(ready_sequence(params,'SPHEREx-D4'),'a'*24)
            self.assertIsNone(ready_sequence(dict(params,ra=269.),'SPHEREx-D4'))
            self.assertIsNone(ready_sequence(params,'SPHEREx-D1'))
            self.assertIsNone(ready_sequence(params,'SPHEREx-D4',start='2026-01-01'))
            manifest['groups']=[{'indices':[0]},{'indices':[1]}]
            (p/'manifest.json').write_text(json.dumps(manifest))
            self.assertIsNone(ready_sequence(params,'SPHEREx-D4',match=True))
            self.assertEqual(ready_sequence(params,'SPHEREx-D4',match=False),'a'*24)

if __name__=='__main__':unittest.main()
