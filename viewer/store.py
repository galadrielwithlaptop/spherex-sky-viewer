"""Persistent metadata catalogue and exact spatial-query coverage cache."""
import hashlib, json, sqlite3, time, threading, os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from geometry import footprint,cap_bounds,vector,intersects,RAD,angle

ROOT = Path(__file__).resolve().parent
CACHE = Path(os.environ.get('SPHEREX_CACHE_DIR',str(ROOT.parent.parent / 'work' / 'viewer-cache')))
CACHE.mkdir(parents=True, exist_ok=True)
DB = CACHE / 'catalogue.sqlite'
_SCHEMA_LOCK=threading.Lock()

@contextmanager
def connection():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory=sqlite3.Row
    try:
        if con.execute('PRAGMA user_version').fetchone()[0]<2:
            with _SCHEMA_LOCK:
                if con.execute('PRAGMA user_version').fetchone()[0]<2:
                    con.execute('PRAGMA journal_mode=WAL')
                    with con:
                        con.execute('CREATE TABLE IF NOT EXISTS queries (url TEXT PRIMARY KEY, fetched REAL, payload TEXT)')
                        con.execute('CREATE TABLE IF NOT EXISTS exposures (id TEXT PRIMARY KEY, ra REAL, dec REAL, mjd REAL, detector TEXT, payload TEXT)')
                        con.execute('CREATE INDEX IF NOT EXISTS by_date ON exposures(mjd)')
                        con.execute('CREATE TABLE IF NOT EXISTS footprint_shapes (image_rowid INTEGER PRIMARY KEY, shape TEXT NOT NULL)')
                        con.execute('CREATE VIRTUAL TABLE IF NOT EXISTS footprint_index USING rtree(image_rowid,x_min,x_max,y_min,y_max,z_min,z_max)')
                        con.execute('CREATE TABLE IF NOT EXISTS regions (url TEXT PRIMARY KEY,ra REAL,dec REAL,radius REAL,collection TEXT,fetched REAL,complete INTEGER)')
                        con.execute('CREATE INDEX IF NOT EXISTS by_region_release ON regions(collection,complete,fetched)')
                        con.execute('CREATE TABLE IF NOT EXISTS index_state (name TEXT PRIMARY KEY,value INTEGER)')
                        con.execute("INSERT OR IGNORE INTO index_state VALUES ('revision',0)")
                        con.execute('CREATE TABLE IF NOT EXISTS image_filters (image_rowid INTEGER PRIMARY KEY,collection TEXT,detector INTEGER,end_mjd REAL)')
                        con.execute('CREATE INDEX IF NOT EXISTS by_collection_detector ON image_filters(collection,detector,image_rowid)')
                        con.execute('PRAGMA user_version=2')
        if con.execute('PRAGMA user_version').fetchone()[0]<3:
            with _SCHEMA_LOCK:
                if con.execute('PRAGMA user_version').fetchone()[0]<3:
                    with con:
                        con.execute('CREATE TABLE IF NOT EXISTS query_members (url TEXT,image_id TEXT,PRIMARY KEY(url,image_id)) WITHOUT ROWID')
                        con.execute('CREATE TABLE IF NOT EXISTS query_snapshot_state (url TEXT PRIMARY KEY,fetched REAL)')
                        con.execute('PRAGMA user_version=3')
        if con.execute('PRAGMA user_version').fetchone()[0]<4:
            with _SCHEMA_LOCK:
                if con.execute('PRAGMA user_version').fetchone()[0]<4:
                    with con:
                        con.execute('CREATE TABLE IF NOT EXISTS global_generations (generation TEXT PRIMARY KEY, status TEXT, completed REAL, start_mjd REAL, end_mjd REAL, collections TEXT)')
                        con.execute('CREATE TABLE IF NOT EXISTS global_members (generation TEXT,image_id TEXT,PRIMARY KEY(generation,image_id)) WITHOUT ROWID')
                        con.execute('PRAGMA user_version=4')
        with con:yield con
    finally:con.close()

def get_query(url):
    with connection() as c:
        r = c.execute('SELECT fetched,payload FROM queries WHERE url=?', (url,)).fetchone()
    return None if r is None else {'fetched': r[0], **json.loads(r[1])}

