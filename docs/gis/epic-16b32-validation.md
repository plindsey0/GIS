# Epic 16B.32 validation

Base branch: main. Base SHA: `e0ad4dbeccdbf0211f17696d84c710faec669969`.
Implementation branch: `codex/epic-16b32-domain-execution-correctness`. Not merged.

## Confirmed causes and repair

The Domain Search execution binding omitted location arguments. The adapter's local
validation rejected that request before HTTP dispatch. Contrary to the old error wording,
the current DataForSEO contract permits all-location requests; GIS now makes its narrower
explicit-market requirement visible in configuration, preview, dispatch, and provenance.
No live market choice is silently seeded.

The collector caught the exception and persisted FAILED ingestion, but CLI returned zero.
The worker trusted process completion and never validated the linked ingestion. The CLI
now returns failure plus exact ingestion identity; the worker validates ingestion status,
errors and scope, preserves failed-run linkage/cost, and applies existing classified retry
rules. Workbench derives failure for the historical inconsistency without updating any row.

## Validation

- Backend: 356 tests passed; 8 new regression cases in `test_domain_execution.py`.
- Workbench: 42 tests passed; new operator-facing effective/recorded-state test.
- Ruff src/tests and changed-file formatting passed; mypy passed for 124 source files.
- Repository-wide Ruff still reports two pre-existing imports in migration 0012; unrelated
  repository formatting debt was not rewritten in this focused repair.
- ESLint, TypeScript, Next.js production build (36 pages), Python package build: passed.
- dbt build on isolated gis_test: 450 passed (including 232 data tests and 2 unit tests).
- Alembic empty-database upgrade/rollback tested. No new migration. Real database current,
  head and check: `20260904_0031`, no drift.
- Existing Python 3.9/google-auth and dbt deprecation warnings remain.
- Browser: real historical run shows Failed / configuration problem / 1 request / 0 / 0
  records / 1 error / unknown cost, with explicit recorded-success explanation. Provider
  activity shows the effective failure. Desktop and 390px layout checked; no console errors
  or page overflow. Manual defaults unselected; domain/query/mixed counts remain 1/1/1,
  1/1/1, 2/2/2. Missing domain market blocks confirmation, independently of SERP selection.
- API, Workbench and worker started under paid-execution hold. No provider configuration
  was saved, no paid call or external LLM call was made, and zero paid credits were consumed.
- Git whitespace and changed-content secret-pattern review passed.

## Historical preservation

SHA-256 hashes of ordered PostgreSQL row JSON matched before and after implementation:

| Table | Rows | Unchanged SHA-256 |
| --- | ---: | --- |
| execution_attempt | 28 | df88c8d519578ef50db046cc353ec5095604efeadecc958750aec0b87e9f7079 |
| ingestion_run | 95 | 4f28633b12389d33658831854c0d32f65a3674ff170d52a2b17661fb03295cc3 |
| objective_audit_event | 3 | 3925531e00234ea0702676a365597b04dc80de1ea7862ea1da03825a16c61c9e |
| orchestration_obligation | 15 | 8db2e61493d8724de6ac63a72fa9b2b83f9d96ca521388422e538f99a3e47714 |
| orchestration_run | 24 | 3a6fe64d5a7a582cc86b0261ab7c3f5972609149fc49af84d40e334d4f38cf72 |
| provider_policy_audit_event | 35 | 8ca9cfccc7fa936503f7d86b2c7b3b67eaf21b1a67e1880f9cbd94f5ea327d8a |
| provider_usage_event | 3 | fac7536a9039ebaf64495fbfe1590bde2d89b2ffca26da09b7e6ceed99e1107a |
| schedule_definition | 19 | b0c669e3cc096202b724e37330da87cf7355f16821e501871fe0e7da119572fa |

The September 4, 2026, 7:00 AM America/New_York SERP recurrence is untouched. The historical
domain failure's ledger retains FAILED / 1 request / unknown actual and estimated cost.
No response cost is available; the local pre-dispatch failure is not converted to a $0
provider charge. See [operator semantics](domain-search-execution.md).

## Operator follow-up

Before a separately authorized paid Domain Search test, choose explicit location/language
configuration (United States / English: 2840 / en). No live settings were changed during
this repair. Existing provider configuration save reconciles schedules, so coordinate that
step with the separately protected scheduled SERP acceptance test. Paid execution remains
held; lifting that hold is not part of this implementation.
