# SPHEREx sky-change explorer

This web application searches public SPHEREx observations, keeps a persistent metadata catalogue, extracts real image regions, and prepares an interactive sky blink viewer. It is an exploratory tool, not a validated variability or discovery pipeline.

## Open the app

Double-click **Launch Viewer.cmd**, or open http://127.0.0.1:8765 while the server is running. The launcher starts the local backend when needed and reuses it on subsequent launches. Opening `web/index.html` directly cannot provide the backend; the page now explains this rather than showing an unexplained fetch error.

1. Choose a challenge target or enter ICRS RA/Dec in degrees and a circular field diameter.
2. Click **Find observations**. The app finds metadata and progressively prepares an initial selection of real cutouts. Existing pixels speed preparation but do not restrict which records can be requested. The status beside the button and inside the viewer shows first-load preparation progress. Review dates, detector arrays, releases and archive provenance below.
3. Open Advanced settings at the top right for detector/date filters and the initial load size (6/12/24). Data & downloads lists every returned record with pagination, selections, per-record viewing and an explicit Load every result progressively action. Wavelength groups organize comparisons without discarding other selected records.
4. To change the automatic sequence, click **Reload sequence with these settings**. Image preparation runs in the background and reports failed/skipped records. A first sequence can take several minutes because the archive is remote. Repeated sequences reuse local cutouts and products.
5. Play/pause, step or scrub the timeline. Choose a narrow wavelength group for more comparable views. Groups with multiple frames provide a blink GIF and an exploratory difference; groups also provide an unweighted mean coadd.
6. Optionally load Gaia or AllWISE positions. Catalogue service errors are displayed separately from image failures. Brightness changes affect the display only.

## Implemented

- Input validation; selectable field diameter; fixed-coordinate share URLs and saved sequence URLs.
- SQLite metadata index preserving full returned records, footprints, dates, array/range metadata, processing-release URLs and source IDs. Exact spatial-query coverage results are cached for 24 hours; refresh is explicit. A failed refresh can use saved metadata with a stale warning.
- Image selection and date sorting happen **before** image retrieval. The catalogue is incremental, not a claimed all-sky mirror. A new field still requires a lightweight archive metadata query. Existing records alone cannot establish complete coverage of a field that has never been queried.
- Explicit record IDs are retained, including distinct archive products. Individual sequence/mosaic requests accept up to 24 records; durable field-download jobs accept up to 500 indexed overlapping records and retain per-record outcomes. The all-sky metadata importer targets DR1/QR3 wide/deep collections, but ingestion is currently incomplete after archive HTTP 502 failures. Regional default searches still cover wide-survey DR1/QR3.
- Real native science, variance, zodiacal background and quality pixels. IRSA cutout requests returned HTTP 503 during development, so the adapter uses supported HTTP byte ranges to read headers and science row strips, plus compressed quality-mask extensions decoded locally. It does not retain whole native exposures.
- Default archive IMAGE display: common fixed-sky TAN projection, north up/east left, nearest native pixels, common asinh stretch and finite/in-bounds footprint. No additional PSF/ePSF model, ZODI subtraction or quality mask is applied in this view. Explicitly selected analysis products subtract ZODI once. Every quality bit except informational SOURCE/FULLSAMPLE is conservatively excluded; nonfinite data and nonpositive variance are also excluded. Header flag definitions are used rather than assuming SOURCE means bad data.
- Approximate target-position wavelength and bandwidth from WCS-WAVE. Narrow groups require the same detector and release, centre differences no greater than 0.25 of the smaller bandwidth, and widths within 10% of the other group members. These are exploratory eligibility rules, not verified identical response functions.
- UTC observation labels, playback speeds, date stepping, timeline, wavelength filtering, group coadds, last-minus-first differences, labelled animated GIFs and provenance/metadata JSON downloads.
- Real Gaia DR3 / AllWISE overlay adapter through IRSA cone search. Gaia uses approximate linear proper motion when available, without parallax/radial velocity; AllWISE positions are fixed at catalogue epochs. Cone margins and row caps limit completeness. Overlays are for individual frames, not mixed-epoch products.
- Durable field preparation, bounded queue, stop-after-current and explicit resume, per-record failures and common-stretch cached assembly. The development listener defaults to localhost; portable curl selection, configurable persistent cache/listener/hosts and a Linux container recipe support hosted deployment preparation. The container and public multi-user deployment have not been verified.

## Actual public coverage checked 14 November 2026

Five-arcminute diameter queries (archive overlap counts, **not independent usable epochs or detections**):

| Target | DR1 records | QR3 records |
| --- | ---: | ---: |
| WISE0855, challenge-supplied position | 277 | 0 |
| Barnard's Star | 254 | 125 |
| Epsilon Indi B, brown-dwarf system | 358 | 120 |
| RW Aurigae | 228 | 113 |
| R Draconis | 448 | 127 |

Other than WISE0855, positions were resolved by CDS Sesame/SIMBAD; raw resolver evidence, coordinates and per-release date bounds are saved in `evidence/target-coverage.json`. Epsilon Indi B resolved to the brown-dwarf system, not the bright primary. Reference positions are not automatically propagated to each SPHEREx epoch. Small fields can therefore miss high-proper-motion targets; enlarge the field and inspect catalogue epochs. The original two XML files used a smaller radius of 0.001 degrees and correctly retain their earlier 258/0 counts.

