# Provider configuration and execution binding

**Data Providers → provider → Configure collection** is the reviewed path from
connection to execution. A connection is not permission to collect.

## Operator workflow

1. Select an existing connection. Credentials remain in secret references.
2. Enable supported capabilities. Planned integrations are inspectable, not editable.
3. Search and select canonical targets. Query choices are active tracked queries;
   domain choices are site domains and active collection domains; URL choices are
   the site canonical URL and active collection URL targets. Selection is static:
   discovery and market membership do not automatically authorize paid collection.
4. Choose manual-only, daily, weekly or monthly cadence per capability. Weekly
   includes weekday/local time; monthly days are bounded to 1–28. Business timezone
   and freshness objective are explicit and separate from cadence.
5. Enter commercial USD budgets, request limits and a reviewed per-target price,
   or explicitly permit unknown cost within daily/monthly/per-execution limits.
6. Preview on the server. **Save Disabled** authorizes no work. **Activate Collection**
   authorizes future execution and is unavailable while blockers remain.

Price is an operator assumption, not live provider pricing. One unit represents one
target retrieval using the adapter's current request shape. Review assumptions when
endpoint, depth, location or billing terms change. Estimates use 30 days or 4.345 weeks
per month and exclude retries. They are not forecasts. Each target is one orchestration
execution; per-run budgets apply to that execution, not the whole cadence window.
For explicitly permitted unknown cost, request ceilings bound exposure. A monetary
ceiling cannot guarantee an unknown provider charge. Unknown is never displayed as free.

Soft budgets warn; hard budgets block projected excess. Failed and partial calls
still count against usage. Missing actual cost retains the estimate when available.
Interrupted reservations remain conservative holds pending reconciliation.

Pause retains intent and history but stops future authorization. Resume revalidates
the saved policy. Disable preserves connection, configuration, observations and usage.
An already dispatched external request cannot be recalled.

**Preview manual run** checks current targets and budgets without calls or queueing.
Explicit confirmation queues through the existing orchestrator. A configuration
fingerprint rejects stale confirmation; a request UUID prevents duplicate queueing.
Execution still rechecks authorization and reserves commercial spend before calling.

## Canonical policy and derived execution

Existing provider policy, capability, target, pricing, usage and audit tables remain
canonical. `ConfigurationService` validates and saves them transactionally. Binding
reconciles existing schedule/target tables as projections, not independent policy.
Do not edit a derived schedule to change authorization.

Reconciliation disables superseded schedules for the site's provider pipelines,
cancels pending scheduled work, blocks superseded obligations and creates a policy
version. Historical runs remain. Paid schedules do not replay missed occurrences;
retries are bounded. Free legacy schedules stay unchanged until explicitly configured.
Representable legacy times initialize the editor; saving is an explicit replacement.
No migration automatically enables commercial collection.

Dispatch re-resolves current policy, capability, canonical target, connection and
schedule version. Disabled capabilities, inactive/removed targets, paused policies
and stale jobs fail closed. SERP and external-search execution reserve through shared
preflight; caller estimates cannot override persisted pricing. Existing orchestration
rights, reliability and dependency checks remain in force. Legacy granular API edits
save disabled drafts and require review before activation.

PageSpeed LAB and available FIELD/CrUX share one retrieval. With both enabled, targets
and cadence must match; one schedule/call per target is generated. A FIELD toggle
does not guarantee field coverage. The shared response may contain both families even
when only one is selected.

## API, migration and maintenance

- `GET /api/v1/providers/{key}/configuration`: configuration and canonical choices.
- `POST .../configuration/preview`: validation and estimates, no external calls.
- `PUT .../configuration`: disabled save or explicitly reviewed activation.
- `POST /api/v1/providers/{key}/actions`: pause/resume/disable and reconcile.
- `POST /api/v1/providers/{key}/run`: preview; confirmation plus fingerprint and
  stable request UUID queues manual work.

Tenant/site scope is required. Mutation/preview endpoints require ADMIN; inspection
uses READ. The existing authenticated Workbench proxy keeps credentials server-side.

Migration `20260903_0030` adds tenant/site pricing scope. Global defaults remain
possible; paired-null and composite foreign-key constraints protect scope. Overrides
never leak across customers. Apply `.venv/bin/alembic upgrade head` with the local
environment loaded. Rollback to `20260902_0029` removes scope columns: back up operator
pricing first. Connections and observations are not removed.

```sh
# Disposable database ONLY: the test fixture downgrades it on completion.
TEST_DATABASE_URL=postgresql+psycopg://gis:gis@localhost:5433/gis_test .venv/bin/pytest
.venv/bin/ruff check src tests
.venv/bin/mypy src/gis
npm --prefix apps/workbench test
npm --prefix apps/workbench run lint
npm --prefix apps/workbench run typecheck
npm --prefix apps/workbench run build
```

Future adapters must supply explicit bindings and canonical target resolution, prove
pause/disable, stale jobs, reservation, tenant isolation and shared retrieval in tests,
and update this guide and Learn GIS. Do not mark planned adapters executable merely
to expose controls. Live source/run detail remains under System, not maintained prose.

## Epic 16B acceptance record

Validated against the real local Workbench and database on September 2, 2026:
DataForSEO was saved **disabled**, using the existing connection and the sole active
tracked query, `va loan calculator` (fewer than ten were available). SERP is selected;
domain intelligence is off. Schedule: Monday 08:00 America/New_York; freshness: 168
hours. Monthly soft/hard: $20/$30; per-target execution hard: $5. Request limits:
20/day, 100/month, 1/execution, maximum 10 authorized targets. Pricing remains unknown
and unknown-cost permission remains off. The derived schedule is disabled with no
next run. Reload preserved the configuration. Manual preview was blocked. No paid
calls, queued commercial work, usage events or external LLM calls were introduced.

Validation: 301 backend tests; 24 frontend tests; Python/TypeScript checks, lint,
production build and dbt parse passed. Local migration head is `20260903_0030`;
Alembic reported no schema drift. Tests also exercised migration creation/rollback
on the disposable database. Existing Python 3.9/google-auth and dbt deprecation
warnings remain; runtime dependency upgrades are outside this epic.
