# Data snapshot

This directory contains the searchable regional metadata index and current VM
image products exported on 15 November 2026. `snapshot-summary.json` describes
the five fields. `starter-5arcmin.json` retains per-observation source metadata
and preparation results. `products/starter/index.json` is the published display
catalogue; target sequence IDs point to prepared manifests under `products/`.

There are 141 ready IMAGE cutouts: 89 for WISE0855 and 13 each for the other four targets. The VM backfill was still progressing when this snapshot was captured. Sequence products
also contain derived PNG copies and manifests from progressive publication;
counting all files is not a count of unique archive observations.

The SQLite file was exported using SQLite's backup API. No live WAL, credentials
or process logs are included. Updates should export the database consistently,
publish files before updating manifests, and commit an explicit dated snapshot.
Do not copy a live SQLite database without accounting for its WAL.

The native FITS files here contain extracted IMAGE regions, not full original
detector exposures. Preserve their archive source URLs and processing metadata.
