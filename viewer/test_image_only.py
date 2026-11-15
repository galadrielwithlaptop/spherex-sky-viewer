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


class ImageOnlyTests(unittest.TestCase):
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
