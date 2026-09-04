# Epic 16B.4.1 validation and handoff

Branch: `codex/epic-16b41-builtwith-governance-telemetry`

Base: `566c022e695c219056b65df16d06493f2ef215fc`

## Architecture and delivery

Reused DataRightsPolicy, DataRightsGrant, supersedes_policy_id, the shared per-use evaluator,
connection scoping, administrator authentication, provider readiness and source pages.
The existing bulk reviewed-policy activation command was not used: it can rewrite broader
state and is inappropriate for a single operator review.

New human reviews capture each compatibility field and effective permitted-use grant,
review authority, server review time, basis, version, immediate effective time, retention,
license/reference, jurisdiction and notes. They preserve old policy/grant snapshots.
Only the selected connection pointer changes when an operator explicitly approves;
no live approval was performed by this epic.

New account telemetry uses one additive table and the existing credential resolver.
No new provider execution framework, ingestion type, domain target, schedule, or billing
entry was added. Account interaction can establish historical authentication but never
technology collection acceptance.

BuiltWith collection requires only raw_retention and normalized_retention = ALLOWED.
Exact current blockers are displayed independently from credentials/hold/authorization.
Recommendations in [the rights review](builtwith-rights-review.md) are not policy grants.
Broad GIS commercial/third-party/competing-product use requires scope clarification.

WhoAmI: GET https://api.builtwith.com/whoamiv1/api.json, same credential via header.
Official references document zero purchased credits. No live call was necessary here.
Only safe normalized credit/limit/privacy/inventory fields persist; raw responses, account
email, keys and response URLs do not. Manual admin confirmation, one-minute cooldown,
24-hour freshness and process-hold enforcement apply. No polling was introduced.

The dependency bug was an incomplete read model: provider-created pipelines have no
direct data_source_id, while their schedule has the correct source connection. Source
impact now follows that existing site-scoped relation, plus direct links. Missing asset
lineage remains explicitly explained. No operational record was rewritten to fix display.

## Migration and checks

- Added `20260904_0032_provider_account_telemetry.py`.
- Real database current/head: `20260904_0032`; Alembic check: no new operations.
- Backend: **384 passed**, including 16 new rights, API security, telemetry and dependency tests.
- Workbench: **47 passed**, including four new source-governance tests.
- Ruff src/tests/new migration, changed Python formatting and mypy (127 files): passed.
- ESLint, TypeScript, Next production build and Python package build: passed.
- dbt parse: passed; no analytics models changed.
- Desktop and 390px source/review/provider inspection: no page overflow or console errors.
- Tests use isolated gis_test and mocked provider responses only.
- Staged secret scan passed: no configured environment secrets or private-key material;
  provider fixtures and placeholder values were reviewed.
- Existing Python 3.9/dbt deprecation warnings and old migration import lint debt were not changed.
- A temporary preview cache initially entered the lint scan; after moving that generated
  cache out of the workspace, the normal checks passed.
- Browser review was read-only: no policy approval, activation, or telemetry refresh.

## Protected operational state

Baseline: **261 tables, 12,679 rows**, excluding transient executor heartbeats.
Whole-table fingerprints match for **251 original tables**, including source
connections, provider policies/capabilities/targets, rights/grants, source ingestion,
provider usage, audit events and provider evidence.

Ten shared tables changed during the independently running local market_intelligence
schedule at 2026-09-04 15:30:11 UTC. This task did not restart, pause, reconcile or mutate
the normal scheduler/worker. Its background derived-market work accounts for appended
market observations and the run/attempt/cost/obligation rows, plus its own schedule and
freshness updates.

Excluding rows created after branch creation (2026-09-04 15:18:26 UTC) restores the exact
baseline hashes for **all original runs, attempts, obligations and cost-ledger records**:

| Table | Original rows | Matching SHA-256 |
| --- | ---: | --- |


Only market_intelligence rows have post-start updates in schedule_definition and
freshness_state. DataForSEO's enabled SERP schedule
`03b1cc6f-f11e-48c3-aa96-40aee156822f` remains `0 7 * * 5`,
America/New_York, next **2026-09-11 11:00 UTC / 7:00 AM EDT**. Its prior success
completed September 4 at 12:38:30 UTC / 8:38:30 AM EDT and was not rewritten.

The new account-telemetry table contains **0 rows**. Live BuiltWith policy remains
unreviewed; credentials, authorized target and manual-only configuration are unchanged.
Whole shared-table equality is not claimed where autonomous market processing occurred.

## Operator handoff

Merge/restart when approved; this branch was not merged. The real database has the
additive migration, but the normal API/worker were deliberately left running unchanged.
A separate paid-held API/Workbench preview was used and then stopped. Restart the normal
runtime after deployment to load the new endpoints. Old-API fallback remains readable.

1. Open BuiltWith source and review the documented rights evidence.
2. Approve only supported uses, especially the two retention grants, with human provenance.
3. Inspect/explicitly refresh account telemetry if authorized; confirm account entitlement.
4. Confirm vahomemath.com only, Manual only, one-request ceiling and conservative budget.
5. Review any process hold and other pending paid work before deliberately releasing it.
6. Preview, select the domain, verify 1 capability / 1 target / 1 request, then separately confirm.
7. Inspect run → attempt → ingestion → technology evidence → usage; optionally refresh balance.

BuiltWith technology calls: **0**. Account telemetry calls: **0**.
BuiltWith credits consumed: **0**. DataForSEO calls: **0**. External LLM calls: **0**.
Implementation blockers: none. Human rights approval and live account/collection acceptance remain operator steps.
