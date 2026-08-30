# Growth Dashboard — P0 (Epic 6 implementation record)

Epic 20.5 supersedes this primary information architecture with
[GIS Executive Intelligence](executive-intelligence-dashboard.md). The API provisioning mechanism
originated here remains in use, but the current manifest now provisions an executive collection
hierarchy and supporting dashboards rather than this single provider-oriented page.

## Purpose and architecture

Epic 6 provides the first operator-facing GIS dashboard. It uses Metabase OSS, the BI platform
selected by the PRD, and reads only dbt-owned `gis_analytics` marts. Metabase does not write to
GIS schemas. Alembic remains responsible for application schemas and dbt remains responsible for
derived schemas.

The dashboard definition is reproducible: `dashboard/manifest.json` defines its cards, layout,
and global filters; `dashboard/questions/` contains native SQL; and `dashboard/provision.py`
creates or updates the collection, questions, and dashboard through the Metabase API.

## Sections and sources

| Dashboard section | Source marts |
|---|---|
| Executive Overview | `mart_site_daily`, `mart_data_reconciliation`, `mart_acquisition_daily` |
| Search Performance | `mart_site_daily` |
| Page Performance | `mart_page_daily`, `mart_data_reconciliation` |
| Keyword / Query Performance | `mart_keyword_daily`, `mart_keyword_page_daily`, `mart_page_daily` |
| Acquisition | `mart_acquisition_daily` |
| Calculator Performance | `mart_calculator_performance`, `mart_data_reconciliation` |
| Conversion Performance | `mart_conversion_daily`, `mart_data_reconciliation` |
| Data Quality / Reconciliation | `mart_data_reconciliation` |

Every question supports tenant, site, start-date, and end-date parameters. Page, query, and
channel questions add relevant card-level filters. IDs are parameters and are never hard-coded,
so the same dashboard supports every tenant and site.

## Local startup and provisioning

Run migrations and dbt before starting Metabase:

```bash
cp .env.example .env
# Set unique local values for METABASE_ADMIN_EMAIL and METABASE_ADMIN_PASSWORD in .env.
set -a && source .env && set +a
docker compose up -d db
alembic upgrade head
dbt build --project-dir analytics --profiles-dir analytics
docker compose up -d metabase
python dashboard/provision.py
```

Open `http://localhost:3030`. The service binds only to loopback and is not publicly exposed.
Port 3030 is configurable through `METABASE_PORT` and does not use PostgreSQL ports 5432 or 5433.

The provisioner initializes a fresh Metabase instance with the local admin values, registers the
GIS PostgreSQL connection, creates the `GIS Operations` collection, and provisions the dashboard.
On later runs it updates existing named questions and adds missing dashboard cards. Passwords are
read from the environment and are neither embedded in the manifest nor printed.

For production, use an external Metabase application database, a read-only GIS database role,
deployment-managed secrets, TLS, and network access controls. Compose is deliberately local-first.

## Metric and missing-data semantics

- GSC impressions are search-result visibility, not visits.
- GSC clicks and GA4 organic sessions are independent measurements and need not agree.
- GA4 sessions follow GA4 reporting and attribution semantics.
- First-party sessions are exact GIS telemetry sessions. VAHomeMath telemetry is not deployed yet.
- A missing provider is unavailable/NULL, not a measured zero.
- A present GA4 date with zero organic sessions is a valid zero.
- Recent missing GSC dates may be provider latency and are not zero demand.
- Reconciliation ratios remain NULL when required evidence is absent or the denominator is zero.

Calculator and conversion cards emit `FIRST_PARTY_TELEMETRY_NOT_YET_AVAILABLE` when coverage is
absent. Executive and page views use presence flags to suppress misleading first-party zeroes.
The data-quality section exposes source-presence flags, deltas, valid ratios, and `quality_status`.

## Troubleshooting

- Check `docker compose ps` and the Metabase health status if the UI does not load.
- Run `dbt build --project-dir analytics --profiles-dir analytics` if a mart is missing.
- Keep `METABASE_GIS_DB_HOST=db` in Compose; `localhost` would mean the Metabase container.
- If login fails, use the admin account that initialized the existing `gis-metabase-data` volume.
- Use `docker compose logs metabase` for startup or driver errors without pasting secrets.

Generated application state stays in the Docker volume. The manifest, SQL, and provisioner are
the source of truth for recreating the dashboard.
