# SPHEREx Sky Viewer

Explore real SPHEREx infrared sky images, discover archive observations by sky
coordinates, and inspect prepared image sequences through a public web interface.
Independent NASA Space Apps project; not an official NASA or IRSA service.

**Live viewer:** https://srv2163798.hstgr.cloud/

**API documentation:** https://srv2163798.hstgr.cloud/api/docs

## Current snapshot

As of **15 November 2026**, this repository includes:

| Target | Indexed archive products | Cached 5′ IMAGE cutouts |
|---|---:|---:|
| WISE0855 | 277 | 13 |
| Barnard's Star | 379 | 13 |
| Epsilon Indi B | 478 | 13 |
| RW Aurigae | 341 | 13 |
| R Draconis | 575 | 13 |
| **Total** | **2,050** | **65** |

Archive overlap counts describe metadata records, not confirmed detections or
independent same-wavelength epochs. This is a regional index, **not a complete
all-sky SPHEREx catalogue**. See [snapshot metadata](data/snapshot-summary.json).

The hosted starter pipeline reads the calibrated archive **IMAGE** plane. It does
not fit ePSFs, subtract zodiacal brightness, or apply quality-flag masks. It does
project pixels onto a common sky grid and stretch them to produce visible PNGs.
Artifacts can remain visible. Detector ranges are labelled; target-position
wavelengths were not downloaded for this starter batch.

## Repository layout

```text
viewer/               Python backend, browser frontend, tests, Docker recipe
  web/                 HTML, JavaScript, styles and reproducible examples
  evidence/            Source metadata fixtures and target positions
data/                  Portable snapshot of metadata and downloaded cutouts
  catalogue.sqlite     Searchable observation index
  products/            Retained FITS, previews and sequence manifests
  starter-5arcmin.json  Starter preparation report and observation provenance
docs/                  Screenshots, reports and development history
scripts/               Historical Windows launch helpers
compose.yaml           Local Docker deployment with persistent data
.env.example           Deployment settings, without credentials
```

Some historical reports describe earlier builds, failures or smaller two-/three-
frame demonstrations. They are retained as development history; this README and
the dated data snapshot describe the published repository state.

## Run with Docker

Install Docker with Compose, then:

```sh
git clone https://github.com/galadrielwithlaptop/spherex-sky-viewer.git
cd spherex-sky-viewer
docker compose up --build -d
```

