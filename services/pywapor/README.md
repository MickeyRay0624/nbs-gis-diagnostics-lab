# Online diagnostics and pyWaPOR service

The unified eight-module workspace submits to `/api/analyses`. Its environmental child uses `/api/diagnostics`, the same automatic browser session, and a separate durable queue under `/data/diagnostics`. Its Python 3.12 / NumPy 2 image contains the seven-module engine and checked Ganjam reference inputs. `prepare-build.py` copies the engine and data from the repository into the build context and records their SHA-256 hashes. The diagnostics worker verifies those hashes before becoming ready.

Run `python3 services/pywapor/prepare-build.py` from the repository root before copying or building this service. Deploy all files in the service directory, including `build/`, and preserve `.env` and `data/` on updates. Production code and containers must use matching builds. Diagnostics dependencies are pinned in `requirements-diagnostics.lock.txt`; the short requirements file records the intended direct dependency ranges.

The two workers share `/data/compute.lock`, acquired before claiming a job. This serializes heavy computation across both numerical environments while preserving separate compatible numerical environments. Each worker has a 1.5 GB RAM limit, up to 3 GB total RAM/swap, and one CPU. There must be only one worker for each queue.

All seven Ganjam modules recalculate stored source inputs. New-area flood, degradation, climate, land cover and forest tasks acquire public data. New-area public land inputs use WorldCover 2020 v100 / 2021 v200, with differing map algorithms recorded as a limitation. The online upload path accepts 1–3 user rasters, years, crosswalks, forest definitions and protected/OECM polygon layers. NASA acquisition needs `NBS_NASA_USERNAME` and `NBS_NASA_PASSWORD`. Enable groundwater with `NBS_GLDAS_VERIFIED=true` and vegetation health with `NBS_MODIS_VERIFIED=true`, independently and only after each source passes an authenticated end-to-end run and resource checks. Successful login alone is insufficient. The legacy `NBS_EARTHDATA_VERIFIED` is a fallback only when a per-source flag is absent. The account owner must accept the NASA GESDISC DATA ARCHIVE EULA before GLDAS download. MODIS tasks estimate the selected granules before downloading; oversized tasks explain how to split growing seasons while keeping the 15-year minimum reference. GLDAS acquires authenticated regional GWS_tavg subsets on the native 0.25° grid using at most four HTTP connections. Each response's daily date, coordinates and unit are checked; streamed bytes count against the task budget. NetCDF is decoded serially. Global daily files are not downloaded. The existing Ganjam inputs do not require a fresh NASA login.

Diagnostics enforce an enclosing rectangle ≤20,000 km²; new public land-cover/forest ≤2,000 km² and two million analysis cells; uploaded land cover ≤20,000 km² and eight million analysis cells; boundary ≤190 KB; climate ≤240 annual subset requests; managed downloads ≤10 GB; total task storage ≤12 GB; four-hour runtime; 30-day result retention. If an individual module fails, completed modules are retained and the task is marked `partial`. A worker termination or hard resource limit fails the task without publishing unfinished outputs. The result ZIP contains two-band COGs, statistics, tables, methods and source provenance. Band 1 is the result; band 2 is eligible pixel area in km².

The **Water & productivity** module shares the study-area wizard, task list and results view with the other seven diagnostics. Its child jobs still use the original water queue and result endpoints.
Visitors need only a browser; the workspace opens automatically. The service uses pyWaPOR
3.7.3, SE_ROOT v3 and ETLook v3 in a separate environment from the NbS engine.

The first deployed pilot supports the pinned FAO Fayoum provider inputs for
1–31 July 2021, recomputed for each job. These are satellite/weather product
caches, not precomputed model results. Arbitrary regions remain disabled until
NASA Earthdata, Copernicus Data Space and CDS access are configured and a new-area
run is verified. The model uses the nominal 60 m `WaPOR3_level_2` input grid.

The existing pyWaPOR thermal sharpener fits a `BaggingRegressor` without a fixed `random_state`. Fresh runs are not guaranteed to reproduce earlier pixels exactly. Preserve each result and run manifest; compare source hashes, configuration, coverage and numeric differences rather than assuming byte-for-byte model equality. The v0.7 workflow integration does not modify the scientific pipeline or set a new seed.

## Combined analyses

