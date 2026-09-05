# Database safety

## Incident and invariant

On September 4, 2026, a migration-test fixture configured `TEST_DATABASE_URL`, while
Alembic's environment replaced it with inherited `DATABASE_URL`. Session teardown then
downgraded the persistent `gis` development database. The schema was recreated, but local
provider-control history was irreversibly lost. See the [forensic baseline](recovery/2026-09-04-provider-control-incident-baseline.md).

**Never run destructive migration validation against a persistent database.** Destructive
tests now provision a uniquely named `gis_migration_test_<run-id>` database. The harness
requires all of: TEST environment, the exact run-owned database name, an internal run token,
and a database distinct from `DATABASE_URL`. It also denies `gis`, `postgres`, `template0`,
and `template1`. A missing `TEST_DATABASE_URL` fails closed; there is no development fallback.

Safe test invocation:

```sh
set -a; source .env; set +a
export TEST_DATABASE_URL=postgresql+psycopg://gis:gis@localhost:5433/gis_test
.venv/bin/pytest
```

Migration tests create, migrate, identify, exercise, and drop their own ephemeral database.
Their safe identity log includes environment, host, port, database, disposable state, and run
ID—never credentials. Any mismatch fails before downgrade or destructive SQL with:

`REFUSING DESTRUCTIVE MIGRATION TEST AGAINST NON-DISPOSABLE DATABASE`

## Development migrations

Use the backed-up workflow, not a bare downgrade:

```sh
scripts/dev-migrate.sh
```

It asserts local development and database `gis`, creates a PostgreSQL custom archive under
`~/.local/share/gis/backups/`, verifies the file and `pg_restore --list`, records the current
revision in the filename, applies `upgrade head`, then runs `current` and `check`. It retains
the newest 20 verified pre-migration archives and never removes the archive created by the
current run. A failed or unreadable backup aborts before migration.

Normal `alembic upgrade head` remains supported, but the repository workflow above is the
required operator practice for persistent local development. Automated tests must never use
an override or interactive escape hatch.

## Restore

Restores are destructive and are never automatic:

```sh
scripts/dev-restore.sh /absolute/path/to/verified.dump
```

The script requires local development, target database `gis`, an absolute readable custom
archive, successful archive listing, and typed confirmation `RESTORE gis`. It first creates
and verifies a new pre-restore safety archive, then restores explicitly and runs Alembic
health checks. Stop application writers before an actual restore.

Do not commit database archives, expose database URLs, reuse a persistent test database for
downgrade testing, or make `TEST_DATABASE_URL` fall back to `DATABASE_URL`.
