# All-sky spectral-image metadata index

## Scope and current state

The metadata importer covers four currently searchable spectral-image collections:
SPHEREx DR1/QR3 wide and deep. It does not enumerate every calibration file, the
DR1 all-sky cube, unsearchable historical QR2 files or future unpublished releases.

At setup on 15 November 2026, the VM's day-sized and smaller SIA queries and a TAP
probe timed out. The existing regional database contained 2,050 records. A
separate retrying metadata worker was started, but this is not evidence of a
completed all-sky import. Read its current status before making coverage claims.

## Data flow

1. SIA queries return image metadata only: sky footprint, time, detector, release,
   wavelength bounds, archive URL and identifiers.
2. Overflow responses split time intervals; broad queries that time out can also
   split. Failed intervals stay pending. Small failed intervals rotate so other
   collections can advance. Retries back off rather than dropping failed records.
3. Each successful interval is ingested into the existing SQLite index. A
   generation becomes authoritative only when all its intervals complete.
4. Coordinate searches use the spherical spatial index and exact footprint
   checks. Until local coverage is established, live regional metadata discovery
   remains necessary for reliable completeness and freshness claims.
5. Images are fetched separately, only for requested/prepared observations.
   Cached prepared fields are reused. Importing metadata does not download FITS
   science pixels, wavelength headers, ePSFs or ZODI arrays.

The worker covers a recorded acquisition-time interval ending at its start time.
Late archive ingestion and future releases require later reconciliation. The
worker exits after completing that interval; it is not a perpetual promise that
every subsequent weekly release has been synchronized. Refresh queries remain
available separately. An incremental update strategy must preserve late arrivals
and reprocessing rather than assuming acquisition time equals publication time.

## Run and inspect

Local Docker setup:

```sh
docker compose -f compose.yaml -f compose.metadata.yaml up -d --build
docker compose -f compose.yaml -f compose.metadata.yaml logs -f metadata
```

The hosted VM uses a separate container named `spherex-metadata-sync`, sharing
`/opt/spherex/data` with the viewer. It has a 512 MiB memory ceiling and half a CPU.
The metadata database budget is configured to 8 GiB; a 4 GiB free-disk reserve
also stops import. Storage limits leave unfinished work pending.

Public progress endpoint:

https://srv2163798.hstgr.cloud/api/v1/catalogue-sync

Interpret its fields:

- `status`: running, retrying_smaller_partition, upstream_failed,
  paused_at_request_limit, storage_limit, or complete_for_time_interval.
- `completed_partitions`: successfully consumed complete metadata responses.
- `returned_records`: imported response rows; overlaps can repeat an observation,
  so this is not the number of unique catalogue records.
- `pending`: intervals still requiring successful complete responses.
- `pixel_downloads` and `header_downloads`: zero for this metadata-only workflow.

`complete_for_time_interval` is meaningful only for the declared collections and
time interval. Zero results during failure are not proof of no observations.

Official archive reference:
https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/
