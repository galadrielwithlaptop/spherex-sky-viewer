# SPHEREx scope and checkpoints

Updated 15 November 2026 (Asia/Kolkata).

## Agreed work

1. Metadata-first spatial catalogue: select only observations overlapping requested coordinates, filter and order before any pixels are fetched. Do not bulk-download images.
2. Versioned, documented APIs that external callers can integrate. Build and test locally; external hosting/publication is not authorized.
3. Regression-test implemented options and measure latency, distinguishing local/cache, archive metadata and actual image preparation.
4. Apply optimizations justified by measurements; preserve scientific caveats and cache/completeness provenance.

## Historical implementation work (superseded by the latest checkpoint below)

- Existing app has 2,050 image records, exact-query caches, wavelength-header caches and a few requested prepared sequences.
- Implemented a 3D spherical-cap R-tree, exact convex spherical-footprint intersection, normalized query-snapshot membership, and explicit regional completeness/freshness. Migration used existing metadata only.
- Implemented versioned `/api/v1` metadata/coverage/options/targets interfaces, chronological cursor pagination and observation detail; explicit sequence POST/status and cached artifact routes; OpenAPI contract and interactive `/api/docs`.
- Public metadata GETs support CORS. The running service still needs its final source restart/browser check; no public internet hosting is enabled.
- 35 Python tests and 29 fixture-backed frontend option regressions pass. Remote image transfers are denied in the regression/benchmark harness.
- Saved the initial 20-repeat local HTTP latency baseline. Its uncovered-region archive requests took about 91 seconds each and returned incomplete coverage; no images were downloaded. Added a 12-second per-metadata-request timeout and failure cooldown, currently under repeat measurement.
- Found and corrected SQLite's choice to join the release filter before the spatial index. The verified query plan now uses all six R-tree bounds first. A repeated local spatial microcheck improved from roughly 25 ms median to roughly 14.5 ms; final HTTP distributions are pending and must remain separate from that microcheck.
- JSON responses negotiate gzip. Pixel artifacts remain byte-preserving and expose ETags.
- No all-sky image download, NEP modification, purchases or publication.

## Checkpoint policy

An hourly heartbeat audit is active (`spherex-hourly-scope-checkpoint`). It reads this file and test/latency reports, appends timestamped progress/scope findings, and does not act as a second implementation worker. Existing NEP automation remains untouched.

## Evidence so far

Previous milestone: seven Python tests and three frontend flow regressions; real WISE0855 and Barnard's Star image pairs rendered and cached. Those checks do not yet establish full option/latency coverage or a publicly deployed API.

Current evidence files: `latency-baseline.json`, `latency-baseline-samples.csv`, `frontend-regression-results.json`, and the `test_*.py` / `test_frontend.cjs` suites. The optimized benchmark is running in the current task; do not start a duplicate. No image-processing or bulk-prefetch worker has been started for this milestone.

## Next checkpoint should verify

Finish optimized HTTP measurements, inspect all status/coverage outcomes, run real cached-browser control checks and API-doc request checks, and write the option/latency matrix. Cold image latency, hosted internet latency and scientific detection/PSF/response validation are deliberately unmeasured rather than inferred from cached tests. Record remaining gaps explicitly.

## Hourly audit — 2026-11-14 22:27 UTC / 2026-11-15 03:57 IST

- Reviewed the current progress log, optimized latency report, baseline comparison and frontend regression results. No application source, workers, images or NEP resources were changed by this audit.
- New evidence beyond the earlier progress summary: the optimized HTTP benchmark is complete, covering 42 cases with 20 measured requests each. All returned HTTP 200; completeness remains explicitly false for unindexed/deep/large-field cases. The five target metadata medians are 25.55–42.02 ms, versus 64.51–81.37 ms in the saved baseline. These are sequential localhost measurements, not internet/load guarantees.
- The cold metadata attempt took 12.156 seconds and encountered an IRSA timeout and HTTP 502; coverage remained incomplete. The immediate cooldown repeat took 29.30 ms, with the same explicit errors. Neither request downloaded image pixels. Upstream availability remains a limitation, not evidence of successful new coverage.
- Frontend report contains passing fixture-backed option regressions; their durations are logic-test timings, not real browser latency. The progress log reports 35 Python and 29 frontend tests passing; this audit did not rerun them.
- Remaining requirements: finish and save real cached-browser control/API-documentation checks, write the option/latency coverage matrix and integration guide, and reconcile this progress summary with the completed benchmark. No final completion evidence or browser-latency artifact is present among the latest report files inspected.
- Scope remains aligned with metadata-first spatial selection, versioned APIs, regression/latency evidence and measured optimization. Documentation and browser verification remain open; next corrective step is to finish those checks and reports before declaring completion. No bulk image downloads or public deployment are authorized or needed for this checkpoint.