Open http://localhost:8765. Select a target under **Open a prepared 5′ field**, then
open **Blink & timeline** to play or step through its cached frames. These links
do not request new archive images. The [starter gallery](http://localhost:8765/starter.html)
shows the individual cutouts and FITS download links.

For public deployment, set `SPHEREX_ALLOWED_HOSTS` to your hostname, terminate
HTTPS with a reverse proxy such as Traefik, and persist `/data`. The running
Hostinger installation uses `/opt/spherex/data`; its source and Compose files are
separate from that data. Do not put passwords, SSH private keys or GitHub tokens
in this repository. The historical Fly configuration is optional and is not the
live hosting configuration.

## Run Python directly

Python 3.13 and system `curl` are used by the container. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r viewer/requirements.txt
export SPHEREX_CACHE_DIR="$PWD/data"
python viewer/server.py
```

On PowerShell, use `.venv\Scripts\Activate.ps1` and set
`$env:SPHEREX_CACHE_DIR = (Resolve-Path data).Path` before starting Python.

## Metadata-first discovery and local reuse

The SQLite index stores observation identifiers, dates, footprints, detector
information and archive URLs. Coordinate searches select candidate observations
from metadata rather than downloading the entire image archive.

For the five prepared 5′ fields, ordinary **Find observations** queries the
metadata and reuses the current published cached sequence when its coordinates,
diameter and filters match. The current sequence is resolved from data metadata;
its identifier is not hard-coded into the frontend. Explicit reloads and other
fields can request more work through the Python backend.

The starter gallery reads `products/starter/index.json` every ten seconds.
Adding files and publishing their metadata does not require a frontend rebuild.
Files must exist before their entries are marked ready. If a file moves, update
its metadata URL; metadata alone cannot manufacture missing images.

## Add more IMAGE-only cutouts

In a running Docker deployment:

```sh
docker compose exec viewer python seed_raw_targets.py --execute --cache-only --per-target 12 --minutes 43
```

The command retains existing ready images, selects additional observations,
downloads native IMAGE regions, and publishes updated cached sequences as images
finish. It skips retained ready observations. This is a sampled starter workflow,
not a request to mirror every indexed archive product. The per-target option is
the number of sampled records; retained earlier records can make the total larger.
Run only one instance against a data directory at a time.

To rebuild sequences from existing cutouts without archive downloads:

```sh
docker compose exec viewer python publish_starter_sequences.py
```

Metadata-only archive ingestion is available separately:

```sh
docker compose exec viewer python sync_catalogue.py
```

For a separate retrying metadata worker, use the optional
[`compose.metadata.yaml`](compose.metadata.yaml). See
[all-sky metadata scope and progress](docs/ALL_SKY_METADATA.md). Starting the
worker does not establish that its all-sky import has completed.

It resumes time partitions, but archive outages can prevent completion. A
successful regional query or an image download does not establish all-sky
completeness. Keep image preparation and metadata ingestion statuses separate.

## Public APIs

Use `/api/docs` or `/api/openapi.json` for the full current contract. Examples:

```sh
curl 'http://localhost:8765/api/health'
curl 'http://localhost:8765/api/v1/targets'
curl 'http://localhost:8765/api/v1/observations?ra=133.7951291667&dec=-7.2451472222&fov_arcmin=5&mode=cache_only&limit=25'
```

Observation queries are paginated. Image preparation uses explicit POST requests;
the versioned sequence status endpoint reports progress. The browser also retains
legacy routes for compatibility. Do not use legacy job-status GET requests as a
guarantee that no interrupted work can resume.

## Checks

Use an isolated scratch cache for tests, not the published data directory:

```sh
SPHEREX_CACHE_DIR=/tmp/spherex-tests python -m unittest discover -s viewer -p 'test_*.py'
node viewer/test_raw_view.cjs
node viewer/test_validation.cjs
```

Regression checks include the curl integer retry-time requirement, native
IMAGE-only extraction without analysis extensions, metadata queries and browser
logic. Fixture tests are not a substitute for hosted latency or browser testing.

## Scientific and operational limits

- Different wavelengths can mimic changes in brightness. The starter frames do
  not establish calibrated variability, motion measurements or discoveries.
- No target-position wavelength or quality-flag analysis was performed for the
  lightweight starter batch. Fixed coordinates do not propagate proper motion.
- A requested field can have partial detector coverage; missing pixels remain
  missing. Spatial overlap does not prove the named target is visible.
- Advanced analysis/coadd/difference features retain a separate legacy processing
  path. They are not the IMAGE-only starter workflow, and all advanced features
  have not been validated on the public deployment.
- Processing queues and cache limits are bounded. The 512 MiB legacy field-product
  guard is separate from available server disk capacity.
- GitHub stores a versioned snapshot. It is not the live Python host or an
  unlimited astronomical archive. Future large datasets should use suitable data
  storage and manifests rather than adding every intermediate product to Git.

## Sources and attribution

Science pixels and observation metadata come from NASA's SPHEREx mission through
the [NASA/IPAC Infrared Science Archive](https://irsa.ipac.caltech.edu/).
Named positions use challenge-supplied coordinates and CDS Sesame/SIMBAD as
recorded in the evidence fixtures. See [credits](viewer/web/credits.html) for
software and other catalogue/data sources. Development used OpenAI Codex.

No blanket software license has been selected by the project owner. Third-party
software and astronomical data retain their own terms and attribution needs.
