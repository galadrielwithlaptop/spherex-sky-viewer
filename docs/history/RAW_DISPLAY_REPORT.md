# Default archive IMAGE display

The viewer defaults to the calibrated IMAGE plane supplied by SPHEREx, rather than the existing background-subtracted/quality-masked analysis PNGs. No PSF/ePSF fitting or deconvolution was performed by the previous viewer; the distinction is now explicit.

The default display does not subtract ZODI or apply the quality-flag mask. It retains nearest-pixel sky alignment on the requested field grid and one common asinh display stretch per sequence, so frames remain geometrically comparable. Archive Level-2 IMAGE is already calibrated; this is not unprocessed detector telemetry. Finite coverage is labelled separately from quality-screened usable coverage, and flagged artifacts may be visible.

All existing native FITS, analysis PNGs, aligned arrays, coadds, differences and provenance remain intact. The NEP workspace/process was not accessed or modified. The ongoing field download was not stopped or restarted. A separate display renderer reads cached IMAGE planes and writes only new raw/ subdirectories and a bounded 256 MiB raw-display array cache. It downloads no archive data. An OS lock prevents duplicate display renderers. The launcher and future server startup start the renderer automatically.

Advanced settings → Image source exposes the preserved analysis products only by explicit choice. Raw display uses its own provenance link and does not silently fall back to analysis PNGs. Existing analysis blink GIF links are hidden in raw mode. Coadd/difference/mosaic views require explicitly choosing Analysis products.

This changes the display and avoids additional science processing in that display renderer. It does not remove the ongoing archive-transfer bottleneck or stop the existing analysis workflow. No cold-download latency improvement is claimed without measurement.

Verification: 54 Python tests, 29 existing frontend checks, 4 new archive-display logic regressions and 27 input-validation cases pass. A numerical fixture proves IMAGE=7 remains 7 despite ZODI=5 and all quality bits set; original FITS bytes remain identical. Tests also verify one common raw stretch, preservation of existing analysis files, and no processed-PNG fallback. Browser verification confirmed archive IMAGE playback, default source=raw, the raw provenance URL and false flags for zodi_subtracted/quality_mask_applied/psf_applied. Screenshot: archive-image-display.jpg.
