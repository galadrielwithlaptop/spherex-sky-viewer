"""Explain every locally indexed overlapping record without retrieving archive data."""
import json
from collections import Counter
from archive import COLLECTIONS,query_url
from store import spatial_rows,coverage,CACHE
from imaging import wavelength_probe

def audit(ra,dec,fov):
    query_url(ra,dec,fov,COLLECTIONS[0])
    rows=spatial_rows(ra,dec,fov/120,COLLECTIONS)['rows']
    prepared={}
    for path in (CACHE/'products').glob('*/manifest.json'):
        try:
            m=json.loads(path.read_text());p=m['parameters']
            if any(abs(float(p[k])-v)>1e-9 for k,v in [('ra',ra),('dec',dec),('fov',fov)]):continue
            for frame in m['frames']:prepared[frame['id']]={'job':path.parent.name,'image':frame['image'],'valid_fraction':frame['valid_fraction'],'wavelength_um':frame['wavelength_um'],'bandwidth_um':frame['bandwidth_um'],'wavelength_reference':frame.get('wavelength_reference','target')}
        except (ValueError,KeyError,OSError):continue
    output=[]
    for row in sorted(rows,key=lambda r:(float(r['t_min']),r['id'])):
        item=dict(source_record=row,id=row['id'],observation=row['obs_id'],collection=row['obs_collection'],detector=row['energy_bandpassname'],mjd=float(row['t_min']),source_url=row['access_url'],footprint=row.get('s_region'),status='not_attempted',reason='Metadata overlap; image has not been prepared for this field',target_wavelength_um=None,centre_status='not_checked')
        try:
            probe=wavelength_probe(row,ra,dec,cached_only=True)
            item.update(target_wavelength_um=probe['wavelength_um'],bandwidth_um=probe['bandwidth_um'],centre_status='inside_native_image')
        except FileNotFoundError:pass
        except ValueError as e:item.update(centre_status='outside_or_unavailable',reason='Partial-field candidate: '+str(e)+'. Still available to request as a cutout.')
        if row['id'] in prepared:
            ready=prepared[row['id']];item.update(status='prepared',reason='Real field cutout prepared',prepared=ready)
            if ready['wavelength_reference']=='target':item.update(target_wavelength_um=ready['wavelength_um'],bandwidth_um=ready['bandwidth_um'],centre_status='inside_native_image')
        output.append(item)
    states=[dict(coverage(ra,dec,fov/120,c),collection=c) for c in COLLECTIONS]
    return dict(records=output,total=len(output),counts=dict(Counter(r['status'] for r in output)),coverage=states,metadata_scope='Currently indexed overlapping DR1/QR3 wide-survey records, not a complete all-sky index',pixel_downloads=0,header_downloads=0)
