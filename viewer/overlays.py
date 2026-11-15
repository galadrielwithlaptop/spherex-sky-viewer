"""Real catalogue positions from IRSA cone search, with epoch limitations."""
import hashlib, json, time
from urllib.parse import urlencode
from archive import query_url, COLLECTIONS, parse_votable
from network import text
from store import CACHE
from catalogue import APIError

def catalogue(ra,dec,fov,name,cache_only=False):
    query_url(ra,dec,fov,COLLECTIONS[0])
    ra,dec,fov=map(float,(ra,dec,fov))
    tables={'gaia':('gaia_dr3_source','source_id,ra,dec,pmra,pmdec,ref_epoch,phot_g_mean_mag'),'wise':('allwise_p3as_psd','designation,ra,dec,w1mpro,w2mpro')}
    if name not in tables:raise ValueError('Choose gaia or wise overlay')
    table,columns=tables[name]
    # Include a modest margin for high proper motion; completeness not guaranteed.
    # IRSA SCS proved responsive when the same cone timed out through TAP.
    url='https://irsa.ipac.caltech.edu/SCS?'+urlencode({'table':table,'RA':ra,'DEC':dec,'SR':fov/120+.05,'MAXREC':501})
    key=hashlib.sha256(url.encode()).hexdigest()[:24];directory=CACHE/'overlays';directory.mkdir(exist_ok=True);path=directory/(key+'.json')
    if path.exists() and (cache_only or time.time()-path.stat().st_mtime<86400):
        return dict(json.loads(path.read_text()),cached=True,stale=time.time()-path.stat().st_mtime>=86400)
    if cache_only:raise ValueError('This overlay is not cached; use mode=auto for a metadata-only catalogue query')
    try:
        raw=text(url)
        parsed=parse_votable(raw)
    except Exception as error:
        label='AllWISE' if name=='wise' else 'Gaia'
        message=f'IRSA is unavailable. The {label} catalogue could not be reached. Cached sky images remain available.'
        if path.exists():
            saved=json.loads(path.read_text())
            return dict(saved,cached=True,stale=True,archive_unavailable=True,warning=message+' Showing an older cached catalogue. '+saved['warning'])
        raise APIError(message,502,'irsa_unavailable') from error
    rows=[{k:v for k,v in row.items() if k in columns.split(',')} for row in parsed['rows']]
    if rows and 'ra' not in rows[0]:raise ValueError('Unexpected catalogue response')
    result={'catalogue':table,'query_url':url,'rows':rows[:500],'truncated':len(rows)>500 or parsed['truncated'],'fetched':time.time(),'warning':'Gaia positions use a linear proper-motion approximation when available, without parallax or radial velocity. AllWISE positions remain at catalogue epochs. Cone margin and 500-row cap limit completeness.'}
    path.write_text(json.dumps(result));return result
