# Regression latency report

Monotonic end-to-end local HTTP request through complete response read; 1 warmup per route; no concurrent load.

20 measured requests per case; all image artifacts were already cached. No new archive images were requested.

| Case | Status | p50 ms | p95 ms | Bytes sent | Coverage complete |
| --- | ---: | ---: | ---: | ---: | --- |
| target WISE0855 | 200 | 31.26 | 36.15 | 122308 | True |
| target Barnard's Star | 200 | 25.55 | 41.48 | 121660 | True |
| target eps Ind B | 200 | 42.02 | 49.77 | 122191 | True |
| target RW Aur | 200 | 26.55 | 45.09 | 121451 | True |
| target R Dra | 200 | 39.32 | 64.75 | 121404 | True |
| detector 1 | 200 | 30.79 | 38.33 | 55394 | True |
| detector 2 | 200 | 19.38 | 32.20 | 61359 | True |
| detector 3 | 200 | 19.87 | 40.48 | 56566 | True |
| detector 4 | 200 | 18.03 | 35.60 | 53518 | True |
| detector 5 | 200 | 11.88 | 36.07 | 60662 | True |
| detector 6 | 200 | 17.47 | 34.44 | 55934 | True |
| FOV 1 arcmin | 200 | 25.90 | 40.32 | 122440 | True |
| FOV 10 arcmin | 200 | 23.89 | 41.75 | 122690 | False |
| FOV 30 arcmin | 200 | 23.02 | 33.59 | 122690 | False |
| FOV 60 arcmin | 200 | 26.70 | 35.10 | 122690 | False |
| date interval | 200 | 28.41 | 39.68 | 122314 | True |
| descending order | 200 | 20.21 | 36.15 | 122187 | True |
| collection spherex_dr1 | 200 | 24.68 | 36.77 | 122025 | True |
| collection spherex_qr3 | 200 | 7.01 | 26.82 | 1324 | True |
| collection spherex_dr1_deep | 200 | 17.33 | 32.46 | 1294 | False |
| collection spherex_qr3_deep | 200 | 11.94 | 30.37 | 1294 | False |
| page size 1 | 200 | 18.70 | 38.04 | 2932 | True |
| page size 500 | 200 | 31.65 | 52.94 | 335409 | True |
| gzip metadata | 200 | 34.70 | 50.89 | 18158 | True |
| unknown indexed region | 200 | 16.26 | 30.35 | 1390 | False |
| status | 200 | 5.46 | 24.99 | 547 | None |
| options | 200 | 1.79 | 23.07 | 802 | None |
| targets | 200 | 2.11 | 3.31 | 926 | None |
| known coverage | 200 | 21.09 | 35.95 | 690 | None |
| OpenAPI contract | 200 | 2.89 | 24.92 | 22726 | None |
| API documentation | 200 | 1.80 | 18.66 | 5414 | None |
| gaia overlay metadata | 200 | 15.27 | 23.72 | 41604 | None |
| wise overlay metadata | 200 | 12.26 | 26.37 | 56395 | None |
| cached sequence acceptance | 200 | 7.91 | 31.65 | 226 | None |
| cached sequence status | 200 | 1.93 | 13.54 | 4107 | None |
| cached manifest.json | 200 | 3.27 | 17.38 | 4849 | None |
| cached 0.png | 200 | 9.96 | 21.53 | 30174 | None |
| cached coadd-0.png | 200 | 16.36 | 28.51 | 45051 | None |
| cached difference-0.png | 200 | 1.66 | 17.61 | 45388 | None |
| cached blink-0.gif | 200 | 4.49 | 23.00 | 106497 | None |
| cached aligned.npz | 200 | 16.83 | 24.73 | 69311 | None |
| cached native FITS | 200 | 8.81 | 24.07 | 313920 | None |

## Cold metadata comparison

[
  {
    "elapsed_ms": 12156.087899988052,
    "wire_bytes": 122934,
    "decoded_bytes": 122934,
    "status": 200,
    "server_timing": "app;dur=12122.398",
    "cache": "local_index",
    "coverage_complete": false,
    "phase": "initial_request",
    "collection_sources": [
      "local_index",
      "local_index"
    ],
    "archive_errors": [
      "Archive request failed: curl: (28) Operation timed out after 12011 milliseconds with 0 bytes received",
      "Archive request failed: curl: (22) The requested URL returned error: 502"
    ],
    "retry_after_seconds": [
      60,
      60
    ],
    "pixel_downloads": 0
  },
  {
    "elapsed_ms": 29.298999987076968,
    "wire_bytes": 122934,
    "decoded_bytes": 122934,
    "status": 200,
    "server_timing": "app;dur=27.109",
    "cache": "local_index",
    "coverage_complete": false,
    "phase": "repeat_request",
    "collection_sources": [
      "local_index",
      "local_index"
    ],
    "archive_errors": [
      "Archive request failed: curl: (28) Operation timed out after 12011 milliseconds with 0 bytes received",
      "Archive request failed: curl: (22) The requested URL returned error: 502"
    ],
    "retry_after_seconds": [
      60,
      49
    ],
    "pixel_downloads": 0
  }
]

## Unmeasured

- New image cutout transfer, alignment and first-time sequence preparation (not run: metadata-first/no bulk image fetch scope)
- Internet-hosted service latency and multi-user load (no public deployment authorized)
- Scientific identification, calibrated variability significance and full-response validation