"""Read-only lookup of rendered IMAGE sequences already on this server."""
import json
from datetime import datetime,timezone


def find(products,params,detector='all',start=None,end=None):
    def boundary(value):
        return datetime.strptime(value,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()/86400+40587 if value else None
    low,high=boundary(start),boundary(end)
    candidates=[]
    for path in products.glob('*/manifest.json'):
        try:
            manifest=json.loads(path.read_text());field=manifest['parameters']
            if any(abs(float(field[k])-float(params[k]))>1e-7 for k in ('ra','dec','fov')):continue
            raw_path=path.parent/'raw/manifest.json'
            raw=json.loads(raw_path.read_text())
            raw_ids={f['id'] for f in raw['frames']}
            usable=[]
            for frame in manifest['frames']:
                if frame['id'] not in raw_ids:continue
                if detector!='all' and frame['detector']!=detector:continue
                if low is not None and frame['mjd']<low:continue
                if high is not None and frame['mjd']>=high+1:continue
                item=next(f for f in raw['frames'] if f['id']==frame['id'])
                relative=item['image'].removeprefix('/products/')
                image=(products/relative).resolve()
                if not image.is_relative_to(products.resolve()) or not image.is_file():continue
                usable.append(frame)
            if usable:
                if len(usable)!=len(manifest['frames']):manifest={**manifest,'frames':usable,'groups':[]}
                candidates.append((len(usable),path.stat().st_mtime,path.parent.name,manifest))
        except (ValueError,KeyError,OSError,TypeError):continue
    if not candidates:return {'job_id':None,'cached_frames':0,'archive_requests':0,'pixel_downloads':0}
    count,_,key,manifest=max(candidates,key=lambda item:item[:3])
    return {'job_id':key,'manifest':manifest,'cached_frames':count,'archive_requests':0,'pixel_downloads':0,
            'notice':'Prepared server-local IMAGE frames; this is not a complete archive selection.'}
