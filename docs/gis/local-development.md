# Local PostgreSQL development

## Prerequisites

- Docker with Compose
- Python 3.9 or newer

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

If port 5432 is already in use, start with `GIS_DB_PORT=55433 docker compose up -d db`
and update the port in `.env` before loading it.

The seed command creates VAHomeMath tenant, organization, site, and primary domain records and
the 16 provider definitions. It is safe to rerun and never runs on application startup. The
hostname flag is explicit so a confirmed production hostname can replace the default without a
schema change. No provider credentials are seeded. All sources receive a conservative shared
`UNKNOWN` rights policy until their licenses are reviewed.

This repository currently has no web application process to start; it is a database foundation.
Future application packages should consume `gis.db.session_factory` and add their own run command.

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
mypy
pytest
python -m build
```

Tests migrate `gis_test` from empty to head and downgrade it after the suite. Override its URL
with `TEST_DATABASE_URL`. Never point `TEST_DATABASE_URL` at a database containing useful data.
