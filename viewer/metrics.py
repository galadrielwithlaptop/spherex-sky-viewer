"""Small bounded local telemetry; never logs coordinate query strings."""
import json,threading,time
from collections import deque
from store import CACHE

_lock=threading.Lock();_recent=deque(maxlen=1000)
def record(event):
    event=dict(event,at_unix=time.time())
    with _lock:
        _recent.append(event)
        path=CACHE/'request-metrics.jsonl'
        if path.exists() and path.stat().st_size>1024*1024:path.replace(CACHE/'request-metrics.previous.jsonl')
        with path.open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')

def snapshot():
    with _lock:rows=list(_recent)
    groups={}
    for row in rows:groups.setdefault(row['path'],[]).append(row['headers_ready_ms'])
    result={}
    for path,values in groups.items():
        values.sort();result[path]={'samples':len(values),'p50_ms':values[len(values)//2],'p95_ms':values[min(len(values)-1,int(len(values)*.95))]}
    return {'measure':'Server work until response headers; client reports separately measure full response','recent_requests':len(rows),'routes':result}
