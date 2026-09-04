# BuiltWith active collection acceptance readiness

## Delivered scope

Branch: `codex/epic-16b4-builtwith-active-collection`

Base: `fc49861e5253d1ab39c65f0af2f4aaf6d6879b35`

The base already contained the implemented v23 adapter and registration migration
0031. This epic reuses that control plane, adds exact failed-ingestion linkage through
the CLI and worker, normalizes documented provider detection dates, and adds mocked
acceptance tests and operator guidance. No migration, provider credentials, authorization,
live evidence, schedule, pricing assumption or rights grant was created.

## Validation

- Backend: 368 passed (including 12 new acceptance cases); isolated `gis_test`.
- Workbench: 43 passed; ESLint, TypeScript and Next.js production build passed.
- Ruff: `src tests` passed; changed Python format checks passed.
- Repository-wide Ruff still reports the two pre-existing import findings in migration
  `20260830_0012`; intentionally unchanged.
- mypy: 125 source files passed; Python sdist/wheel build passed.
- dbt parse passed; build passed all 450 tasks (214 models, 232 data tests,
  2 unit tests, 2 seeds) on migrated `gis_test`.
  An initial build followed pytest schema teardown and failed for missing relations;
  rerunning after isolated schema creation passed. Generated test analytics objects
  were then removed so migration teardown remains usable.
- Real Alembic current/head: `20260904_0031`; check found no upgrade operations.
- API, combined scheduler/worker and Workbench restarted successfully under the paid hold.
- Browser: desktop and 390px provider/configuration/guide checks, no page overflow
  and no browser console errors. No configuration was saved in the live browser.
- Secret scan: no configured environment secrets or private-key material in staged
  changes; fixture placeholders reviewed. Worker paid-hold environment verified.
- Existing Python 3.9 end-of-life and dbt-version warnings remain outside this epic.

Mocked success, authentication rejection, throttling, malformed response and internal
processing failure traverse the actual CLI handler and worker. Every dispatched
fixture retains exact ingestion/attempt/usage linkage; failures do not become success.
Raw payload, UTC detection dates, technology evidence, activity and run detail are
verified. Decimal operator estimate `0.0495` is exact; actual USD remains unknown
because the documented API supplies no per-response dollar charge. No fictional
provider-cost field was introduced merely to satisfy a test.

Existing tests additionally cover registration, credentials, scope/idempotency,
rights, hard limits and manual-only scheduling. New cases cover explicit unknown-cost
policy and capability-specific UI without DataForSEO location/language fields.

## Live isolation

Before/after read-only fingerprints matched for **all 261 GIS base tables / 11,831 rows**.
Only transient `executor_heartbeat` was excluded. Each table's ordered
`row_to_json(t)::text` values were SHA-256 hashed; no raw records or secrets were copied
into this report. This includes all DataForSEO policies, targets, connections, rights,
obligations, runs, attempts, ingestion, ledger and recommendations.

Protected enabled SERP schedule `03b1cc6f-f11e-48c3-aa96-40aee156822f` remains
`0 7 * * 5`, `America/New_York`, next `2026-09-04T11:00:00Z`
(**September 4, 7:00 AM New York**).

Selected whole-table fingerprints (before = after):

| Table | Rows | SHA-256 |
| --- | ---: | --- |
| gis_core.data_rights_policy | 10 | `fc069cf13386f31b7ed07f46854c0cf68285a178032c58a3cd7c1621596719b9` |
| gis_core.execution_attempt | 29 | `26174ba26eb43d838322c01557dc7bea3e9475bf811b9b15d72b40c92a9d79a1` |
| gis_core.ingestion_run | 96 | `f87bd352b60183c5c6c83c6ddc162f20c826257c99fd82e89a502db925e447f8` |
| gis_core.orchestration_run | 25 | `a7db1b4881916029e678b2e2fe246d3104ebba96dede243982a126a0820e66a0` |
| gis_core.provider_collection_target | 2 | `98d289fc8251ab2001c456d6b60c0b7494da9e781fa7d78dfaa29a5366dfa52f` |
| gis_core.provider_usage_event | 4 | `c7c45c5db01d7d039b417a6ceb14924d7f869fcb70583a3c99daa2d755252f28` |
| gis_core.schedule_definition | 19 | `5246b9f3e20410eb9090737d1bad614b24519c61108a98ee125d2564ec1ad2e8` |

## Live-test boundary and handoff

No BuiltWith connection currently exists in the checked local environment. The UI
correctly reports not connected, authentication not independently validated, disabled
manual-only capability and no collection history. Readiness is conditional on operator
credential/entitlement/rights/budget/target configuration, not fabricated acceptance.

Follow [the operator checklist](builtwith.md#first-live-acceptance-operator-checklist-not-performed-by-this-epic)
or Workbench `/docs/builtwith-acceptance`. Merge/restart, configure the shared secret
reference, review rights, authorize only `vahomemath.com`, keep Manual only, set conservative
limits, preview 1 capability / 1 target / 1 request, then confirm only with separate live approval.

**The runtime remains under `GIS_PAID_EXECUTION_DISABLED=1`.** Saved DataForSEO
recurrence is intact, but a global paid hold prevents dispatch. The operator must
deliberately release it before an authorized live test or scheduled acceptance run,
after inspecting other pending paid work. This epic does not release that hold.

Paid BuiltWith calls: **0**. BuiltWith credits: **0**.
DataForSEO calls: **0**. External LLM calls: **0**.
No historical records rewritten; no fabricated authentication, costs, evidence or opportunities.
