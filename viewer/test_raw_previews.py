import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
import raw_previews

class ArchiveImageDisplayTests(unittest.TestCase):
 def test_archive_IMAGE_is_not_background_subtracted_or_flag_masked(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'source.fits';w=WCS(naxis=2);w.wcs.crpix=[64.5,64.5];w.wcs.crval=[0,0];w.wcs.cdelt=[-.001,-.001];w.wcs.ctype=['RA---TAN','DEC--TAN']
   fits.HDUList([fits.PrimaryHDU(),fits.ImageHDU(np.full((128,128),7.),header=w.to_header(),name='IMAGE'),fits.ImageHDU(np.full((128,128),5.),name='ZODI'),fits.ImageHDU(np.full((128,128),65535,dtype=np.int32),name='FLAGS')]).writeto(path)
   original=path.read_bytes();array=raw_previews.image_plane(path,{'ra':0,'dec':0,'fov':1})
   self.assertTrue(np.all(array==7));self.assertEqual(path.read_bytes(),original)
 def test_common_raw_stretch_and_existing_products_preserved(self):
  with tempfile.TemporaryDirectory() as d,patch.object(raw_previews,'RAW',Path(d)/'raw-arrays'),patch.object(raw_previews,'CACHE',Path(d)):
   root=Path(d);(root/'raw-arrays').mkdir();job=root/'products'/'test';job.mkdir(parents=True);old=job/'0.png';old.write_bytes(b'existing analysis product')
   frames=[]
   for i,value in enumerate([7.,70.]):
    key=str(i)*24;np.savez_compressed(root/'raw-arrays'/(key+'.npz'),image=np.full((256,256),value));frames.append({'id':key,'fits_key':key,'source_url':'https://irsa.ipac.caltech.edu/test'})
   path=job/'manifest.json';source={'parameters':{'ra':0,'dec':0,'fov':10},'frames':frames};path.write_text(json.dumps(source));raw_previews.render(path)
   result=json.loads((job/'raw'/'manifest.json').read_text());self.assertEqual(result['stretch']['low'],7);self.assertEqual(result['stretch']['high'],70)
   self.assertFalse(result['zodi_subtracted']);self.assertFalse(result['quality_mask_applied']);self.assertFalse(result['psf_applied']);self.assertEqual(old.read_bytes(),b'existing analysis product');self.assertEqual(json.loads(path.read_text()),source)