## Hourly audit — 2026-11-14 23:30 UTC / 2026-11-15 05:00 IST

- Re-read the progress log and newest regression/latency reports. Their evidence is unchanged since the prior audit; only the audit log itself has a newer timestamp. No new completion claim is justified.
- Completed evidence remains 42 local HTTP benchmark cases with 20 measurements each, five target metadata medians of 25.55–42.02 ms, and the previously reported 35 Python / 29 fixture-backed frontend passing checks. No tests or benchmarks were repeated for this audit.
- Open work remains cached-browser/API-doc verification, the option/latency matrix, integration guide and final progress reconciliation. Cold image preparation, hosted latency, concurrent load and scientific validation remain unmeasured. Archive timeout/502 and incomplete regional coverage remain explicit limitations; cache freshness is not independently refreshed by this audit.
- No new blocker or scope divergence was evidenced. There is no new implementation evidence during this interval. Next step remains finishing the outstanding verification/documentation before marking the agreed work complete. This audit neither starts another worker nor changes application source, images, NEP resources, deployment or automations.

## Hourly audit — 2026-11-15 00:31 UTC / 06:01 IST

- Inspected the current progress log and latest regression/latency artifacts. No new implementation, test, benchmark or completion artifact has appeared since the previous audit; the evidence remains unchanged.
- Recorded evidence remains 42 sequential localhost HTTP cases (20 measurements each), target metadata medians 25.55–42.02 ms, and previously reported 35 Python / 29 fixture-backed frontend passing tests. These measurements do not establish actual browser, internet-hosted or cold image latency.
- Outstanding work remains cached-browser controls/API-doc checks, the option/latency matrix, integration guide and final progress reconciliation. Archive timeout/502 failures and incomplete regional coverage remain limitations; this audit has neither refreshed catalogue freshness nor inferred completeness or scientific validation.
- No new blocker or scope divergence is evidenced. Progress has no new supporting artifact during this interval. The next step remains completing the outstanding verification/documentation within the four agreed requirements before claiming completion. No workers, image downloads, source edits, NEP changes, publication or automation changes were made by this audit.

## Hourly audit — 2026-11-15 01:27 UTC / 06:57 IST

- Reviewed the progress log and newest regression/latency reports. Artifact timestamps and measured results are unchanged since the preceding audit; there is no new evidence of implementation progress or completion.
- Completed evidence remains metadata spatial indexing/versioned API implementation described above, 42 sequential localhost benchmark cases with 20 samples each, five target query medians 25.55–42.02 ms, and previously reported 35 Python / 29 fixture-backed frontend passing tests. No repeat tests or network requests were started.
- Still unfinished: actual cached-browser control/API-doc verification, option/latency coverage matrix, integration guide and final progress reconciliation. Cold image preparation, hosted latency, concurrent load and scientific validation remain unmeasured. Incomplete regions, archive timeout/502 failures and cache-freshness provenance must remain explicit; this audit did not refresh metadata.
- No new scope divergence or actionable blocker is evidenced. The implementation has no new supporting artifact during this interval; the next step remains completing outstanding verification/documentation before marking the agreed requirements complete. This checkpoint changed only this audit log: no image downloads, application-source edits, duplicate workers, NEP changes, publication, purchases or automation changes.

## Hourly audit — 2026-11-15 02:33 UTC / 08:03 IST