`online/analyses.py` stores submission intent in `/data/analyses.sqlite3` before creating either child. Child IDs derive deterministically from the parent ID and kind. A background dispatcher resumes incomplete dispatch, including after API restart or temporary queue pressure, without browser polling. Idempotency keys bind to the full validated request. Cancellation is persisted before cancelling both children and survives restarts. Completed outputs remain available if another child fails or is cancelled.

The API enforces one shared geographic boundary. Ganjam reference data cannot be paired with the Fayoum water sample. New-area water can inherit the environmental polygon server-side to avoid submitting large boundaries twice. Existing source-access checks, ownership, origin protection, queue/resource limits and separate scientific environments continue to apply. The unified list also returns legacy environmental and water jobs; no historical queue or result migration is required.

Use one API process with this SQLite dispatcher and one worker per numerical queue. Preserve `/data/analyses.sqlite3`, both existing job databases, session storage and result directories in backups. `GET /api/analyses` returns browser-owned recent analyses; `POST /api/analyses` submits; `POST /api/analyses/{id}/cancel` cancels unfinished children. Per-module result files are still served by the established job endpoints.

## Architecture and limits

```text
Eight-module browser workflow --HTTPS + HttpOnly session--> FastAPI
                                                           |
                                             durable parent analyses
                                                /               \
                                    diagnostics queue       pyWaPOR queue
                                           |                     |
                                    NumPy 2 worker         pyWaPOR worker
                                                \               /
                                                shared compute lock
                                                         |
                                               persistent result files
```

- API and worker share a local persistent data directory. Use exactly one worker
  per directory; a filesystem lock enforces this. Do not put SQLite on NFS or
  scale this deployment across hosts. A multi-host installation should migrate
  the queue to a shared database and results to object storage.
- Each browser workspace sees only its own jobs. An automatic HttpOnly cookie
  restores its history; clearing site data opens a new workspace. Optional
  legacy analyst keys remain server secrets and are never built into frontend assets.
- Limit: 500 km² **enclosing rectangle**, 31 inclusive days, 8 pending jobs total,
  2 pending per browser workspace. A single compute worker serializes jobs.
- The deployment caps API memory at 256 MB and worker memory at 1.5 GB, with up
  to 3 GB combined RAM/swap for the worker and 1 CPU. These are pilot settings
  for a shared 2-vCPU server; benchmark before increasing area or concurrency.
- Jobs have a 4-hour deadline, a storage ceiling, and a free-disk threshold.
  Results expire after 30 days by default. The worker cleans expired job files.
- Queued jobs survive restarts. An interrupted running job becomes failed
  (or cancelled if cancellation was pending); it is not silently resubmitted.
- Submission keys prevent duplicate jobs when a client retries the same request.
  Explicit new submissions run the model again. There is no completed-result cache.
- After saving model output, the pipeline replaces its process before exporting.
  This releases pyWaPOR's retained model arrays and task graphs before loading
  the output again. A first server trial hit the memory limit when both phases
  shared a process; the deployment uses separate process lifetimes.

## Deploy on one Ubuntu host

Copy this directory to an independent application directory. Do not put data,
provider secrets or access codes in a public web root or in Git.

1. Copy `.env.example` to `.env` and give it mode `600`. Enable
   `NBS_PUBLIC_ACCESS=true` to open browser workspaces without an access code.
   Match `NBS_SESSION_COOKIE_PATH` to the public API path and set allowed web
   origins explicitly. Keep the frontend and API on the same HTTPS site.
   Optional legacy keys in `NBS_ACCESS_KEYS` support administrative API access;
   keep them out of source files. Leave `NBS_ENABLE_CUSTOM=false` for the public sample.
2. Run `python3 prepare-build.py` in a full repository checkout, then `docker compose build`. The images install their own compatible Python/GDAL
   environment. Existing host Python installations are not modified.
3. Create `data`, give it mode `700`, and assign it to the image user. For the pinned image that user
   is UID/GID **57439**; verify with `docker run --rm nbs-pywapor:0.4.4 id`.
4. Provision sources once, either from the FAO archive:

   ```sh
   docker compose run --rm --no-deps api python -m online.sample --data /data
   ```

   or mount a previously verified source directory read-only and add
   `--source /source`. The provisioner checks every provider-file SHA-256.
5. Run `docker compose up -d`. API listens only on host loopback port **8021**;
   publish it through the existing HTTPS reverse proxy. Do not expose 8021
   directly to the Internet.
