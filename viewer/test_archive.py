import unittest
from pathlib import Path
from archive import parse_votable, query_url

class ArchiveTests(unittest.TestCase):
    def test_saved_real_metadata(self):
        root = Path(__file__).parent / 'evidence'
        dr1 = parse_votable((root / 'wise0855-spherex_dr1.xml').read_bytes())
        self.assertEqual(len(dr1['rows']), 258)
        self.assertFalse(dr1['truncated'])
        self.assertTrue(all(r['access_url'].startswith('https://irsa.ipac.caltech.edu/') for r in dr1['rows']))
        self.assertEqual(parse_votable((root / 'wise0855-spherex_qr3.xml').read_bytes())['rows'], [])

    def test_unknown_is_not_empty_coverage(self):
        with self.assertRaises(ValueError):
            parse_votable('<VOTABLE xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><INFO name="QUERY_STATUS" value="ERROR">failed</INFO></VOTABLE>')

    def test_query_bounds(self):
        for ra, dec, fov in [('nan',0,5), (360,0,5), (1,91,5), (1,0,100)]:
            with self.assertRaises(ValueError):
                query_url(ra,dec,fov,'spherex_dr1')
        self.assertIn('0.041666',query_url(1,2,5,'spherex_dr1'))

if __name__ == '__main__':
    unittest.main()
