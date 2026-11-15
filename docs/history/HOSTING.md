# Hosting and metadata ingestion

The source is intended to serve remote users through the same coordinate APIs and on-demand cutout jobs. Localhost is the development listener, not the product scope. No public deployment has been performed.

A Linux container recipe is included (not built or load-tested in this environment):

    docker build -t spherex-viewer .
    docker run --rm -p 8765:8765 -v spherex-data:/data -e SPHEREX_ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.example spherex-viewer

Put a TLS reverse proxy in front of an authorized public deployment. Set SPHEREX_ALLOWED_HOSTS to the actual domain; SPHEREX_ALLOWED_ORIGINS is available for additional explicitly allowed preparation callers. Persist /data. The existing single-worker queue and local SQLite/R-tree are not a claim of validated multi-user scalability. Hosting, concurrency limits, job durability and quotas need hosted load verification before calling the submission production-ready.

All-sky metadata ingestion, without science pixels or wavelength headers:

    python sync_catalogue.py

This resumes the pending time partitions in the persistent cache. Four current DR1/QR3 wide/deep spectral-image collections are included. Overflow responses split into smaller time partitions; errors retain pending work. The metadata database has a 4 GiB guard. GET /api/v1/catalogue-sync exposes progress. Only a completed ingestion for its recorded time interval can claim that interval was ingested; weekly archive updates require a subsequent incremental interval (not yet automated).

The first live all-sky SIA attempt and an official TAP fallback probe both returned HTTP 502 on 15 November 2026. No all-sky completeness claim is justified. Existing regional metadata remains usable and its own coverage/freshness is separate from ingestion status.
