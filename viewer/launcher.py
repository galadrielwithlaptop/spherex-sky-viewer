"""Start or reuse the local app, then open its actual server URL."""
import json, os, subprocess, sys, time, urllib.request, webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8765'
def ready():
    try:
        with urllib.request.urlopen(URL+'/api/health',timeout=2) as r:
            return json.load(r).get('version')==2
    except Exception:return False

if __name__=='__main__':
    if not ready():
        logs=ROOT.parent.parent/'work';logs.mkdir(exist_ok=True)
        with (logs/'viewer-server.log').open('a') as out,(logs/'viewer-server-errors.log').open('a') as err:
            subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=ROOT,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(40):
            if ready():break
            time.sleep(.25)
        else:raise SystemExit('Viewer could not start. See work/viewer-server-errors.log.')
    logs=ROOT.parent.parent/'work';logs.mkdir(exist_ok=True)
    with (logs/'raw-preview-worker.log').open('a') as out:
        subprocess.Popen([sys.executable,str(ROOT/'raw_previews.py'),'--watch','--server-url',URL],cwd=ROOT,stdout=out,stderr=out,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    print(URL)
    if '--no-browser' not in sys.argv:webbrowser.open(URL)
