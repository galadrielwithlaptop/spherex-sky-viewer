import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import network


class CurlTimeoutTests(unittest.TestCase):
    def test_float_metadata_timeout_produces_integer_retry_window(self):
        for timeout,retries,expected in [(12.0,0,'17'),(2.25,1,'10'),(45,1,'95')]:
            with self.subTest(timeout=timeout,retries=retries),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'response'
                def run(args,**kwargs):
                    self.assertEqual(args[args.index('--retry-max-time')+1],expected)
                    self.assertEqual(args[args.index('--max-time')+1],str(timeout))
                    path.write_bytes(b'ok')
                    return subprocess.CompletedProcess(args,0,'200','')
                with patch('network.subprocess.run',side_effect=run):
                    network.download('https://irsa.ipac.caltech.edu/test',path,timeout=timeout,retries=retries)


if __name__=='__main__':unittest.main()
