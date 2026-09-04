# Epic 16B.3.1 validation

Base: `a954e67b7890ef1d3f5939d18e74c42f66d307c1` (current main at start).
Branch: `codex/epic-16b31-manual-scoping-builtwith`. Not merged.

## Manual-scoping investigation

The base source and both generated frontend bundles contained the target selector.
The backend included the authorized manual DOMAIN and scheduled QUERY; no cadence or
target-type exclusion explained the report. The historical browser-loaded bundle was
not available, so its exact deployment/cache cause cannot be established retrospectively.
The reported summary-only $0 screen is consistent with a legacy frontend using the
empty-scope preview response. This is an inference, not a reproduced historical cause.

Discovery now has a separate GET contract. The frontend validates the choices response,
starts every target unselected, and invalidates previews when selection changes. An old
empty-scope POST now gets an actionable reload/selector error instead of a $0 preview.

## Validation results

- Python: 348 passed (two existing Python 3.9/google-auth deprecation warnings).
- Workbench: 41 passed across 9 files; ESLint and TypeScript passed.
- Mypy: 123 source files passed. Changed Python files pass Ruff lint and formatting.
- Repository-wide Ruff has two pre-existing import findings in migration 0012 and
  unrelated formatting debt. The base migration reproduces those lint failures;
  unrelated files were not reformatted as part of this epic.
- Next.js production build: 36 pages generated successfully.
- Python source/wheel package build: passed; installed `gis-builtwith --help` passed.
- dbt parse and isolated-database build passed: 450 nodes, including 232 data tests
  and 2 unit tests; no errors or skips. Existing dbt version deprecation warning remains.
- Empty-database migrations and rollback exercised by Python tests. Real local database
  current/head/check: `20260904_0031`, no schema drift.
- Browser: DataForSEO domain-only 1/1/1, query-only 1/1/1, both 2/2/2; zero selection
  disables review. BuiltWith shows implemented but disabled/unconnected, not planned.
  Desktop and 390px layouts inspected; document width equals viewport width; no console errors.
- Secret-pattern review and Git whitespace check passed.

## Historical-state preservation

Read-only checks compare SHA-256 of ordered PostgreSQL row JSON before and after work.
All rows and hashes are unchanged:

| Table | Rows | SHA-256 |
| --- | ---: | --- |
| schedule_definition | 19 | b0c669e3cc096202b724e37330da87cf7355f16821e501871fe0e7da119572fa |
| orchestration_run | 23 | 37765b02265ca32fa3054e474b0880f3b964c0f4466305feec6814c5546a9f92 |
| orchestration_obligation | 15 | 8db2e61493d8724de6ac63a72fa9b2b83f9d96ca521388422e538f99a3e47714 |
| execution_attempt | 27 | 192011e919a94d14af2d41c28270b03803a5992eb4daca24329ff685be6ea061 |
| provider_usage_event | 2 | be854343f8a82a7eb9776bb1a414ea634b634f5163ea21deaf4dd6aaede25f60 |
| ingestion_run | 94 | 20c3e86ad8b6a614e6cbaab53bc5716d9ba39f94cee3893b6488411438b513a3 |

The September 4 SERP recurrence and historical DataForSEO outcomes/costs are untouched.
Paid provider calls: **0**. Paid credits consumed: **0**. No external LLM calls.
The API, Workbench, scheduler and worker started with paid execution held. BuiltWith
has no local credential/entitlement validation, authorization, schedule, or live history.

## Operator boundary

See [BuiltWith setup and pricing](builtwith.md). Live acceptance requires an API key
and Domain API credit entitlement, reviewed rights, explicit target authorization and
limits, and separate approval to lift the paid-execution hold. No subscription purchase
or live authentication is performed by implementation or migration.