- Read the progress log and latest latency/frontend regression reports. Results and non-audit artifact timestamps remain unchanged; no new completion evidence is available.
- Evidence remains 42 sequential localhost HTTP benchmark cases (20 measured requests each), five target metadata medians of 25.55–42.02 ms, and previously reported 35 Python / 29 fixture-backed frontend passing checks. No tests, archive requests or image workers were repeated by this audit.
- Outstanding requirements remain actual cached-browser/API-doc verification, option/latency coverage matrix, integration guide and final progress reconciliation. Archive timeout/502 and incomplete regional coverage remain limitations. Cache freshness was not refreshed; cold image preparation, hosted/concurrent latency and scientific validation remain unmeasured.
- Scope remains aligned with metadata-first spatial/chronological selection, documented versioned APIs, regression coverage and measured optimizations. No new blocker or divergence is evidenced. Next corrective step remains finishing the outstanding verification/documentation before any completion claim. Only this checkpoint log was changed; no source, images, NEP resources, automations, deployment or purchases were changed.

## Hourly audit — 2026-11-15 03:29 UTC / 08:59 IST

- Reviewed PROGRESS.md and the newest latency/frontend regression reports. Non-audit artifacts and results are unchanged since the previous checkpoint; completion is not established.
- Existing evidence remains 42 sequential localhost HTTP cases with 20 measurements each, five target metadata medians 25.55–42.02 ms, and previously reported 35 Python / 29 fixture-backed frontend passing checks. These are historical local results, not newly measured browser or internet performance.
- Unfinished work remains cached-browser/API-doc verification, option/latency matrix, integration guide and final progress reconciliation. Archive timeout/502 and incomplete regional coverage remain explicit limitations. Cache freshness was not refreshed, and cold image preparation, hosted/concurrent latency and scientific validation remain unmeasured.
- No new scope divergence or actionable blocker was evidenced. There is no new implementation evidence during this interval. Next step remains completing outstanding verification/documentation before claiming all four requirements complete. This audit only appended this checkpoint; it started no workers or downloads and changed no application source, NEP resources, automations, deployment or purchases.

## Hourly audit — 2026-11-15 04:28 UTC / 09:58 IST

- Read the progress log and newest regression/latency reports. Non-audit report timestamps and results remain unchanged; there is no new completion evidence.
- Evidence remains 42 sequential localhost benchmark cases with 20 measurements each, target metadata medians 25.55–42.02 ms and previously reported 35 Python / 29 fixture-backed frontend passing checks. No measurements were rerun by this audit.
- Unfinished requirements remain actual cached-browser/API-doc checks, option/latency matrix, integration guide and final progress reconciliation. Archive timeout/502 and incomplete coverage remain limitations. This audit did not refresh catalogue freshness; cold image preparation, hosted/concurrent latency and scientific validation remain unmeasured.
- No new scope divergence or actionable blocker is evidenced. The next step remains completing outstanding verification/documentation before declaring the four agreed requirements complete. Only this checkpoint was appended; no image downloads, source edits, workers, NEP changes, automation changes, publication or purchases occurred in this audit.

## Hourly audit — 2026-11-15 05:37 UTC / 11:07 IST

- Read the progress log and latest latency/frontend regression reports. Non-audit timestamps and results remain unchanged; no new completion evidence is present.
- Existing evidence remains 42 sequential localhost HTTP benchmark cases with 20 measurements each, five target metadata medians of 25.55–42.02 ms, and previously reported 35 Python / 29 fixture-backed frontend passing checks. These historical results were not rerun or treated as browser/internet performance.
- Outstanding requirements remain cached-browser/API-doc verification, option/latency matrix, integration guide and final progress reconciliation. Archive timeout/502 and incomplete regional coverage remain limitations. Catalogue freshness was not refreshed; cold image preparation, hosted/concurrent latency and scientific validation remain unmeasured.
- No new scope divergence or actionable blocker is evidenced. Next step remains finishing outstanding verification/documentation before declaring the agreed work complete. This audit appended only this checkpoint and started no downloads or workers; application source, scientific thresholds, NEP resources, deployment, purchases and automations were untouched.

## Hourly audit — 2026-11-15 06:37 UTC / 12:07 IST

