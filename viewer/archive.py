"""Metadata only: never downloads or changes science images."""
import math
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

COLLECTIONS = ('spherex_dr1', 'spherex_qr3')
AVAILABLE_COLLECTIONS=COLLECTIONS+('spherex_dr1_deep','spherex_qr3_deep')
NS = {'v': 'http://www.ivoa.net/xml/VOTable/v1.3'}

def query_url(ra, dec, fov, collection):
    ra, dec, fov = map(float, (ra, dec, fov))
    if not all(map(math.isfinite, (ra, dec, fov))) or not (0 <= ra < 360 and -90 <= dec <= 90 and 1 <= fov <= 60):
        raise ValueError('Use RA 0–360 (exclusive), Dec −90–90, and field diameter 1–60 arcmin.')
    if collection not in AVAILABLE_COLLECTIONS:
        raise ValueError('Unsupported collection')
    return 'https://irsa.ipac.caltech.edu/SIA?' + urlencode({'COLLECTION': collection, 'POS': f'CIRCLE {ra} {dec} {fov / 120}', 'MAXREC': 2000})

def parse_votable(data):
    root = ET.fromstring(data)
    infos = root.findall('.//v:INFO', NS)
    for info in infos:
        if info.get('name') == 'QUERY_STATUS' and info.get('value') == 'ERROR':
            raise ValueError(info.text or 'Archive query failed')
    tables = root.findall('.//v:TABLE', NS)
    if not tables:
        raise ValueError('Archive returned no result table')
    table = tables[-1]
    fields = [f.get('name') for f in table.findall('v:FIELD', NS)]
    rows = [dict(zip(fields, [(c.text or '').strip() for c in r.findall('v:TD', NS)])) for r in table.findall('.//v:TR', NS)]
    return {'rows': rows, 'truncated': any(i.get('value') == 'OVERFLOW' for i in infos)}
