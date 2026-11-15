"""System-trusted HTTPS transport. No certificate-validation bypass."""
import os, subprocess, shutil, math
from pathlib import Path
from urllib.parse import urlsplit
CURL=shutil.which('curl.exe') or shutil.which('curl') or 'curl'

def download(url, path, max_bytes=24*1024*1024, byte_range=None,timeout=45,retries=1):
    u = urlsplit(url)
    if u.scheme != 'https' or u.hostname not in ('irsa.ipac.caltech.edu','cds.unistra.fr'):
        raise ValueError('Unapproved archive host')
    # curl permits fractional --max-time, but --retry-max-time requires an integer.
    retry_window=math.ceil((retries+1)*timeout+5)
    args=[CURL,'--fail','--silent','--show-error','--location','--proto','=https','--proto-redir','=https','--max-time',str(timeout),'--retry',str(retries),'--retry-all-errors','--retry-delay','1','--retry-max-time',str(retry_window),'--max-filesize',str(max_bytes),'--output',str(path),'--write-out','%{http_code}']
    if byte_range is not None: args += ['--range',f'{byte_range[0]}-{byte_range[1]}']
    p = subprocess.run(args+[url],capture_output=True,text=True,timeout=(retries+1)*(timeout+2)+10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if p.returncode:
        Path(path).unlink(missing_ok=True)
        raise RuntimeError('Archive request failed: '+p.stderr.strip()[:240])
    if Path(path).stat().st_size > max_bytes:
        Path(path).unlink(missing_ok=True)
        raise RuntimeError('Archive response exceeded download limit')
    if byte_range is not None and p.stdout.strip() != '206':
        Path(path).unlink(missing_ok=True)
        raise RuntimeError('Archive did not honor byte-range request')

def text(url):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'response'
        timeout=max(2,min(30,float(os.environ.get('SPHEREX_METADATA_TIMEOUT','12'))))
        download(url,p,12*1024*1024,timeout=timeout,retries=0)
        return p.read_text(encoding='utf-8-sig')
