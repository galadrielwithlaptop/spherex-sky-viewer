# Hosted viewer status — 15 November 2026

Main site: https://srv2163798.hstgr.cloud/

Python runs in the spherex-viewer Docker container, behind Traefik HTTPS.
Docker is enabled at boot; the container restart policy is unless-stopped.
Persistent host data is /opt/spherex/data mounted at /data.
Deployment source is /opt/spherex/app; Compose config is /opt/spherex/compose.yaml.

The main page reads /products/starter/index.json for prepared-field shortcuts.
Each target has a three-frame main-viewer sequence using cached IMAGE-only FITS.
publish_starter_sequences.py regenerates those sequences from cached starter
files without archive requests. It uses a common stretch per target and does
not subtract ZODI or perform PSF/ePSF processing. Native-image downloads link
directly to the retained FITS products.

Verified after rebuilding the image and recreating the container:
- HTTPS health API returns 2,050 indexed observations and 13 cached queries.
- All five sequence endpoints return three frames each.
- A PNG from each sequence returns HTTP 200.
- API documentation returns HTTP 200.
- Browser renders WISE0855 and advances to frame two of three.

Previous batch verification checked all 15 PNG and FITS download paths.
No full all-sky metadata ingestion or full regression/load test is claimed.
Different wavelengths are exploratory; target-position wavelength metadata was
deliberately not downloaded for this starter batch.
