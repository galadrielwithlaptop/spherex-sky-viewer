# Fly.io deployment

Status: configuration prepared; not yet authenticated, built or deployed.

The Docker build context permits only Python source, requirements and web assets.
It excludes local caches, evidence, environments and credentials. Local images are
not automatically uploaded. The persistent /data volume starts empty.

## Deployment from PowerShell

Use the downloaded CLI at the workspace's work/flyctl/flyctl.exe, or install
flyctl using Fly's official instructions. Run from this viewer source directory.

1. Run `flyctl auth login` and complete Fly's browser sign-in. Configure billing
   in Fly's dashboard yourself; do not share a password or API token in chat.
2. Choose a globally unique app name and run `flyctl apps create YOUR-APP`.
3. Add `app = "YOUR-APP"` at the top of fly.toml and add this entry under [env]:
   `SPHEREX_ALLOWED_HOSTS = "YOUR-APP.fly.dev,localhost,127.0.0.1"`.
4. Create persistent storage:
   `flyctl volumes create spherex_data --region iad --size 10 --app YOUR-APP`
5. Deploy one machine using Fly's remote builder (local Docker is unnecessary):
   `flyctl deploy --remote-only --ha=false --app YOUR-APP`.
6. Inspect `flyctl status --app YOUR-APP` and `flyctl logs --app YOUR-APP`.
7. Open https://YOUR-APP.fly.dev/api/health and the main viewer. Verify metadata,
   a first real frame, raw preview, field status polling and a restart before
   describing the deployment as tested. Check memory under a larger sequence.

This configuration deliberately disables automatic stopping because the current
image worker runs inside the web process. One machine owns the SQLite database
and job journals. It is not a redundant or horizontally scaled deployment.
Compute, storage, backups and traffic can incur charges.

## Preparing the five target fields

For WISE0855, Barnard's Star, Epsilon Indi B, RW Aurigae and R Draconis:

1. Choose the target and field diameter, then Find observations. Review coverage
   and the actual number of matching archive products for that field.
2. Use the records table's load-all action to submit the field job. It attempts
   every selected observation, progressively exposing the prepared timeline.
3. Inspect prepared/failed counts and each failure reason. Resume explicitly if
   a job pauses after three consecutive failures. Run one target at a time;
   the current backend accepts only one active field download.
4. Repeat for the other four targets. Counts vary with target, diameter,
   collection, detector, date and archive coverage. 277 is not a universal count.

The server downloads native image regions on demand, then generates aligned
display previews. Raw display means the archive IMAGE values, not ePSF fits;
alignment and PNG rendering still happen. It does not mean the browser displays
a full FITS detector file directly. Different wavelengths are labelled and are
not automatically comparable measurements of brightness change.

Important current limitation: field_jobs.py has a hard-coded 512 MiB product
guard, alongside other bounded caches. A 10 GB Fly volume does not increase this
application guard. Do not promise that all five complete fields will remain
cached until their sizes are measured and the storage policy is updated. Full
original FITS mirroring is a separate workflow, not implemented by Load all.

An empty deployment must fetch archive metadata or import a consistent database
backup. The local regional index is not a completed all-sky catalogue. Archive
outages remain possible; failures must stay visible rather than becoming blank
frames or fabricated counts.

Official references:
- https://fly.io/docs/flyctl/install/
- https://fly.io/docs/reference/configuration/
- https://fly.io/docs/volumes/overview/