def put_query(url, result):
    with connection() as c:
        for row in result['rows']:
            key = hashlib.sha256(row['access_url'].encode()).hexdigest()[:24]
            row['id'] = key
            prior=c.execute('SELECT rowid,payload FROM exposures WHERE id=?',(key,)).fetchone()
            payload=json.dumps(row)
            c.execute('INSERT INTO exposures VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET ra=excluded.ra,dec=excluded.dec,mjd=excluded.mjd,detector=excluded.detector,payload=excluded.payload', (key,float(row['s_ra']),float(row['s_dec']),float(row['t_min']),row.get('energy_bandpassname',''),payload))
            image_rowid=c.execute('SELECT rowid FROM exposures WHERE id=?',(key,)).fetchone()[0]
            if prior is None or prior['payload']!=payload:
                index_row(c,image_rowid,row)
                c.execute("UPDATE index_state SET value=value+1 WHERE name='revision'")
        fetched=time.time()
        c.execute('INSERT OR REPLACE INTO queries VALUES (?,?,?)', (url,fetched,json.dumps(result)))
        record_region(c,url,result,fetched)
        record_members(c,url,result,fetched)
        c.execute("UPDATE index_state SET value=value+1 WHERE name='revision'")

def record_members(c,url,result,fetched):
    c.execute('DELETE FROM query_members WHERE url=?',(url,))
    c.executemany('INSERT OR IGNORE INTO query_members VALUES (?,?)',((url,hashlib.sha256(r['access_url'].encode()).hexdigest()[:24]) for r in result['rows']))
    c.execute('INSERT OR REPLACE INTO query_snapshot_state VALUES (?,?)',(url,fetched))

def index_row(c,image_rowid,row):
    shape=footprint(row.get('s_region',''));bounds=cap_bounds(shape['center'],shape['radius'])
    c.execute('INSERT OR REPLACE INTO footprint_shapes VALUES (?,?)',(image_rowid,json.dumps(shape)))
    c.execute('INSERT OR REPLACE INTO footprint_index VALUES (?,?,?,?,?,?,?)',(image_rowid,*bounds))
    label=row.get('energy_bandpassname','')
    detector=int(label[-1]) if label[-1:].isdigit() else None
    c.execute('INSERT OR REPLACE INTO image_filters VALUES (?,?,?,?)',(image_rowid,row.get('obs_collection',''),detector,float(row.get('t_max') or row['t_min'])))

def record_region(c,url,result,fetched):
    try:
        q=parse_qs(urlsplit(url).query);parts=q['POS'][0].split()
        if parts[0].upper()!='CIRCLE':return
        ra,dec,radius=map(float,parts[1:]);collection=q['COLLECTION'][0]
        c.execute('INSERT OR REPLACE INTO regions VALUES (?,?,?,?,?,?,?)',(url,ra,dec,radius,collection,fetched,int(not result['truncated'])))
    except (ValueError,KeyError,IndexError):pass

def initialize_index():
    """Migrate existing metadata locally; never reads image bytes or contacts IRSA."""
    with connection() as c:
        for table in ('footprint_index','footprint_shapes','image_filters'):
            c.execute(f'DELETE FROM {table} WHERE image_rowid NOT IN (SELECT rowid FROM exposures)')
        for r in c.execute('SELECT e.rowid AS n,e.payload FROM exposures e LEFT JOIN footprint_shapes s ON e.rowid=s.image_rowid WHERE s.image_rowid IS NULL').fetchall():
            index_row(c,r['n'],json.loads(r['payload']))
            c.execute("UPDATE index_state SET value=value+1 WHERE name='revision'")
        for r in c.execute('SELECT q.* FROM queries q LEFT JOIN regions r ON q.url=r.url WHERE r.url IS NULL').fetchall():
            record_region(c,r['url'],json.loads(r['payload']),r['fetched'])
        for r in c.execute('SELECT q.* FROM queries q LEFT JOIN query_snapshot_state s ON q.url=s.url WHERE s.url IS NULL OR s.fetched!=q.fetched').fetchall():
            record_members(c,r['url'],json.loads(r['payload']),r['fetched'])

def global_snapshot(c):
    r=c.execute("SELECT * FROM global_generations WHERE status='complete' ORDER BY completed DESC LIMIT 1").fetchone()
    return dict(r) if r else None