6. Build the NbS frontend with `VITE_NBS_API_URL=https://YOUR_HOST/nbs-api`.
   `NBS_BASE_PATH=/nbs/` supports serving the full platform below `/nbs/`.
   Proxy `/nbs-api/` to `http://127.0.0.1:8021/api/` with the trailing slashes.
   The Pages entry forwards visitors to the deployed online workspace;
   cookie-based browser workspaces require a frontend on the same site as the API.
   Set the origin in `.env` to the actual frontend origin when deploying elsewhere.

For the September 2026 installation, the application is isolated at
`/opt/lmqstudio/nbs-pywapor`, with the platform at `https://lmqstudio.com/nbs/`
and the API at `https://lmqstudio.com/nbs-api`. Existing applications keep their
own compose projects, ports and directories. Nginx route changes are backed up
under `/opt/lmqstudio/backups/nbs-pywapor-*` before reload.

## Provider accounts for custom regions

Set `NBS_NASA_USERNAME`, `NBS_NASA_PASSWORD`, `NBS_CDSE_USERNAME`,
`NBS_CDSE_PASSWORD` and `NBS_CDS_TOKEN` **on the server**. The account owner must
complete provider registration and applicable dataset terms. The worker supplies
credentials through pyWaPOR's account getter without interactive prompts or
writing into site-packages. They are never placed in job payloads or exports.