- Read the progress log and newest latency/frontend regression reports. Non-audit artifacts and results remain unchanged; no additional completion evidence was found.
- Evidence remains 42 sequential localhost HTTP benchmark cases with 20 measurements each, five target metadata medians 25.55–42.02 ms, and previously reported 35 Python / 29 fixture-backed frontend passing checks. No tests or benchmarks were repeated.
- Still outstanding: actual cached-browser/API-doc verification, option/latency matrix, integration guide and final progress reconciliation. Archive timeout/502 and incomplete coverage remain limitations. Cache freshness was not refreshed; cold image preparation, hosted/concurrent latency and scientific validation remain unmeasured.
- No new scope divergence or actionable blocker is evidenced. Next step remains finishing outstanding verification/documentation before declaring the four agreed requirements complete. This audit changed only this checkpoint log; no image downloads, source edits, workers, NEP changes, publication, purchases or automation changes occurred.

## Hourly audit — 2026-11-15 07:33 UTC / 13:03 IST

- Read PROGRESS.md and the newest latency/frontend regression reports. Non-audit artifact timestamps and results remain unchanged; no new implementation or completion evidence was found.
- Existing evidence remains 42 sequential localhost HTTP cases (20 measurements each), five target metadata medians 25.55–42.02 ms, and previously reported 35 Python / 29 fixture-backed frontend passing checks. This audit did not repeat tests or measurements.
- Outstanding work remains actual cached-browser/API-doc verification, option/latency coverage matrix, integration guide and final progress reconciliation. Archive timeout/502 and incomplete regional coverage remain explicit limitations. Catalogue freshness was not refreshed; cold image preparation, hosted/concurrent latency and scientific validation remain unmeasured.
- No new scope divergence or actionable blocker is evidenced. Next step remains completing outstanding verification/documentation before declaring all four agreed requirements complete. This audit appended only this checkpoint; no image downloads, application-source edits, workers, NEP changes, publication, purchases or automation changes occurred.

## Hourly audit — 2026-11-15 08:40 UTC / 14:10 IST

- Read the progress log and latest latency/frontend regression reports. Non-audit artifacts and results remain unchanged since the preceding checkpoint; no new implementation or completion evidence is present.
- Evidence remains 42 sequential localhost HTTP benchmark cases with 20 measurements each, five target metadata medians 25.55–42.02 ms, and previously reported 35 Python / 29 fixture-backed frontend passing checks. No tests or benchmarks were repeated by this audit.
- Outstanding requirements remain actual cached-browser/API-doc verification, option/latency matrix, integration guide and final progress reconciliation. Archive timeout/502 and incomplete regional coverage remain limitations. Cache freshness was not refreshed; cold image preparation, hosted/concurrent latency and scientific validation remain unmeasured.
- No new scope divergence or actionable blocker is evidenced. Next step remains completing outstanding verification/documentation before declaring the four agreed requirements complete. This audit changed only this checkpoint log; no image downloads, source edits, workers, NEP changes, publication, purchases or automation changes occurred.

## User-requested navigation update — 15 November 2026

Added six top tabs: Find sky images, Blink & timeline, Compare images, Catalogue overlays, Data & downloads, and Developer API. Each has contextual instructions; the same loaded canvas/sequence persists across navigation. Keyboard arrows/Home/End navigate tabs with selected-state and focus support. Verified all six panels in the running browser using the cached Barnard sequence, confirmed the frame/date survives tab changes, and stepped to the second frame inside Playback. Saved feature-tabs.jpg. Existing 29 frontend option regressions pass after the markup change. No archive pixels were requested for this update. The broader outstanding verification/documentation from the earlier milestone remains open.


## Input validation and first-visit guidance — 15 November 2026

User-requested update complete: coordinate bounds/finite/required checks, supported field/target/detector/sequence/sample checks, valid calendar dates and date ordering, listed playback/comparison/overlay choices, slider limits, and saved job-ID format. Invalid searches/preparations are blocked with visible accessible messages; API-side existing validation remains in place. API documentation form also has coordinate bounds. Advanced detector/date/sequence/sample controls moved into a modal opened at the top right; Close/Escape retain edits without running preparation. Basic search includes units, examples and a first-visit three-step workflow.

