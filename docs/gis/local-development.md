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
uvicorn gis.api.app:app --host 127.0.0.1 --port 8000
gis-telemetry send --write-key local-development-only \
  --event page_view --page-path /va-loan-calculator/
```

Production browser code should send to a VAHomeMath same-origin server route, which forwards to
GIS with the private write key. See [first-party telemetry](first-party-telemetry.md).

If port 5432 is already in use, start with `GIS_DB_PORT=55433 docker compose up -d db`
and update the port in `.env` before loading it.

The seed command creates VAHomeMath tenant, organization, site, and primary domain records and
the 16 provider definitions. It is safe to rerun and never runs on application startup. The
hostname flag is explicit so a confirmed production hostname can replace the default without a
schema change. No provider credentials are seeded. All sources receive a conservative shared
`UNKNOWN` rights policy until their licenses are reviewed.

This repository currently has no web application process to start; it is a database foundation.
Future application packages should consume `gis.db.session_factory` and add their own run command.

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