CDSE's downloader also holds a direct import of the account getter; the worker
configures both references. For NASA VIIRS, complete any Earthdata profile fields
requested by LAADS and authorize LAADS Web once. The worker then uses the official
[EDL find-or-create token API](https://urs.earthdata.nasa.gov/documentation/for_users/user_token)
instead of the interactive OAuth callback. Tokens stay in process memory, are
reused within a job, and are sent only to the HTTPS LAADS data host. Existing
tokens are not revoked. Provider passwords still belong only in the private
server environment; browser visitors do not need their own provider accounts.

The authorization check streams only the response headers. VIIRS geolocation
uses the matching, compressed NASA archive file, downloaded in four verified
byte ranges. Only the original latitude/longitude arrays and attributes are
copied, without spatial subsampling. Thermal observations and cloud masks retain
their upstream OPeNDAP subsets and quality rules. Required source products must
all be present; each prepared provider input's relative path, size and SHA-256
is recorded in the run manifest before modelling.

Before opening custom regions to analysts, perform a controlled small-area run
with a valid historical period and verify acquisition, quality filtering and
outputs. Set `NBS_ENABLE_CUSTOM=true` only as part of that rollout; readiness
checks confirm presence of secrets, not whether a provider will accept them.
Full Ganjam exceeds the pilot area limit: use a smaller test polygon/rectangle.

## Results and scientific interpretation

The API returns `nbs-water/v1`, separate from the existing seven-module
`nbs-step2/v1` catalog. No existing import schema or diagnostic output is changed.
The UI reads one selected period raster at a time, verifies SHA-256 and grid,
and reuses the platform's map projection and time-series components.

- `daily-results.nc`: eight daily variables, with boundary masking and NoData.
- `whole.tif`, monthly and dekadal COGs: nine bands; the last is included pixel
  area in m². All eight physical/model variables remain in downloads; four are
  exposed as primary map layers.
- `daily-summary.csv`, `period-summary.csv`, `run-manifest.json`, source
  configuration, boundary and validation evidence; `results.zip` bundles these.
- ET = E + T. AETI additionally includes interception. Reference ET is retained.
- NPP is gC/m² per daily bin, not crop yield or dry biomass. Relative root-zone
  saturation is dimensionless, not volumetric soil moisture.
- Water/NPP period totals require every daily value at a pixel. Saturation uses
  a complete-period mean. Missing data never become zero. Calendar periods cut
  by the submitted date range are labelled “selected days”.
- Area summaries use WGS84 geodesic pixel areas with a pixel-centre polygon mask.
  They include all land-cover types inside the boundary, without a crop mask.
- Successful software checks do not establish field accuracy, irrigation
  performance or causal effects of an NbS intervention.

## Operation and recovery

Use `docker compose ps` and the public `/api/health` endpoint for API status.
Authenticated `/api/capabilities` also reports worker heartbeat and source
readiness. Stages reflect actual model steps; the UI uses no invented percentage
or completion-time estimate. For a failed task, inspect `data/jobs/ID/private-worker.log`
on the server. It is deliberately not exposed through the API because provider
exceptions may contain sensitive URLs. Successful jobs remove model scratch
data after publishing checked results. Logs remain private until expiry.

Back up the persistent directory and `.env` with restricted access; use SQLite's
backup API for a live database. To stop this feature, run `docker compose stop`
in this directory. Restore the backed-up Nginx configuration to remove routes.
Do not run `docker compose down -v` or delete `data` as a routine update.

## Verification

The deployed host completed a fresh public-input run on 17 September 2026:
job `02699b6794714b40922213b0530e5d5d`, 31 daily bins, 349 × 348 pixels,
15 minutes 26 seconds from submission to checked results. All 27 export checks
passed. The authenticated 88,302,263-byte results archive and its 13 files were
downloaded and checked against SHA-256; all 20 map combinations matched the
browser reader's independently recomputed area-weighted statistics. API restart
during calculation and worker restart after completion preserved the expected
job state and stored results. This is one pilot benchmark, not a run-time promise.

```sh
python -m pip install -r requirements-api.txt -r requirements-diagnostics.lock.txt -r requirements-test.txt
PYTHONPATH=.:../../engine/localprep:../../engine/src python -m pytest tests -q
```

Tests cover automatic browser sessions, legacy-history recovery, task isolation, cookie persistence and expiry, cross-site write rejection, queue limits, CORS, geometry/date/size rejection,
idempotent retries, queue quotas, concurrent claims, cancellation races,
restart recovery, file allowlisting and expiry. The repository's `pnpm test`
also checks client HTTPS requirements, token handling and download checksums.
Run `PYTHONPATH=. python tests/check_result_semantics.py` in the model environment to verify missing-day totals, AOI holes, carbon units and partial calendar periods. Actual model runs and browser acceptance evidence are recorded separately.

Primary implementation references:
[FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/),
[heavy background computation](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat),
[Compose startup ordering](https://docs.docker.com/compose/how-tos/startup-order/),
[FAO public test inputs](https://storage.googleapis.com/fao-cog-data/pywapor_test_data/test_data.zip).

### Access without a code

Set `NBS_PUBLIC_ACCESS=true`, `NBS_SESSION_COOKIE_PATH=/nbs-api`, and `NBS_SECURE_COOKIE=true` for the deployed site. Keep the frontend and API on the same HTTPS site. `POST /api/session` creates or renews a random, HttpOnly, Secure, SameSite=Lax cookie; the persistent session database stores only its SHA-256 digest and task owner. No shared administrator key is embedded in frontend code. Cookie lifetime follows result retention. Clearing site data opens a different workspace. Existing valid session-stored analyst codes are automatically exchanged for a browser session belonging to the same owner, preserving that task history. Existing keys continue to work for administrative API access; new deployments can use `NBS_ACCESS_KEYS={}`. The API default remains restricted unless public access is explicitly enabled. Local HTTP development can set `NBS_SECURE_COOKIE=false` and use cookie path `/api`.

## Private source uploads (v0.8)

`POST /api/diagnostics/uploads?kind=raster|vector&name=...` accepts an authenticated `application/octet-stream` body. This exact route streams a bounded file (100,000,000 bytes for TIFF, 5,000,000 for polygon GeoJSON). Other JSON routes retain the 220 KB request limit and same-origin/session checks. The reverse proxy must allow 100 MB only on the exact public upload route, with a 180-second read timeout. `POST /api/diagnostics/uploads/{id}/discard` releases unused unpinned draft files.

Rasters require a north-up single-band GeoTIFF, ≤25M decoded cells, supported CRS and ≤256 integer source classes. The API inspects in small windows with one inspection at a time. Draft quotas: 350 MB / 20 files per workspace; 2 GB across uploads; 24-hour expiry. Submitted inputs are pinned for result retention +2 days. Files are private and checksummed again by the worker. Crosswalk coverage and ownership are checked before enqueueing. Source TIFFs are not copied into the result ZIP; hashes and metadata are. Selected protection geometries are included.

The uploaded land calculation allows ≤8M analysis cells; public WorldCover acquisition keeps ≤2M cells. Both uses validate an enclosing area cap (20,000 / 2,000 km²). The existing 50 m Ganjam grid is retained by default. Two-band COGs retain NoData and eligible-area weights. New `input-manifest.json`, crosswalk, balance and forest-change CSVs document source definitions and pairwise common coverage. See [method differences](../../docs/method-differences.md).

The exact upload-location example is [nginx-upload.conf.example](nginx-upload.conf.example). Add it alongside the ordinary API route, test with `nginx -t`, then reload. It preserves the small JSON-body limit on other routes.
