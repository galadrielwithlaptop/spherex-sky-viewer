import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import numpy as np
from imaging import build

class AllRecordsTests(unittest.TestCase):
 def fake(self,row,**params):
  a=np.full((256,256),float(row['n']));a[:20,:20]=np.nan
  m=dict(id=str(row['n']),observation=str(row['n']),detector='SPHEREx-D4',collection='spherex_dr1',mjd=60000+row['n'],utc=f'epoch-{row["n"]}',wavelength_um=2.5+row['n']*.4,bandwidth_um=.08,wavelength_reference='target',valid_fraction=float(np.isfinite(a).mean()))
  return a,m
 def test_matching_does_not_discard_unmatched_images(self):
  with tempfile.TemporaryDirectory() as d,patch('imaging.frame',side_effect=self.fake),patch('imaging.wavelength_probe',side_effect=AssertionError('Do not prefilter records')):
   job={};build(job,[{'n':i} for i in range(3)],dict(ra=0,dec=0,fov=7.5),Path(d),match=True)
   self.assertEqual(len(job['manifest']['frames']),3);self.assertEqual(len(job['manifest']['groups']),3)
 def test_mosaic_keeps_gaps_and_tracks_contributors(self):
  with tempfile.TemporaryDirectory() as d,patch('imaging.frame',side_effect=self.fake):
   job={};build(job,[{'n':i} for i in range(2)],dict(ra=0,dec=0,fov=7.5),Path(d),mosaic=True)
   self.assertEqual(len(job['manifest']['mosaic']['source_ids']),2)
   counts=np.load(Path(d)/'mosaic-coverage.npz')['contributors'];self.assertEqual(counts[0,0],0);self.assertEqual(counts[100,100],2)
   self.assertTrue((Path(d)/'mosaic.png').is_file())

 def test_cached_assembly_regroups_and_uses_common_stretch(self):
  import server
  with tempfile.TemporaryDirectory() as d,patch.object(server,'PRODUCTS',Path(d)),patch('network.download',side_effect=AssertionError('No archive downloads')):
   ids=[]
   for i in range(2):
    key=str(i)*24;ids.append(key);source=Path(d)/key;source.mkdir();a,m=self.fake({'n':i})
    np.savez_compressed(source/'aligned.npz',**{'0':a})
    (source/'manifest.json').write_text(json.dumps({'parameters':dict(ra=0,dec=0,fov=7.5),'frames':[m]}))
   job={};server.run_assembly(job,ids,dict(ra=0,dec=0,fov=7.5),Path(d)/('a'*24))
   self.assertEqual(job['state'],'complete');self.assertEqual(len(job['manifest']['frames']),2)
   self.assertEqual(job['manifest']['stretch']['low'],0);self.assertEqual(job['manifest']['stretch']['high'],1)