Official sources:

- https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/
- https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/
- https://irsa.ipac.caltech.edu/ibe/cutouts.html
- https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html
- https://irsa.ipac.caltech.edu/data/Gaia/dr3/gaia_dr3_source_colDescriptions.html

## Scientific limits

Selecting D1–D6 does not select one fixed wavelength: SPHEREx has linear-variable filters. All-wavelength playback is labelled exploratory and can show spectral differences as apparent variability. Even narrow groups use visualization-precision WCS-WAVE, not calibrated CWAVE/CBAND response kernels. Pixel wavelength also varies across the displayed field.

PSFs are not homogenized; source-level astrometry, proper motion, blending and flux recovery have not been validated. Reprojection uses nearest pixels rather than a flux-conserving measurement operator. Differences have no propagated significance/uncertainty, and coadds are unweighted means with variable coverage. These products must not be used as evidence of a variable source on their own. No calibrated source spectra or automatic discovery claims are made. Gaia/WISE overlay positions do not guarantee unique counterpart associations.

## Storage and isolation

The environment and caches live only in this chat's `work/` directory. Cutout cache: 256 MiB with automatic eviction of derived cached cutouts. The default derived-product capacity is 512 MiB; individual jobs can configure SPHEREX_PRODUCT_CACHE_MIB. The field controller currently uses the 512 MiB guard. Cached native FITS regions can be evicted independently of prepared PNGs; original archive provenance remains recorded. SQLite and compact catalogue overlays are additional metadata storage. No NEP files, original exposures or environments are changed or duplicated; its 100 GB dataset budget remains binding. No external publication/upload or paid service is used.

## Development and checks

Python dependencies are listed in `requirements.txt`. This chat uses the isolated `work/viewer-venv` environment. To recreate it from this directory:

```powershell
python -m venv ../../work/viewer-venv
../../work/viewer-venv/Scripts/python.exe -m pip install -r requirements.txt
../../work/viewer-venv/Scripts/python.exe server.py
```

Windows `curl.exe` or Linux `curl` uses system certificate validation. No certificate checks are disabled. The service is local development software; public hosting still requires container verification, rate limits, durable-volume configuration and hosted concurrency/load testing. See HOSTING.md; no public deployment has been performed.

```powershell
../../work/viewer-venv/Scripts/python.exe -m unittest discover -s . -p "test_*.py"
node --check web/app.js
```

Tests include actual saved metadata, archive errors, coordinate limits, and a separately labelled synthetic numerical fixture for compressed-mask decoding, pixel extraction, WCS preservation and wavelength interpolation. Synthetic fixture imagery is never displayed as observations.

## Later NEP integration

The viewer remains independent. Optional future versioned tables can carry stable `source_id`, ICRS coordinates/reference epoch, classification, spectrum/response/variance references, P(z), interval/mode summaries, quality flags and method/provenance. Reference catalogue redshifts must have separate provenance fields. No validated NEP redshift or science-ready 3D result is asserted here.


## Continuous diameters and spatial mosaics

Any numeric diameter from 1 to 60 arcminutes is accepted. A 10-arcminute diameter is 1/6 degree, with a 5-arcminute radius. The adapter extracts actual native pixels and mask/variance/background data, then projects them onto a common fixed 256×256 TAN sky grid. Output pixel sampling does not increase native angular resolution. The current byte-range fallback transfers row strips and compressed mask data; it does not merely enlarge a cached smaller image or require an exact pre-downloaded field size.

Partial exposures remain eligible for viewing if any usable pixel overlaps the requested grid; unobserved/masked areas remain missing. If the target centre is outside the wavelength grid, the cutout-centre wavelength is explicitly labelled and is not accepted as a target-position match. Select 2–24 same-detector/release sources in Data to request an exploratory spatial mosaic. Valid overlapping samples are averaged on the same grid, missing gaps stay missing, and contributor/coverage provenance is recorded. Different dates/local wavelengths can be mixed: this is not a calibrated single-epoch monochromatic mosaic.

Live WISE0855 field job: 9dc8d6d7fc573c36c301e9d6, requesting 277 records at 10 arcminutes. GET /api/v1/field-downloads/{id} is the authoritative status. A saved sequence alone is not the whole request. Browser reload preserves batch_id; browser closure does not cancel the server controller. A server restart leaves interrupted work for explicit POST resume. Three consecutive failures pause further requests. Common-stretch timelines rebuild at milestones to avoid quadratic product growth; each prepared record can be opened immediately while subsequent cutouts load.


## Archive IMAGE display is the default

Advanced settings → Image source defaults to Archive IMAGE. This uses calibrated mission IMAGE pixels with sky alignment and a common display stretch, without our ZODI subtraction, quality-mask application or any PSF/ePSF fitting. Existing analysis products remain unchanged and are opt-in. See RAW_DISPLAY_REPORT.md for preservation and test evidence. A lightweight raw_previews.py renderer reads cached native data; the launcher starts it alongside an already running server without restarting that server. It fetches no archive pixels. Archive transfer remains the principal cold-load cost in observed cases.

Additional display regression: `node test_raw_view.cjs`.
