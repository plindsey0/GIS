# Local PostgreSQL development

## Prerequisites

- Docker with Compose
- Python 3.9 or newer (Python 3.12 is used in CI and recommended)

No credentials are committed. The Compose password is development-only.

## First-time setup

```bash
docker compose up -d db
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
set -a && source .env && set +a
alembic upgrade head
gis-seed --hostname vahomemath.com
```

For a new checkout, the dependency portion can instead be run with the idempotent bootstrap:

```bash
scripts/bootstrap-local.sh
```

The bootstrap creates `.venv` when missing, installs GIS in editable mode, and installs the exact
Workbench dependencies from its lockfile.

## Start the API and Workbench

Use the checked-in launcher from the repository root:

```bash
set -a && source .env && set +a
alembic upgrade head
scripts/dev-workbench.sh
```

The launcher verifies that `gis` imports from this checkout's `src/gis`, exports the root
environment, pins the API proxy to `http://127.0.0.1:8001`, starts the API on loopback port 8001,
starts the Workbench on loopback port 3001, and starts the combined scheduler/worker. All children
are supervised: if one exits, the launcher stops its siblings. The executor writes leased scheduler
and worker heartbeats and performs bounded, idempotent startup catch-up. Port 8000 is intentionally
not used because it can belong to another local project.

System reports an executor as `RUNNING` only while its lease is current. A process that stops
updating its heartbeat becomes `OFFLINE` after lease expiry; an enabled schedule alone is not proof
that collection is running. A pipeline whose first due time is still in the future displays the
neutral `AWAITING_FIRST_SCHEDULED_RUN` state and does not count as needing attention.

Inspect local automation without querying PostgreSQL:

```bash
gis-orchestrator liveness
gis-orchestrator obligations --tenant vahomemath --overdue
gis-orchestrator status --tenant vahomemath
```

Next development and production builds use separate `.next-dev` and `.next-build` directories.
This makes `npm run build` safe while the development server is running because neither process
can rewrite the other's chunk manifest. If a prior checkout left legacy artifacts, clear only
generated frontend caches with:

```bash
cd apps/workbench
npm run clean:cache
```

Cache clearing is a recovery/clean-validation step, not a requirement for every startup.

## GA4 collector

After seeding, configure a GA4 connection with a secret reference, validate access, and sync:

```bash
gis-ga4 configure --tenant vahomemath --site vahomemath \
  --property-id 123456789 \
  --credential-reference env:GA4_SERVICE_ACCOUNT_JSON
gis-ga4 validate --connection <connection-uuid>
gis-ga4 sync --connection <connection-uuid> --recent-days 3 --dataset all
```

See [GA4 integration](ga4-integration.md) for OAuth, explicit backfills, report definitions, and
recovery behavior. No GA4 credential is required for the automated test suite.

## First-party telemetry API

```bash
export TELEMETRY_WRITE_CREDENTIAL='{"write_key":"local-development-only"}'
gis-telemetry configure --tenant vahomemath --site vahomemath \
  --credential-reference env:TELEMETRY_WRITE_CREDENTIAL
uvicorn gis.api.app:create_app --factory --host 127.0.0.1 --port 8001
gis-telemetry send --write-key local-development-only \
  --event page_view --page-path /va-loan-calculator/
```

Production browser code should send to a VAHomeMath same-origin server route, which forwards to
GIS with the private write key. See [first-party telemetry](first-party-telemetry.md).

## Analytical models

```bash
cp analytics/profiles.yml.example analytics/profiles.yml
export DBT_HOST=localhost DBT_PORT=5432 DBT_USER=gis DBT_PASSWORD=gis DBT_DATABASE=gis
dbt debug --project-dir analytics --profiles-dir analytics
dbt build --project-dir analytics --profiles-dir analytics
dbt test --project-dir analytics --profiles-dir analytics
dbt docs generate --project-dir analytics --profiles-dir analytics
```

Use `DBT_PORT=55433` when following the alternate Compose-port example. dbt owns only the three
derived analytical schemas; run Alembic migrations before dbt. Generated dbt artifacts are ignored.

## Growth Dashboard

After the analytical models build, set local Metabase admin credentials in `.env` and run:

```bash
set -a && source .env && set +a
docker compose up -d metabase
python dashboard/provision.py
```

Open `http://localhost:3030`. See [Growth Dashboard](growth-dashboard.md) for architecture,
filters, source mappings, missing-data semantics, security, and troubleshooting.

If port 5432 is already in use, start with `GIS_DB_PORT=55433 docker compose up -d db`
and update the port in `.env` before loading it.

The seed command creates VAHomeMath tenant, organization, site, and primary domain records and
the 16 provider definitions. It is safe to rerun and never runs on application startup. The
hostname flag is explicit so a confirmed production hostname can replace the default without a
schema change. No provider credentials are seeded. All sources receive a conservative shared
`UNKNOWN` rights policy until their licenses are reviewed.

The GIS API and Workbench are started together with `scripts/dev-workbench.sh`. Domain services
continue to consume `gis.db.session_factory`; the web layer does not introduce a parallel database
configuration.

## Google Search Console

After placing service-account JSON in an environment variable and granting that account access
to the exact Search Console property:

```bash
export GSC_SERVICE_ACCOUNT_JSON="$(< /secure/path/gsc-service-account.json)"
gis-gsc configure \
  --tenant vahomemath \
  --site vahomemath \
  --property-uri sc-domain:vahomemath.com \
  --credential-reference env:GSC_SERVICE_ACCOUNT_JSON
gis-gsc validate --connection <connection-uuid>
gis-gsc sync --connection <connection-uuid> --recent-days 3
```

The secret value is never stored in PostgreSQL. See [GSC integration](gsc-integration.md) for
OAuth credentials, URL-prefix properties, optional dimensions, and backfills.

## Migrations

```bash
alembic upgrade head
alembic downgrade -1
alembic current
alembic check
```

Migrations are deterministic, checked into `migrations/versions`, and reversible. Set
`DATABASE_URL` to target a database other than the Compose default.

## Tests and checks

Create the test database once (the Compose service creates only the development database):

```bash
docker compose exec db createdb -U gis gis_test
```

Then run:

```bash
source .venv/bin/activate
ruff check .
ruff format --check .
mypy
pytest
python -m build
```

Tests migrate `gis_test` from empty to head and downgrade it after the suite. Override its URL
with `TEST_DATABASE_URL`. Never point `TEST_DATABASE_URL` at a database containing useful data.
