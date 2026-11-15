# Archive-to-viewer correction — 15 November 2026

## Verified facts

The saved WISE0855 wide-survey metadata result has 277 products: D1 45, D2 49, D3 46, D4 43, D5 49, D6 45. These are footprint-overlapping products, not 277 detections. The previous workflow sampled six D4 candidates, found no matching wavelength pair and rejected one target-centre probe. It never established that the other field records were unusable.

The corrected viewer lists every returned record with pagination, text filtering, selection and individual cutout viewing. Explicit record IDs are no longer silently collapsed by observation/detector or discarded for wavelength mismatch. Every chosen record is attempted; matching groups organize comparisons. Any numeric field diameter from 1 to 60 arcminutes is accepted.

A previously unprepared D1 record was downloaded and rendered at 10 arcminutes, in addition to the previous D4 pair. A three-frame common-stretch assembly and a selected two-source spatial mosaic were verified. The persistent all-record job has since produced additional actual exposures; eight real frames were verified in the growing timeline, and a newly prepared D6 source at 4.9684 microns could be opened while the remaining records continued loading.

## Live 277-record download

Job: `9dc8d6d7fc573c36c301e9d6`.

Snapshot UTC: 2026-11-15T11:25:44.198183+00:00.

State: running; counts: {'prepared': 13, 'failed': 0, 'loading': 1, 'pending': 263}.

The authoritative status is GET `/api/v1/field-downloads/9dc8d6d7fc573c36c301e9d6`. The on-disk journal is `work/viewer-cache/field-jobs/9dc8d6d7fc573c36c301e9d6.json`. This is an active field-scoped science download, not an all-sky image download. Closing the browser does not stop it. Stop finishes the current cutout; POSTing the same field and IDs explicitly resumes stopped/interrupted work. Three consecutive source failures pause the job, leaving unattempted records pending. Each failed attempt retains its reason/details.

Common-stretch timelines rebuild at milestones and at completion to avoid quadratic derived-product growth. Every prepared record is immediately viewable even before the next aggregate timeline rebuild. Browser reload preserves both the batch ID and current sequence ID; this was checked twice against the actual running job.

## How 10-arcminute cutouts work

10 arcminutes is a diameter of 1/6 degree, radius 5 arcminutes. Native WCS maps the requested sky region into the original exposure. The current range adapter retrieves science/variance/zodiacal row strips and compressed quality-mask data, then projects usable pixels onto a fixed 256×256 TAN grid spanning the requested field. It does not enlarge a preloaded 5-arcminute picture or invent missing sky. Display sampling does not increase native resolution.

Partial exposure coverage is retained, with gaps masked. If the target centre is not covered, the cutout-centre wavelength is labelled and not treated as a target-position match. Explicit selected same-detector/release mosaics combine valid coverage on the same grid and save contributor counts/source provenance. Mixed epochs/local wavelengths remain explicitly exploratory, not a calibrated monochromatic single-epoch product. Automatic scientifically validated per-epoch mosaicking remains unfinished.

## Tests and performance scope

50 Python tests, 29 fixture-backed frontend option regressions and 27 input-validation cases passed. Added tests cover retaining unmatched selected records, mosaic gaps/contributors, common display stretch across cached source jobs, explicit-only assembly, field-job persistence, stop/resume, per-record failures and pausing after consecutive failures. Windows concurrent journal read/replace handling was corrected and tested. Frontend resume regression now checks retention of batch_id.

A separate single local audit request reviewed all 277 records in about 1.52 seconds without pixels or headers fetched; this is not a distribution or hosted latency guarantee. Cold cutouts still take minutes in observed cases. No internet-hosted or concurrent-user performance claim is made.

## Remaining work and blocks

The existing catalogue is regional, not a complete all-sky mirror. A resumable compact all-sky metadata importer now targets four DR1/QR3 wide/deep collections and splits overflowing time partitions. Both live SIA attempts and an official TAP fallback probe returned HTTP 502. Zero all-sky partitions completed; no all-sky completeness claim is justified. Metadata ingestion remains pending upstream availability.

Public hosting was not performed. Linux curl selection, configurable persistent cache/listener/hosts and a container recipe are included, but the container and hosted multi-user load are unverified. The single-worker queue and one active field-download controller remain scaling limits. This milestone is not a submission-ready claim. See HOSTING.md and the illustrated in-app guide.

The original NEP workspace, environments and inputs were not modified. Science downloads are limited to this explicitly requested WISE0855 field. Native-cutout and product caches remain bounded; no full native exposure archive is retained.
