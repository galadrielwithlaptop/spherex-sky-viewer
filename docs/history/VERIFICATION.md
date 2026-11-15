# Verification — 14 November 2026

The local backend is available at http://127.0.0.1:8765. Relaunch with Launch Viewer.cmd after a reboot or if it has stopped.

Verified example:
http://127.0.0.1:8765/?ra=133.7951291667&dec=-7.2451472222&fov=5&job=32a51c0385db27101ce8fb1d

## What passed

- Six automated tests: real archived metadata parsing; archive-error/coordinate validation; persistent-query reuse with stable IDs and an explicitly stale offline fallback; compressed FITS-mask decoding with pixel/WCS/wavelength preservation; signed difference display with zero at middle gray and distinct missing pixels.
- JavaScript syntax and Python module compilation.
- Live backend health, real archive search and local catalogue reuse.
- 2,050 image records indexed across the five requested fields, with 11 stored query results (including the original small-radius evidence query).
- Real SPHEREx frame extraction through HTTP byte ranges; compressed FLAGS decoded locally. Informational SOURCE pixels remain available.
- Default wavelength-first planning on two real observations: May 6 and October 31, 2025; target-position central wavelengths 3.4531539 and 3.4425705 microns. Both passed the declared approximate grouping rules; no frames skipped in this pair.
- Browser rendering of that pair, chronological next/previous and automatic playback with advancing dates, coadd and difference controls.
- Two-frame labelled GIF at 512 by 512 pixels; reproducible frame provenance in evidence/verified-pair-manifest.json.
- Live catalogue overlays: Gaia DR3 returned 228 entries and AllWISE returned 458 entries in the query plus margin. Selection was verified in the browser and real AllWISE position squares were visibly overlaid. Only in-field positions are drawn.
- Native-region FITS download returned successfully. Sequence recovery remained complete after backend restart.

## Faults addressed

The original HTML depended on a backend that was not listening when checked. The launcher now starts or reuses that backend; file-only or disconnected use produces an actionable startup message.

IRSA's generated-cutout path returned HTTP 503. The image adapter instead reads bounded native file ranges and locally decodes the compressed mask extension. Some transfers reset; bounded retries and explicit per-frame failure records are implemented. An earlier exploratory four-record task retained three usable images and reported the failed record, rather than substituting imagery.

TAP catalogue cone queries timed out during verification. IRSA's cone-search interface returned real Gaia/AllWISE rows and is now used for overlays.

## Limits

Image playback was verified for the WISE0855 field; that is not a source detection claim. Barnard's Star also has a verified two-frame image sequence (see the search-flow fix below). Epsilon Indi B, RW Aurigae and R Draconis retain metadata coverage audits; their image sequences and expected astrophysical changes have not been validated. Public hosting, calibrated spectra, PSF-matched significance images and automated discoveries are not implemented. Coadds/differences remain clearly labelled exploratory. The NEP workspace and its originals were not modified.


## Search-flow fix — 14 November 2026

Reproduced the reported blank result. Find observations cleared the existing canvas and stopped after loading metadata, requiring a separate image-preparation click. A browser-retained older script also hid the new feedback in an early retest.

Find observations now automatically loads a compatible completed sequence or starts image preparation. Feedback appears next to the search button and inside the viewer. The image worker queue is explicit; pending job URLs survive refresh. Asset versioning and revalidation prevent the retained-script issue. Cache lookup checks field coordinates, field size, detector, date limits, wavelength-group eligibility and actual product-file availability.

Verified through the visible browser, using the target selector and Find observations button rather than a preselected job link:

- WISE0855: two real near-matching-wavelength frames loaded automatically from cache.
- Barnard's Star: first preparation completed with two usable frames and no skips, at 1.0468733 and 1.0508724 microns, from 29 August 2025 and 11 March 2026. Subsequent Find observations loaded them automatically. This verifies rendering, not an astrophysical motion or source-identification claim.
- Saved screenshot: search-fix-barnard.jpg.
- Seven Python tests pass, including a new cache-eligibility regression.
- Three frontend flow regressions pass against the actual app.js: one-click cached-image rendering, automatic first-time preparation with visible queue feedback and refreshable job URL, and an explicit empty-search result. Run with `node test_frontend.cjs`.
