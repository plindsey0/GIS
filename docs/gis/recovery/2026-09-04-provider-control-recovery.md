# Provider-control recovery — September 2026

## Outcome

Current provider-control operations were reconstructed from surviving evidence after
irreversible local historical-data loss. This is not an exact restoration. History before
the recovery boundary remains incomplete.

The incident occurred around 2026-09-04 22:39:32 UTC and was detected during Epic 26A
validation. The backed-up damaged baseline and exact causal chain are in the
[incident baseline](2026-09-04-provider-control-incident-baseline.md). No recoverable dump,
snapshot, alternate database, Time Machine copy, APFS data snapshot, or PostgreSQL archive
was available. Before reconstruction, the damaged state was preserved in a verified custom
archive outside Git.

## Reconstructed current state

All reconstructed rows have new UUIDs and actual recovery timestamps. They are effective
from recovery forward.

DataForSEO reuses the surviving active connection and reviewed rights policy. SERP Collection
is enabled for `va loan calculator`, weekly Friday at 07:00 America/New_York. The surviving
enabled schedule is reassociated rather than duplicated, and its next recurrence remains
September 11 at 07:00 EDT. Domain Search Intelligence is enabled for `vahomemath.com`,
manual-only, with explicit United States/English market (`2840`, `en`). Monthly soft/hard
budgets are $20/$30; per-run hard budget is $5; request limits are 20/day, 100/month, and
1/run. Current estimates of $0.018 SERP and $0.0132 Domain Search are reconstructed from
surviving real run-cost evidence. They are not recreated usage-ledger rows or universal
provider price claims.

BuiltWith reuses the surviving active connection and reviewed
`builtwith-review-2026-09-04-v1` connection policy. `TECHNOLOGY_PROFILE` is enabled only for
`vahomemath.com`, manual-only. Limits are 1/run, 1/day, and 5/month. Daily soft/hard budgets
are $0.10/$0.25; monthly soft/hard are $1.00/$2.50; per-run hard is $0.10. The $0.0495
estimate is the documented $99/2,000-credit acquisition basis, not a provider-reported USD
charge. Raw retention, normalized retention, internal deterministic analysis, derivative
creation, and aggregate statistics remain allowed by the surviving review; no other right
was broadened.

The three existing provider schedules and scheduled-target records were reassociated to the
new current policy/target identifiers. DataForSEO SERP stayed enabled; Domain Search and
BuiltWith stayed disabled/manual-only. No past-due or duplicate obligation was created.

## Irreplaceable history

The following were deliberately **not** recreated:

- 51 original provider policy audit events;
- 6 original provider usage events;
- 2 original BuiltWith account telemetry snapshots;
- original policy, target, pricing, and capability-policy UUIDs/timestamps;
- historical pricing, target, and policy transitions.

One new incident record and eleven recovery-time audit events document current policy,
capability, target, and pricing establishment. They reference the incident and explicitly say
they are recovery actions, not historical restoration. Usage, audit, telemetry, pricing, and
target-lifecycle completeness are `PARTIAL`, with a recovery-forward completeness boundary.
BuiltWith account telemetry remains UNKNOWN / not refreshed until a future explicitly
authorized real WhoAmI request. No provider call occurred during recovery.

## Operational interpretation

Empty post-recovery usage or telemetry tables do not mean zero lifetime activity. Surviving
orchestration runs, attempts, ingestion runs, and evidence remain historical truth. The
Workbench displays a local-development history warning and labels reset-ledger values as
recovery-forward, while retaining live run evidence separately.

Derived analytics were rebuilt normally from repaired authoritative current state. Trends
that depend on provider-control ledgers retain a discontinuity at the recovery boundary.
No analytics relation was manually edited.

## Prevention

See [database safety](../database-safety.md). Destructive migration tests now require an
explicit run-owned ephemeral database and fail closed before destructive SQL. Alembic honors
the test harness's explicit URL instead of inherited application configuration. Persistent
development migrations use a verified pre-migration backup workflow with bounded retention;
restores are explicit and create their own safety archive.
