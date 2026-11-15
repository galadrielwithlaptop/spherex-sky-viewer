"""Small 5' archive-IMAGE-only starter batch. Run on the hosting VM.

Does not invoke the analysis, ePSF, ZODI, coadd or difference pipelines.
Default plan is metadata-only; --execute retrieves the requested sample and retains ready frames.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def sample(rows, count):
    if len(rows) <= count:
        return rows
    return [rows[round(i * (len(rows)-1)/(count-1))] for i in range(count)] if count > 1 else rows[:1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--cache-only', action='store_true')
    parser.add_argument('--base-url', default='http://127.0.0.1:8765')
    parser.add_argument('--per-target', type=int, choices=range(1, 25), default=3)
    parser.add_argument('--minutes', type=int, choices=range(1, 56), default=45)
    args = parser.parse_args()
    from store import CACHE
    from remote_fits import extract
    from raw_previews import image_plane, POLICY
    from imaging import png
    from astropy.time import Time
    import numpy as np

    def get(path):
        with urlopen(args.base_url.rstrip('/')+path, timeout=45) as response:
            return json.load(response)

    started = time.monotonic()
    deadline = started + args.minutes*60
    report = {'diameter_arcmin': 5, 'processing': POLICY, 'targets': [], 'deadline_minutes': args.minutes}
    output = CACHE/'starter-5arcmin.json'
    previous=json.loads(output.read_text()) if output.exists() else {'targets':[]}
    previous_targets={t['name']:t for t in previous['targets']}
    def save():
        report['elapsed_seconds'] = round(time.monotonic()-started, 2)
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')
        published = CACHE/'products'/'starter'
        published.mkdir(parents=True, exist_ok=True)
        temporary = published/'index.tmp'
        temporary.write_text(json.dumps(report), encoding='utf-8')
        temporary.replace(published/'index.json')

    targets = get('/api/v1/targets')['targets']
    # Plan every target first; execute round-robin so one field cannot monopolize the batch.
    for target in targets:
        if time.monotonic() >= deadline:
            break
        entry = dict(name=target['name'], ra=target['ra'], dec=target['dec'], selected=[], results=[])
        report['targets'].append(entry)
        try:
            q = dict(ra=target['ra'], dec=target['dec'], fov_arcmin=5, limit=500,
                     mode='cache_only' if args.cache_only else 'auto', sort='asc')
            rows = []
            while True:
                page = get('/api/v1/observations?'+urlencode(q))
                rows.extend(page['observations'])
                entry['coverage'] = page['coverage']
                if not page['pagination']['next_cursor']:
                    break
                q['cursor'] = page['pagination']['next_cursor']
            entry['indexed_matches'] = len(rows)
            old=previous_targets.get(target['name'],{})
            selected=sample(rows,args.per_target)
            kept=[r for r in old.get('results',[]) if r.get('state')=='ready']
            prior={r['id']:r for r in old.get('selected',[])}
            merged={r['id']:r for r in selected}
            for result in kept:
                if result['id'] in prior:merged.setdefault(result['id'],prior[result['id']])
            entry['selected']=sorted(merged.values(),key=lambda r:r['time_start_mjd'])
            entry['results']=[r for r in kept if r['id'] in merged]
            if old.get('sequence_id'):entry.update(sequence_id=old['sequence_id'],viewer_url=old['viewer_url'])
        except Exception as exc:
            entry['error'] = str(exc)
        save()
    if args.execute:
        for slot in range(max((len(t['selected']) for t in report['targets']),default=0)):
            for entry in report['targets']:
                if slot >= len(entry['selected']):
                    continue
                # Allow a reserve for a bounded current HTTP request to finish.
                if time.monotonic()+120 >= deadline:
                    report['stopped_reason'] = 'Time budget reserve reached; remaining observations deferred'
                    save()
                    return
                row = entry['selected'][slot]
                if any(r['id']==row['id'] and r['state']=='ready' for r in entry['results']):continue
                result = {'id': row['id'], 'state': 'loading'}
                entry['results'].append(result)
                save()
                try:
                    params = dict(ra=entry['ra'], dec=entry['dec'], fov=5)
                    key = hashlib.sha256(('starter-image-only-v1:'+json.dumps([row['id'],params],sort_keys=True)).encode()).hexdigest()[:24]
                    dest = CACHE/'products'/key
                    dest.mkdir(parents=True, exist_ok=True)
                    native = dest/'native-image.fits'
                    if not native.exists():
                        temp = dest/'native-image.part'
                        try:
                            extract(row['source_url'], **params, path=temp, image_only=True)
                            temp.replace(native)
                        finally:
                            temp.unlink(missing_ok=True)
                    array = image_plane(native, params)
                    values = array[np.isfinite(array)]
                    if not values.size:
                        raise ValueError('No finite IMAGE pixels in requested field')
                    low, high = np.percentile(values, [10,99.5])
                    raw = dest/'raw'
                    raw.mkdir(exist_ok=True)
                    png(array, low, high).save(raw/'0.png')
                    frame = {'id':row['id'], 'observation':row['observation_id'],
                             'detector':'D'+str(row['detector']), 'collection':row['collection'],
                             'mjd':row['time_start_mjd'], 'utc':row['time_start_utc'],
                             'source_url':row['source_url'], 'processing':POLICY,
                             'psf_applied':False,'zodi_subtracted':False,'quality_mask_applied':False,
                             'image':f'/products/{key}/raw/0.png', 'index':0,
                             'valid_fraction':float(np.isfinite(array).mean()),
                             'wavelength_um':sum(row['wavelength_bounds_um'])/2,
                             'wavelength_reference':'Detector-wide midpoint only; target wavelength not inspected',
                             'wavelength_bounds_um':row['wavelength_bounds_um']}
                    manifest = {'recipe_version':'archive-image-display-v1', 'source':'archive_IMAGE',
                                'parameters':params,'frames':[frame],'groups':[], 'errors':[],
                                'psf_applied':False,'zodi_subtracted':False,'quality_mask_applied':False,
                                'processing':POLICY,'stretch':{'low':float(low),'high':float(high),'method':'asinh'},
                                'warnings':['Single starter frame; different wavelengths are not a brightness-change measurement.']}
                    (raw/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
                    # Separate starter products never overwrite existing analysis sequences.
                    (dest/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
                    result.update(state='ready', product_id=key, image=frame['image'],
                                  native_fits=f'/products/{key}/native-image.fits')
                except Exception as exc:
                    result.update(state='failed',error=str(exc))
                print(entry['name'], result['state'], flush=True)
                save()
                if result['state']=='ready':
                    from publish_starter_sequences import main as publish
                    publish()
                    published=json.loads(output.read_text())
                    for current,updated in zip(report['targets'],published['targets']):
                        for key in ('viewer_url','sequence_id'):
                            if key in updated:current[key]=updated[key]
    report['state'] = 'finished' if args.execute else 'planned'
    save()
    print(output, flush=True)


if __name__ == '__main__':
    main()
