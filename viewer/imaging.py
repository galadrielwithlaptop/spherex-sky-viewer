"""Exploratory fixed-sky rendering; not calibrated variability photometry."""
import hashlib, json, threading, time
from pathlib import Path
from urllib.parse import urlencode
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from scipy.ndimage import map_coordinates
from scipy.interpolate import RegularGridInterpolator
from PIL import Image, ImageDraw
from network import download
from remote_fits import extract
from store import CACHE, exposure

LOCK=threading.Lock()
LIMIT=256*1024*1024
PIXELS=256

def wavelength_probe(row,ra,dec,cached_only=False):
    """Persist native WCS and wavelength grids without retrieving science pixels."""
    local=CACHE/'local-import/wavelengths.json'
    if local.exists():
        record=json.loads(local.read_text()).get(row['id'])
        if record and abs(record['ra']-ra)<1e-7 and abs(record['dec']-dec)<1e-7:
            return {'wavelength_um':record['wavelength_um'],'bandwidth_um':record['bandwidth_um'],
                    'detector':row['energy_bandpassname'],'collection':row['obs_collection'],
                    'provenance':'Target-position wavelength from previously cached native cutout on the project laptop'}
    from remote_fits import RemoteFile
    directory=CACHE/'headers';directory.mkdir(exist_ok=True)
    key=hashlib.sha256(row['access_url'].encode()).hexdigest()[:24]
    path=directory/(key+'.json')
    if path.exists():record=json.loads(path.read_text())
    else:
        if cached_only:raise FileNotFoundError('Target wavelength header is not cached')
        with fits.open(RemoteFile(row['access_url']),memmap=False,lazy_load_hdus=True) as hdus:
            wave=hdus['WCS-WAVE'].data[0]
            record={'header':hdus['IMAGE'].header.tostring(),'x':wave['X'].tolist(),'y':wave['Y'].tolist(),'values':wave['VALUES'].tolist()}
        path.write_text(json.dumps(record))
    header=fits.Header.fromstring(record['header'])
    x,y=WCS(header,naxis=2).all_world2pix(ra,dec,0)
    if not (0<=x<header['NAXIS1'] and 0<=y<header['NAXIS2']):raise ValueError('Target is outside the native detector footprint')
    result=RegularGridInterpolator((record['y'],record['x']),np.asarray(record['values']),bounds_error=False,fill_value=np.nan)([[y+1,x+1]])[0]
    if not np.isfinite(result).all():raise ValueError('Target wavelength unavailable')
    return {'wavelength_um':float(result[0]),'bandwidth_um':float(result[1]),'detector':row['energy_bandpassname'],'collection':row['obs_collection']}

def compatible(a,b):
    if a.get('wavelength_reference','target')!='target' or b.get('wavelength_reference','target')!='target':return False
    return a['detector']==b['detector'] and a['collection']==b['collection'] and abs(a['wavelength_um']-b['wavelength_um'])<=.25*min(a['bandwidth_um'],b['bandwidth_um']) and abs(a['bandwidth_um']/b['bandwidth_um']-1)<=.1

def trim_cache():
    files=sorted([p for p in (CACHE/'images').glob('*') if p.is_file()],key=lambda p:p.stat().st_mtime)
    total=sum(p.stat().st_size for p in files)
    for p in files:
        if total<LIMIT-32*1024*1024: break
        total-=p.stat().st_size; p.unlink()

def target_wavelength(hdus,x,y):
    h=hdus['WCS-WAVE']; data=h.data[0]
    gx=np.asarray(data['X']).reshape(-1); gy=np.asarray(data['Y']).reshape(-1)
    vals=np.asarray(data['VALUES'])
    # FITS TDIM translates into NumPy axis order (y,x,component).
    if vals.shape == (len(gy),len(gx),2): pass
    elif vals.shape == (2,len(gy),len(gx)): vals=np.moveaxis(vals,0,-1)
    else: raise ValueError(f'Unsupported wavelength grid shape: {vals.shape}')
    # WCS-WAVE control points are FITS 1-based native pixel coordinates.
    header=hdus['IMAGE'].header
    px=x+header.get('ORIGX0',0)+1; py=y+header.get('ORIGY0',0)+1
    value=RegularGridInterpolator((gy,gx),vals,bounds_error=False,fill_value=np.nan)([[py,px]])[0]
    if not np.isfinite(value).all(): raise ValueError('Target outside wavelength grid')
    return float(value[0]),float(value[1])

