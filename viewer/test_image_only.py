"""IMAGE-only extraction must work without analysis extensions."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from remote_fits import extract
from imaging import wavelength_probe


class ImageOnlyTests(unittest.TestCase):
    def test_local_wavelength_cache_needs_no_archive_request(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'local-import').mkdir()
            (root/'local-import/wavelengths.json').write_text(json.dumps({'abc':{'ra':133.0,'dec':-7.0,'wavelength_um':3.1,'bandwidth_um':0.06}}))
            row={'id':'abc','energy_bandpassname':'SPHEREx-D4','obs_collection':'spherex_dr1'}
            with patch('imaging.CACHE',root),patch('remote_fits.RemoteFile',side_effect=AssertionError('Must use local wavelength metadata')):
                result=wavelength_probe(row,133.0,-7.0)
                self.assertEqual(result['wavelength_um'],3.1);self.assertEqual(result['bandwidth_um'],0.06)
    def test_image_only_needs_no_zodi_flags_variance_or_wave(self):
        wcs = WCS(naxis=2)
        wcs.wcs.crpix = [50, 50]
        wcs.wcs.crval = [133.7951291667, -7.2451472222]
        wcs.wcs.cdelt = [-6.15/3600, 6.15/3600]
        wcs.wcs.ctype = ['RA---TAN', 'DEC--TAN']
        pixels = np.full((100,100), 42, dtype=np.float32)
        stream = io.BytesIO()
        fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(pixels,header=wcs.to_header(),name='IMAGE')]).writeto(stream)
        stream.seek(0)
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)/'image.fits'
            with patch('remote_fits.RemoteFile', return_value=stream):
                extract('https://example.invalid/image.fits',133.7951291667,-7.2451472222,5,dest,image_only=True)
            with fits.open(dest) as result:
                self.assertEqual([h.name for h in result], ['PRIMARY','IMAGE'])
                self.assertTrue(np.all(result['IMAGE'].data == 42))


if __name__ == '__main__':
    unittest.main()