Added web/guide.html with seven actual screenshots locating the six tabs and Advanced settings, instructions for each control, plus ten limitations with examples and practical next steps. Main viewer links the guide prominently and includes shortcomings examples. Observation table can be expanded in Data to reduce clutter. Verified browser RA=360 rejection and invalid date order with visible error messages, corrected settings, and restored the real cached Barnard sequence; guide advanced image loaded successfully. No archive images downloaded during this work. Saved beginner-viewer.jpg and input-error-example.jpg.

Validation evidence: 27 pure input-validation cases and 29 existing frontend option regressions pass. Updated the saved-job frontend fixture to use a valid 24-character ID so it tests the production URL format. These are logic checks, not new latency measurements. Broader pre-existing cold-image/hosted/load/scientific-validation gaps remain explicit.


## WISE0855 10-arcminute preparation correction — 15 November 2026

Reproduced the reported failed six-candidate request from its saved request.json. Five candidates had no compatible wavelength pair; one did not contain the target centre in native WCS despite field overlap. Implemented cache-informed selection before time sampling: inspect the full bounded detector/date metadata pool using only saved headers, exclude known centre failures, and prefer an existing compatible group. No wavelength thresholds changed; no mixed-wavelength fallback is silently enabled. Explicit versioned API selections remain explicit.

Real metadata-only reproduction: 43 D4 candidates, 11 successful cached wavelength probes, one native-centre exclusion, 31 unknown headers not fetched, two known matched observations selected. Added visible pool/check/exclusion/selection counts and clearer no-pair errors; header failures now update the running skipped count. 38 Python tests, 29 frontend regressions and 27 input-validation checks pass. New real 10-arcminute verification job c58dd63fa183bd674babcfab requests only these two cutouts; first FITS saved (889,920 bytes), second transfer underway. Completion must be verified before claiming image success. See WISE10_FIX.md and wise10-selection-result.json.



## Corrected archive-to-viewer scope — 2026-11-15 16:55 IST

The user clarified that this is a public NASA challenge submission, with all overlapping records retrievable on demand, not a cache-limited local demo. Removed wavelength-based record discarding and silent product deduplication. All 277 returned WISE0855 records are paginated, selectable and individually inspectable. Continuous numeric diameters 1–60 arcminutes, real partial cutouts, common-stretch aggregation and explicit exploratory spatial mosaics are implemented. Metadata completeness is still not an all-sky claim.

A persistent field-scoped download is actually running for all 277 WISE0855 records at 10 arcminutes. Job `9dc8d6d7fc573c36c301e9d6`; latest snapshot {'prepared': 13, 'failed': 0, 'loading': 1, 'pending': 263}. Read the live journal `work/viewer-cache/field-jobs/9dc8d6d7fc573c36c301e9d6.json` at subsequent checkpoints rather than repeating this snapshot. Do not start a duplicate worker. Source outcomes, current sequence ID and stop/resume state are saved there. Browser closure does not cancel the controller; server restart requires explicit resume. The user authorized these field-specific image downloads; this does not authorize all-sky science-image prefetch.

Verified new D1 and D6 cutouts beyond the original D4 pair, growing eight-frame playback, real 10-arcminute products, a selected spatial mosaic, all-record pagination and reload preserving batch_id. Tests: 50 Python, 29 frontend logic, 27 input validation passing. The 277-record audit took approximately 1.52 seconds in one localhost sample; cold image transfer still takes minutes. This is not a hosted latency/load result.

The all-sky metadata importer is implemented but both SIA attempts and a TAP fallback returned HTTP 502; zero global partitions completed. Do not claim the original complete-metadata requirement achieved. Public deployment/container/load tests and scientific per-epoch mosaic validation remain unfinished. Source/host portability changes are included in HOSTING.md, without publication. Current evidence and limitations: ARCHIVE_WORKFLOW_REPORT.md; actual job snapshot: wise0855-field-download-job.json; screenshots: field-records-live.jpg and wise0855-10arcmin-live.jpg.


## User steering: archive IMAGE as default — 2026-11-15 17:16 IST

Default display now reads calibrated archive IMAGE pixels without ZODI subtraction, quality-flag masking or additional PSF/ePSF processing. Geometric alignment and common display stretch remain. Existing analysis products are preserved and available only through an explicit Advanced settings source choice; raw mode does not fall back to them. The previous viewer did not apply an ePSF model. This is not a claim to expose uncalibrated detector telemetry.