def frame(row,ra,dec,fov):
    key=hashlib.sha256(f"range-v3:{row['access_url']}:{ra}:{dec}:{fov}".encode()).hexdigest()[:24]
    directory=CACHE/'images'; directory.mkdir(exist_ok=True)
    path=directory/(key+'.fits')
    with LOCK:
        if not path.exists():
            trim_cache()
            tmp=directory/(key+'.part')
            try:
                # Byte-range extraction avoids the currently failing cutout worker.
                extract(row['access_url'],ra,dec,fov,tmp)
                tmp.replace(path)
            finally: tmp.unlink(missing_ok=True)
        else: path.touch()
    with fits.open(path,memmap=False) as hdus:
        sci=np.asarray(hdus['IMAGE'].data,dtype=float)
        var=np.asarray(hdus['VARIANCE'].data,dtype=float)
        flags=np.asarray(hdus['FLAGS'].data,dtype=np.uint64)
        zodi=np.asarray(hdus['ZODI'].data,dtype=float)
        native=WCS(hdus['IMAGE'].header,naxis=2)
        x,y=native.all_world2pix(ra,dec,0)
        wavelength_reference='target'
        try:
            if not (0<=x<sci.shape[1] and 0<=y<sci.shape[0]):raise ValueError("Target outside native cutout")
            wave,width=target_wavelength(hdus,x,y)
        except ValueError:
            wave,width=target_wavelength(hdus,(sci.shape[1]-1)/2,(sci.shape[0]-1)/2)
            wavelength_reference='cutout centre; target outside wavelength grid'
        # Do not remove SOURCE pixels: these flag real astronomical objects.
        fh=hdus['FLAGS'].header; informational=0
        for k in fh:
            if k.startswith('MSKN') and fh[k].strip() in ('SOURCE','FULLSAMPLE'):
                informational |= int(fh.get('MSKM'+k[4:],0))
        bad=flags & np.uint64(0xffffffffffffffff ^ informational)
        valid=np.isfinite(sci)&np.isfinite(zodi)&np.isfinite(var)&(var>0)&(bad==0)
        grid=WCS(naxis=2);grid.wcs.crpix=[(PIXELS+1)/2]*2
        # PNG row zero is the top: decreasing Dec with row gives north up.
        grid.wcs.crval=[ra,dec];grid.wcs.cdelt=[-fov/60/PIXELS,-fov/60/PIXELS]
        grid.wcs.ctype=['RA---TAN','DEC--TAN']
        yy,xx=np.indices((PIXELS,PIXELS));lon,lat=grid.all_pix2world(xx,yy,0)
        sx,sy=native.all_world2pix(lon,lat,0)
        # Nearest native pixel: does not invent interpolated signal across masks.
        coords=np.array([sy,sx]); mask=map_coordinates(valid.astype(float),coords,order=0,mode='constant',cval=0)>.5
        arr=map_coordinates(np.where(valid,sci-zodi,0),coords,order=0,mode='constant',cval=0)
        arr[~mask]=np.nan
        if not mask.any(): raise ValueError('No unflagged pixels overlap this requested field')
        return arr,{'id':row['id'],'observation':row['obs_id'],'detector':row['energy_bandpassname'],'collection':row['obs_collection'],'mjd':float(row['t_min']),'utc':Time(float(row['t_min']),format='mjd').isot+'Z','wavelength_um':wave,'bandwidth_um':width,'wavelength_reference':wavelength_reference,'valid_fraction':float(mask.mean()),'native_flagged_fraction':float((bad!=0).mean()),'flag_counts':{fh[k].strip():int(np.sum((flags&int(fh.get('MSKM'+k[4:],0)))!=0)) for k in fh if k.startswith('MSKN')},'cutout_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_url':row['access_url'],'fits_key':key,'mask_policy':'all flags except informational SOURCE/FULLSAMPLE excluded; finite IMAGE/ZODI and positive VARIANCE','processing':'IMAGE − ZODI; nearest-pixel WCS projection; north up / east left; no PSF homogenization'}

def png(array,low,high,symmetric=False):
    mask=np.isfinite(array)
    scaled=np.clip((np.nan_to_num(array,nan=low)-low)/max(high-low,1e-9),0,1)
    if not symmetric:scaled=np.arcsinh(scaled*10)/np.arcsinh(10)
    rgb=np.repeat((scaled*255).astype('uint8')[...,None],3,axis=2)
    rgb[~mask]=[21,36,49]
    return Image.fromarray(rgb)

