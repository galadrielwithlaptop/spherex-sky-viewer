"""Publish cached starter IMAGE cutouts as main-viewer sequences; no network I/O."""
import hashlib
import json
from urllib.parse import urlencode
import numpy as np
from store import CACHE
from raw_previews import image_plane, POLICY
from imaging import png,compatible
from store import exposure


def main():
    report = CACHE/'starter-5arcmin.json'
    data = json.loads(report.read_text())
    for target in data['targets']:
        ready = [r for r in target['results'] if r['state']=='ready']
        if not ready:
            continue
        key = hashlib.sha256(('starter-sequence-v1:'+json.dumps([target['ra'],target['dec'],[r['id'] for r in ready]])).encode()).hexdigest()[:24]
        params = {'ra':target['ra'],'dec':target['dec'],'fov':5}
        dest = CACHE/'products'/key
        raw = dest/'raw'
        raw.mkdir(parents=True,exist_ok=True)
        arrays, frames = [], []
        for result in ready:
            source = CACHE/'products'/result['product_id']
            arrays.append(image_plane(source/'native-image.fits',params))
            frame = json.loads((source/'manifest.json').read_text())['frames'][0]
            metadata=exposure(frame['id'])
            frame.update(target_position_icrs_deg=[params['ra'],params['dec']],
                         exposure_seconds=float(metadata['t_exptime']) if metadata.get('t_exptime') else None,
                         archive_footprint=metadata.get('s_region'),
                         quality_status='Quality flags not loaded for this IMAGE-only preview; artifacts may be visible')
            frame['cutout_sha256']=hashlib.sha256((source/'native-image.fits').read_bytes()).hexdigest()
            frame['native_fits'] = result['native_fits']
            # Use archive detector identifiers expected by the viewer filters.
            frame['detector'] = 'SPHEREx-'+frame['detector']
            frames.append(frame)
        ordered = sorted(range(len(frames)),key=lambda i:frames[i]['mjd'])
        arrays = [arrays[i] for i in ordered]
        frames = [frames[i] for i in ordered]
        values = np.concatenate([a[np.isfinite(a)] for a in arrays])
        low,high = np.percentile(values,[10,99.5])
        for i,(array,frame) in enumerate(zip(arrays,frames)):
            image = png(array,low,high)
            image.save(raw/f'{i}.png')
            image.save(dest/f'{i}.png')
            frame.update(index=i,image=f'/products/{key}/raw/{i}.png')
        groups=[]
        for i,frame in enumerate(frames):
            if frame.get('wavelength_reference')!='target':continue
            group=next((g for g in groups if all(compatible(frame,frames[j]) for j in g)),None)
            if group is None:groups.append([i])
            else:group.append(i)
        manifest = {'recipe_version':'archive-image-display-v1','source':'archive_IMAGE',
                    'frames':frames,'groups':[{'indices':g,'wavelength_um':sum(frames[i]['wavelength_um'] for i in g)/len(g),'coadd':None,'difference':None,'animation':None,'metadata_only_group':True} for g in groups], 'parameters':params,'errors':[],
                    'processing':POLICY,'psf_applied':False,'zodi_subtracted':False,
                    'quality_mask_applied':False,'stretch':{'low':float(low),'high':float(high),'method':'common asinh','units':'MJy/sr'},
                    'warnings':['Each frame reports whether its target-position wavelength was measured. Mixed wavelengths and detector artifacts can mimic brightness change.']}
        payload=json.dumps(manifest)
        (raw/'manifest.json').write_text(payload,encoding='utf-8')
        (dest/'manifest.json').write_text(payload,encoding='utf-8')
        target['viewer_url']='/?'+urlencode({**params,'job':key})
        target['sequence_id']=key
    payload=json.dumps(data,indent=2)
    report.write_text(payload,encoding='utf-8')
    published=CACHE/'products/starter/index.json'
    temp=published.with_suffix('.tmp')
    temp.write_text(payload,encoding='utf-8')
    temp.replace(published)
    print('Published',sum('viewer_url' in t for t in data['targets']),'cached starter sequences')


if __name__=='__main__':
    main()