def coverage(ra,dec,radius,collection,max_age=86400):
    center=vector(ra,dec);now=time.time();matches=[]
    with connection() as c:
        regions=c.execute('SELECT * FROM regions WHERE collection=? AND complete=1',(collection,)).fetchall()
        whole=global_snapshot(c)
    if whole and collection in json.loads(whole['collections']):
        matches.append({'fetched':whole['completed'],'url':'allsky:'+whole['generation'],'scope':'all_sky_time_interval','time_range_mjd':[whole['start_mjd'],whole['end_mjd']]})
    for r in regions:
        if angle(center,vector(r['ra'],r['dec']))/RAD+radius<=r['radius']+1e-9:matches.append(dict(r))
    if not matches:return {'complete':False,'fresh':False,'fetched':None}
    best=max(matches,key=lambda r:r['fetched'])
    return {'complete':True,'fresh':now-best['fetched']<=max_age,'fetched':best['fetched'],'source_query':best['url'],**({k:best[k] for k in ['scope','time_range_mjd'] if k in best})}

@lru_cache(maxsize=10000)
def decoded_shape(payload):return json.loads(payload)

def spatial_rows(ra,dec,radius,collections=None,detector=None,start=None,end=None):
    """Indexed candidate lookup followed by spherical footprint intersection."""
    center=vector(ra,dec);b=cap_bounds(center,radius*RAD)
    where=['r.x_min<=?','r.x_max>=?','r.y_min<=?','r.y_max>=?','r.z_min<=?','r.z_max>=?']
    args=[b[1],b[0],b[3],b[2],b[5],b[4]]
    if collections:
        where.append('f.collection IN ('+','.join('?' for _ in collections)+')');args+=list(collections)
    if detector is not None:where.append('f.detector=?');args.append(detector)
    if start is not None:where.append('f.end_mjd>=?');args.append(start)
    if end is not None:where.append('e.mjd<=?');args.append(end)
    sql='SELECT e.payload,s.shape FROM footprint_index r CROSS JOIN exposures e ON e.rowid=r.image_rowid CROSS JOIN footprint_shapes s ON s.image_rowid=e.rowid CROSS JOIN image_filters f ON f.image_rowid=e.rowid WHERE '+' AND '.join(where)+' ORDER BY e.mjd,e.id'
    with connection() as c:
        c.execute('BEGIN');candidates=c.execute(sql,args).fetchall();revision=c.execute("SELECT value FROM index_state WHERE name='revision'").fetchone()[0]
        # A complete covering snapshot is authoritative. Keep historical records
        # in the index, but do not resurrect products removed by a later refresh.
        whole=global_snapshot(c);global_ids=set()
        if whole:
            ids=[json.loads(r['payload'])['id'] for r in candidates]
            for offset in range(0,len(ids),500):
                chunk=ids[offset:offset+500]
                if chunk:global_ids.update(r[0] for r in c.execute('SELECT image_id FROM global_members WHERE generation=? AND image_id IN ('+','.join('?' for _ in chunk)+')',[whole['generation'],*chunk]))
        snapshots={}
        for region in c.execute('SELECT * FROM regions WHERE complete=1 ORDER BY fetched DESC').fetchall():
            release=region['collection']
            if collections and release not in collections:continue
            if release in snapshots:continue
            if angle(center,vector(region['ra'],region['dec']))/RAD+radius>region['radius']+1e-9:continue
            snapshots[release]=(region['fetched'],{r[0] for r in c.execute('SELECT image_id FROM query_members WHERE url=?',(region['url'],))})
    rows=[]
    for r in candidates:
        shape=decoded_shape(r['shape'])
        if intersects(shape,center,radius*RAD):
            row=json.loads(r['payload']);snapshot=snapshots.get(row.get('obs_collection'))
            global_authority=whole and row.get('obs_collection') in json.loads(whole['collections']) and (not snapshot or whole['completed']>=snapshot[0])
            if global_authority:
                if row['id'] not in global_ids:continue
                row['index_membership']='complete_allsky_snapshot'
            else:
                if snapshot and row['id'] not in snapshot[1]:continue
                row['index_membership']='complete_query_snapshot' if snapshot else 'unconfirmed_regional_candidate'
            row['footprint_match']='spherical_polygon' if shape['supported'] else 'unverified_candidate';rows.append(row)
    return {'rows':rows,'revision':revision,'candidates':len(candidates),'unverified_footprints':sum(r['footprint_match']=='unverified_candidate' for r in rows)}

def exposure(key):
    with connection() as c:
        r = c.execute('SELECT payload FROM exposures WHERE id=?',(key,)).fetchone()
    if r is None: raise ValueError('Unknown image ID; search the field first.')
    return json.loads(r[0])

def stats():
    with connection() as c:
        return {'exposures':c.execute('SELECT COUNT(*) FROM exposures').fetchone()[0], 'queries':c.execute('SELECT COUNT(*) FROM queries').fetchone()[0]}