def build(job,rows,params,dest,match=False,mosaic=False,loader=None):
    dest.mkdir(exist_ok=True)
    arrays=[];metadata=[];errors=[]
    planning=None
    planning={'requested_records':len(rows),'method':'All explicitly selected records are attempted; wavelength groups organize comparisons without discarding other records.'}
    for i,row in enumerate(rows):
        job.update(progress=f'Reading frame {i+1}/{len(rows)}',done=i)
        try:
            a,m=(loader or frame)(row,**params);arrays.append(a);metadata.append(m)
        except Exception as e: errors.append({'id':row['id'],'reason':str(e)})
        job['errors']=errors
    if not arrays: raise ValueError('No usable frames. See per-observation failures.')
    # Select a narrow wavelength group at the target, never treat D1–D6 as six fixed bands.
    groups=[]
    for i,m in enumerate(metadata):
        group=next((g for g in groups if all(compatible(m,metadata[j]) for j in g)),None)
        if group is None: groups.append([i])
        else: group.append(i)
    samples=np.concatenate([a[np.isfinite(a)] for a in arrays])
    low,high=np.percentile(samples,[10,99.5]); images=[]
    for i,(a,m) in enumerate(zip(arrays,metadata)):
        image=png(a,low,high);image.save(dest/f'{i}.png');images.append(image)
        m['image']=f'/products/{dest.name}/{i}.png';m['index']=i
    np.savez_compressed(dest/'aligned.npz',**{str(i):a for i,a in enumerate(arrays)})
    for n,g in enumerate(groups):
        selected=np.array([arrays[i] for i in g]); counts=np.sum(np.isfinite(selected),axis=0)
        coadd=np.divide(np.nansum(selected,axis=0),counts,out=np.full(counts.shape,np.nan),where=counts>0)
        png(coadd,low,high).save(dest/f'coadd-{n}.png')
        if len(g)>1:
            delta=arrays[g[-1]]-arrays[g[0]]; d=np.nanpercentile(np.abs(delta),99) if np.isfinite(delta).any() else 1
            # Symmetric difference stretch, zero gray, common valid footprint only.
            png(delta,-max(d,1e-6),max(d,1e-6),symmetric=True).save(dest/f'difference-{n}.png')
            labels=[]
            for i in g:
                im=images[i].resize((512,512),Image.Resampling.NEAREST); draw=ImageDraw.Draw(im);draw.rectangle((0,0,512,24),fill='black');draw.text((8,6),metadata[i]['utc'],fill='white');labels.append(im)
            labels[0].save(dest/f'blink-{n}.gif',save_all=True,append_images=labels[1:],duration=700,loop=0)
    manifest={'frames':metadata,'groups':[{'indices':g,'wavelength_um':metadata[g[0]]['wavelength_um'],'coadd':f'/products/{dest.name}/coadd-{n}.png','difference':f'/products/{dest.name}/difference-{n}.png' if len(g)>1 else None,'animation':f'/products/{dest.name}/blink-{n}.gif' if len(g)>1 else None} for n,g in enumerate(groups)],'errors':errors,'planning':planning,'recipe_version':'4-wavelength-planned','parameters':params,'render_grid':{'projection':'TAN','size':PIXELS,'crpix_fits':[(PIXELS+1)/2]*2,'crval_deg':[params['ra'],params['dec']],'cdelt_deg':[-params['fov']/60/PIXELS]*2},'stretch':{'low':float(low),'high':float(high),'units':'MJy/sr','method':'common asinh'},'warnings':['Exploratory imagery, not a variability detection.','Wavelength lookup is visualization precision; matching centres/widths does not establish identical response.','No PSF matching or astrometric validation. Differences can be instrumental.','Coadds are unweighted means of available frames; no propagated uncertainty.','Conservative masks may remove usable pixels. Proper motion is not propagated.']}
    if mosaic:
        stack=np.asarray(arrays);counts=np.isfinite(stack).sum(axis=0)
        combined=np.divide(np.nansum(stack,axis=0),counts,out=np.full(counts.shape,np.nan),where=counts>0)
        png(combined,low,high).save(dest/'mosaic.png')
        np.savez_compressed(dest/'mosaic-coverage.npz',contributors=counts)
        manifest['mosaic']={'image':f'/products/{dest.name}/mosaic.png','coverage':f'/products/{dest.name}/mosaic-coverage.npz','source_ids':[m['id'] for m in metadata],'valid_fraction':float((counts>0).mean()),'method':'Common sky grid; unweighted mean of valid overlapping samples. Gaps remain missing.','warning':'Exploratory spatial mosaic. Contributors can have different epochs and position-dependent wavelengths; not a single-epoch or monochromatic measurement.'}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2))
    job.update(state='complete',manifest=manifest,progress=f'{len(arrays)} real frames ready')