A separate lightweight display renderer reads cached FITS and writes only new raw-display products/arrays; archive_downloads=0, recorded errors=0. The field download and NEP process were not stopped or restarted. Current field journal snapshot: {'prepared': 33, 'failed': 0, 'loading': 1, 'pending': 243}, state=running. Check the journal for fresh counts. The raw display itself does not solve archive-transfer latency; no unmeasured speed-up is claimed.

Verification: 54 Python tests, 29 existing frontend checks, 4 additional raw-display regressions, 27 input-validation cases pass. Actual browser source selector, playback, provenance and screenshot verified. See RAW_DISPLAY_REPORT.md, raw-display-status-snapshot.json and archive-image-display.jpg. All-sky metadata ingestion and hosted-load verification remain unfinished as previously recorded.

## Hourly audit — 2026-11-15 11:48 UTC / 17:18 IST

- Read the latest progress, raw-display report, frontend regression report, field-audit timing and live journals. The user's later instructions authorize this one field's 277 cutouts and prefer archive IMAGE display while preserving existing analysis products/other processing. They do not authorize all-sky science-image prefetch. This is an authorized scope clarification, not scope drift.
- Field job 9dc8d6d7fc573c36c301e9d6 remains running: 35 prepared, 0 failed, 1 loading, 241 pending (277 requested). This is ordinary progress from the recently reported 33, not completion. No duplicate worker or retry was started by this audit.
- Raw display renderer reports zero errors and zero archive downloads. Its default uses calibrated IMAGE with sky alignment/common stretch, without additional PSF/ePSF processing, ZODI subtraction or quality masking. Existing analysis products remain separate and opt-in; raw is not uncalibrated detector telemetry or a validated variability measurement.
- Latest recorded verification remains 54 Python tests, 29 existing frontend checks, 4 raw-display regressions and 27 input checks. The local 277-record audit was one 1,523.54 ms request with zero pixel/header downloads. The older latency distributions are unchanged; no cold-transfer or hosted/load speed-up is established by the display change. No tests or benchmarks were repeated by this audit.
- Unfinished requirements remain completion/review of this field job, full all-sky metadata ingestion (still upstream_failed after HTTP 502; zero global partitions completed), public deployment/container/load verification and scientific per-epoch mosaic validation. Freshness/completeness must remain scoped to recorded snapshots, not inferred from cached records.
- No new actionable blocker or divergence is evidenced. Next steps remain observing the existing journal, reviewing per-record outcomes and resolving metadata service availability/hosted verification before a submission-ready claim. Only this checkpoint log was changed; no source, scientific thresholds, NEP resources, downloads, publication, purchases or automations were changed by the audit.


## Evidence and reproducible notebook additions —15Nov2026
User in NEP chat authorized implementing discussed discovery-evidence additions in this viewer, testing5namedfields first. Added web/evidence.js, independentstatic panel, no serverrestart or datarecipechange. Pairmetadata screening,inspectpairhandoff,sharepairURL,evidenceJSON,fieldreadiness. All5cacheonlyAPIqueries passed; coverage incompleteexplicit. Notebook web/reproduce.ipynb executed4codecells0errors; offline realanalysisPNGbundle included, distinctfromdefaultarchiveIMAGE.29frontend+27input+8evidencechecks passed. Browser pairselection,warnings,copylinkverified; screenshot evidence-panel.jpg. Existing277fielddownload preserved. RW Aur2framejobc6a532216847ad74618c90b1 underway; R Dra waitingqueue, boundedcompletion helper work/finish_challenge_evidence.py session73976 holdsOSlock and recordsjournal,doNOTduplicate. No validatedmotion/variability orNEPscienceclaim. Read EVIDENCE_ADDITIONS.md.

## Explicit user pause — 15 November 2026

User requested pausing all current work. The field download stopped after its current cutout with 57 observations prepared. The separate raw-display renderer was stopped. Saved products and journals remain intact. The viewer server is left idle for inspection; the separate NEP process was not stopped or modified. No further implementation or downloads should start without a user request to resume.



