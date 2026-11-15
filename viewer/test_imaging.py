"""Synthetic numerical fixtures only. Never displayed as observations."""
import io, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from remote_fits import extract
from imaging import target_wavelength, png

class ExtractionTests(unittest.TestCase):
    def test_difference_zero_is_middle_gray_and_missing_pixels_stay_distinct(self):
        out=np.asarray(png(np.array([[-1.,0.,1.,np.nan]]),-1,1,symmetric=True))
        self.assertEqual(int(out[0,0,0]),0)
        self.assertIn(int(out[0,1,0]),(127,128))
        self.assertEqual(int(out[0,2,0]),255)
        np.testing.assert_array_equal(out[0,3],[21,36,49])
    def test_compressed_flags_and_wcs_survive_cutout(self):
        n=100; w=WCS(naxis=2);w.wcs.crpix=[50,50];w.wcs.crval=[133,-7];w.wcs.cdelt=[-.0017,.0017];w.wcs.ctype=['RA---TAN','DEC--TAN']
        header=w.to_header();a=np.arange(n*n,dtype=np.float32).reshape(n,n)
        flags=np.zeros((n,n),dtype=np.int32);flags[48:52,48:52]=2097152;flags[40:43,40:43]=64
        cols=[fits.Column(name='X',format='2J',array=[[1,n]]),fits.Column(name='Y',format='2J',array=[[1,n]]),fits.Column(name='VALUES',format='8E',dim='(2,2,2)',array=[np.array([[[1.,.1],[2.,.1]],[[1.,.1],[2.,.1]]])])]
        h=fits.HDUList([fits.PrimaryHDU(),fits.ImageHDU(a,header=header,name='IMAGE'),fits.CompImageHDU(flags,header=header,name='FLAGS'),fits.ImageHDU(np.ones_like(a),header=header,name='VARIANCE'),fits.ImageHDU(np.zeros_like(a),header=header,name='ZODI'),fits.BinTableHDU.from_columns(cols,name='WCS-WAVE')]);buffer=io.BytesIO();h.writeto(buffer);raw=buffer.getvalue()
        def download(url,path,max_bytes,byte_range):
            start,end=byte_range;Path(path).write_bytes(raw[start:end+1])
        class Head:
            returncode=0;stdout=f'Content-Length: {len(raw)}\r\n'
        with tempfile.TemporaryDirectory() as d,patch('remote_fits.subprocess.run',return_value=Head()),patch('remote_fits.download',side_effect=download):
            path=Path(d)/'cutout.fits';extract('https://irsa.ipac.caltech.edu/test',133,-7,1,path)
            with fits.open(path) as out:
                x0,y0=out['IMAGE'].header['ORIGX0'],out['IMAGE'].header['ORIGY0'];ny,nx=out['IMAGE'].data.shape
                np.testing.assert_array_equal(out['IMAGE'].data,a[y0:y0+ny,x0:x0+nx])
                np.testing.assert_array_equal(out['FLAGS'].data,flags[y0:y0+ny,x0:x0+nx])
                cw=WCS(out['IMAGE'].header);x,y=cw.all_world2pix(133,-7,0)
                np.testing.assert_allclose([x+x0,y+y0],w.all_world2pix(133,-7,0),atol=1e-9)
                wave,width=target_wavelength(out,x,y)
                self.assertAlmostEqual(wave,1+49/99,places=6);self.assertAlmostEqual(width,.1,places=6)

if __name__=='__main__':unittest.main()
