"""Display archive IMAGE pixels; leave existing analysis products untouched.

No archive downloads. Read only the IMAGE plane in cached native cutouts,
retain sky alignment for blinking, and use one display stretch per sequence.
No zodiacal subtraction, quality-flag masking, PSF/ePSF fitting or deconvolution.
"""
import argparse,json,os,time
from pathlib import Path
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from scipy.ndimage import map_coordinates
from imaging import png,PIXELS
from store import CACHE

PRODUCTS=CACHE/'products'
RAW=CACHE/'raw-display-arrays'
POLICY='Archive calibrated IMAGE; no ZODI subtraction, no quality-flag masking, no PSF/ePSF processing. Nearest-pixel sky alignment and common display stretch only.'

def image_plane(path,parameters):
    with fits.open(path,memmap=False,lazy_load_hdus=True) as hdus:
        h=hdus['IMAGE'];science=np.asarray(h.data,dtype=float)
        native=WCS(h.header,naxis=2)
        grid=WCS(naxis=2);grid.wcs.crpix=[(PIXELS+1)/2]*2;grid.wcs.crval=[parameters['ra'],parameters['dec']]
        grid.wcs.cdelt=[-parameters['fov']/60/PIXELS]*2;grid.wcs.ctype=['RA---TAN','DEC--TAN']
        y,x=np.indices((PIXELS,PIXELS));ra,dec=grid.all_pix2world(x,y,0);sx,sy=native.all_world2pix(ra,dec,0)
        return map_coordinates(science,np.array([sy,sx]),order=0,mode='constant',cval=np.nan)

def source_array(frame,parameters):
    RAW.mkdir(exist_ok=True);path=RAW/(frame['fits_key']+'.npz')
    if path.exists():
        path.touch()
        with np.load(path) as stored:return stored['image'].copy()
    native=CACHE/'images'/(frame['fits_key']+'.fits')
    if not native.exists():raise FileNotFoundError('Native archive IMAGE is no longer cached for '+frame['id'])
    files=sorted(RAW.glob('*.npz'),key=lambda p:p.stat().st_mtime);total=sum(p.stat().st_size for p in files)
    for old in files:
        if total<255*1024**2:break
        total-=old.stat().st_size;old.unlink()
    array=image_plane(native,parameters);temp=path.with_suffix('.tmp.npz');np.savez_compressed(temp,image=array);temp.replace(path)
    return array

def render(manifest_path):
    dest=manifest_path.parent/'raw';ready=dest/'manifest.json'
    if ready.exists() and json.loads(ready.read_text()).get('recipe_version')=='archive-image-display-v1':return
    m=json.loads(manifest_path.read_text());arrays=[source_array(f,m['parameters']) for f in m['frames']]
    valid=[a[np.isfinite(a)] for a in arrays];samples=np.concatenate(valid)
    if not samples.size:raise ValueError('No finite archive IMAGE pixels in this sequence')
    low,high=np.percentile(samples,[10,99.5]);dest.mkdir(exist_ok=True)
    frames=[]
    for i,(array,frame) in enumerate(zip(arrays,m['frames'])):
        temp=dest/f'{i}.tmp.png';png(array,low,high).save(temp);temp.replace(dest/f'{i}.png')
        frames.append({**frame,'mask_policy':'No quality-flag mask applied; finite and in-bounds archive IMAGE pixels only','processing':POLICY,'quality_mask_applied':False,'psf_applied':False,'zodi_subtracted':False,'image':f'/products/{manifest_path.parent.name}/raw/{i}.png','valid_fraction':float(np.isfinite(array).mean()),'source_url':frame['source_url'],'fits_key':frame['fits_key']})
    result={'recipe_version':'archive-image-display-v1','source':'archive_IMAGE','processing':POLICY,'psf_applied':False,'quality_mask_applied':False,'zodi_subtracted':False,'parameters':m['parameters'],'stretch':{'low':float(low),'high':float(high),'method':'common asinh','units':'MJy/sr'},'frames':frames}
    temp=dest/'manifest.tmp';temp.write_text(json.dumps(result),encoding='utf-8');temp.replace(ready)

def scan():
    failures=[]
    for path in PRODUCTS.glob('*/manifest.json'):
        try:render(path)
        except Exception as e:failures.append({'job':path.parent.name,'error':str(e)})
    status={'updated_unix':time.time(),'policy':POLICY,'errors':failures,'archive_downloads':0}
    temp=CACHE/'raw-preview-status.tmp';temp.write_text(json.dumps(status),encoding='utf-8');temp.replace(CACHE/'raw-preview-status.json')

def watch(server_url=None):
    lock=open(CACHE/'raw-preview-worker.lock','a+b')
    try:
        if os.name=='nt':
            import msvcrt
            lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (OSError,BlockingIOError):lock.close();return
    missing=0
    try:
        while True:
            scan()
            if server_url:
                import urllib.request
                try:
                    with urllib.request.urlopen(server_url+'/api/health',timeout=3) as response:response.read()
                    missing=0
                except Exception:missing+=1
                if missing>=3:return
            time.sleep(2)
    finally:lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true');parser.add_argument('--server-url');args=parser.parse_args()
    if args.watch:watch(args.server_url)
    else:scan()