Five-target image preparation check completed: RW Aur and R Dra two-frame jobs complete without skipped frames; decoded at least2actualcachedanalysisPNGs for each ofall5challengefields and recorded dates/wavelengths in web/challenge-validation.json. Mixedwavelengths remain explicit; no calibratedvariability/motion detection. Current matchedpreview pairs fornewvariablefields insufficient for same-wavelength claims. SPLICESchemistry/newnotebooks userdiscussion only, notyetimplementationauthorized.


## Galaxy Evidence Lab checkpoint —15Nov2026
Latestuserexplicitlyresumes scopedfivefieldchecksandGalaxyLab; earlier277fielddownloadpauseisNOTrevoked. Fivefieldreadyexamplelinks nowintheviewerreadinesssection. Added galaxy-lab.html,executed galaxy-lab.ipynb,22.6MBgalaxy-example.zip with561measurementCSV/actual4096sampleconditionedoperators/provenance/opticaloverlays/residualpanels. Headerlinkadded. Notebookend-to-endsteps distinguish completedconditionalstages vsunvalidatedscience; reusableoptinnativecell requires explicitnewcatalogue,exposures,calibration,sciencecodepaths. LegacyDR9shape/skypositions,PMconvention,WCS,ePSF,gain/variance,mask,skyfit,responseintegrationallrecorded. Gaia/Euclidnotuniversaladopted. Redshift/distanceunavailablependinggates. Existing29frontend27input8evidencechecks passed, kernelbundleintegritypassed, browserpage/provenanceverified. Checkpoint evidence/galaxy-lab-checkpoint.json. No NEPfits/models/originals changed.

Notebook finalverification: all6codecells executed0errors. Detectedperformancebug during execution: repeatedly accessing compressedNPZarrays decompressedwholeoperators permeasurement; cachedarraysonce andvectorizedflatresponseintegration, completeexecution~6seconds. Generatorupdatedtopreservefix. Offlinebundle561responseoperators normalized. New-targetnativecell remainedRUN_NATIVE=False and is documented as untested onnewtarget, not falselyclaimedcompletee2escience. Redshiftgate remainsopen.


## Two viewer modes / exact-state / reproducible notebook checkpoint
Implemented view-state.js and view-controls.js: time-mode eligible response/epochgroups,colour-modewavelengthordering,framefilters,empty-selectionguards,strictversionedviewvalidation. Sharedlinksrestore14checkedsettings+frameIDs/currentframe/tab/evidencepair; playbackpaused. Browserverifiedall5challengefields,positiveWISEtimepair,colorplaybackall,explicitnegativeother4,noeligiblepair=disabledtimeplayback; exactcontrolsroundtriptrue;coadd/differencerestorationtrue;invalidversionrejected. Sourcepolicylabelsrestored,unsupportedfilteredcachedproductsrejected.54backend+39newstate+29existingfrontend+27input+8evidencechecks pass. Earlier sandboxblocked15HTTPtests; rerunwithlocal-socketpermission54/54passed. Newreproduce.ipynb6codecells executedofflineandcached-serverliveinparallel,GF/CSV/JSON/PNG/ZIPoutputsverified, bounded4frames/8MBpreviews,noPREPARE/newnativefetchinverification. TwoindependentJSONcheckpoints and CHECKPOINTS.mdsaved. FivefieldreadinesspolicyalignedwithtimeUI. Creditsretained. No unsupportedobjectbrightnessplots/no sciencegate/redshiftclaims.277fielddownloadstillstopped57; userdidnotresume bulk.

WISE0855 5arcmin job0d801365673b34d0d579cf78 blank-frame fix: analysis manifest had8frames but raw/manifest.json absent. Rendered from cached IMAGE cutouts; no archive downloads. Restored OS-locked raw_previews --watch --server-url http://127.0.0.1:8765 watcher PID17868; server existing startup code already contains watcher for future restarts. Browser exact user URL verified frame1/8 then2/8 with image visible, screenshot wise0855-render-recovered.png. Added explicit empty-selection message and Show available infrared images recovery for unrelated no-time-pair case;39selection tests pass. Bulk-download pause preserved.
