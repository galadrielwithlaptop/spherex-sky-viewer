"""Plan all five 5-arcminute fields; --execute explicitly starts cutout jobs.

Run on the VM beside the viewer. Uses the public API, not local cache internals.
"""
import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8765')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--cache-only', action='store_true')
    parser.add_argument('--report', default='five-targets-5arcmin.json')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    if urlsplit(base).scheme not in ('http', 'https'):
        parser.error('base-url must use HTTP or HTTPS')
    report_path = Path(args.report)
    report = {'diameter_arcmin': 5, 'execution_requested': args.execute, 'targets': []}

    def save():
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def api(path, body=None):
        req = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={'Content-Type': 'application/json'})
        with urlopen(req, timeout=90) as response:
            return json.load(response)

    targets = api('/api/v1/targets')['targets']
    for target in targets:
        entry = {'name': target['name'], 'ra': target['ra'], 'dec': target['dec']}
        report['targets'].append(entry)
        try:
            params = {'ra': target['ra'], 'dec': target['dec'], 'fov_arcmin': 5,
                      'limit': 500, 'sort': 'asc', 'mode': 'cache_only' if args.cache_only else 'auto'}
            ids = []
            while True:
                page = api('/api/v1/observations?' + urlencode(params))
                ids.extend(row['id'] for row in page['observations'])
                entry['coverage'] = page['coverage']
                cursor = page['pagination']['next_cursor']
                if not cursor:
                    break
                params['cursor'] = cursor
            ids = list(dict.fromkeys(ids))
            entry.update(observation_ids=ids, indexed_matches=len(ids), state='planned')
            print(f"{target['name']}: {len(ids)} indexed matches; diameter 5 arcmin", flush=True)
            save()
            if not args.execute:
                continue
            if not entry['coverage']['complete_for_requested_collections']:
                raise RuntimeError('Coverage incomplete; refusing to label a partial selection as all observations')
            if not ids:
                entry['state'] = 'no_observations'
                save()
                continue
            if len(ids) > 500:
                raise RuntimeError('Field exceeds the current 500-record job limit; no records silently omitted')
            state = api('/api/v1/field-downloads', {'ra': target['ra'], 'dec': target['dec'],
                        'fov_arcmin': 5, 'observation_ids': ids})
            entry['job_id'] = state['id']
            while True:
                entry.update(state=state['state'], counts=state.get('counts'),
                             sequence_id=state.get('sequence_id'), records=state.get('records', []))
                save()
                if state['state'] not in ('queued', 'running'):
                    break
                time.sleep(5)
                state = api('/api/v1/field-downloads/' + state['id'])
            if state['state'] not in ('complete', 'complete_with_failures'):
                raise RuntimeError('Field stopped: ' + state.get('error', state['state']))
        except Exception as exc:
            entry.update(state='error', error=str(exc))
            print(f"{target['name']}: {exc}", flush=True)
            save()
            if args.execute:
                raise SystemExit('Batch stopped; inspect the report before retrying') from exc
        save()
    print(f'Report: {report_path.resolve()}', flush=True)


if __name__ == '__main__':
    main()
