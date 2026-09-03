# GIS Scheduling, Orchestration, and Operations

## Architecture

PostgreSQL is the system of record for pipeline definitions, schedules, durable data obligations,
targets, executions, attempts, executor heartbeats, freshness, budgets, costs, and alerts. A
schedule states a preferred execution time; an obligation states that a reporting window must be
satisfied. The scheduler materializes bounded missed obligations and workers claim their runs with
`FOR UPDATE SKIP LOCKED`.

The local implementation runs with `gis-orchestrator worker`. A future ECS, Lambda, EventBridge,
Kubernetes, or managed worker can claim the same PostgreSQL queue without changing the domain
model. First-party telemetry remains event-driven and has no polling schedule.

## Execution lifecycle

An execution begins as `PENDING`, may wait for dependencies, becomes `RUNNING`, and terminates as
`SUCCEEDED`, `FAILED`, `BLOCKED`, or `CANCELLED`. Retriable failures enter `RETRY_WAIT`. Every
worker invocation creates an append-only attempt; failures are never overwritten. The execution
retains tenant, site, schedule, target, source connection, rights policy, upstream execution,
resulting ingestion run, estimated/actual cost, and error classification.

Workers use a fixed handler registry. `COLLECTOR_CLI` invokes only allowlisted GIS collector
executables without a shell; `DBT` invokes `dbt build`. These adapters reuse existing collector
boundaries rather than reproducing ingestion logic. Collector arguments live in the explicitly
reviewed schedule configuration.

## Schedule semantics

Schedules use five-field cron expressions and an IANA timezone. Calculation scans UTC instants and
matches their local representation. Nonexistent spring-forward times are skipped. An ambiguous
fall-back wall-clock time runs once, at `fold=0`. Each schedule occurrence and target has a database
unique key, so scheduler restarts cannot create duplicates. On startup the scheduler examines only
the configured `automatic_catchup_seconds` window, creates missing obligations, and executes them as
`CATCH_UP`. Older windows require an explicit bounded backfill. Disabled schedules create nothing.

Each obligation preserves its reporting window, original due time, expiry, policy version, status,
attempt count, completion outcome, ingestion link, failure category, and explanation. A late success
satisfies the original obligation rather than erasing the missed preferred time.

Schedules are independently enabled and disabled. Creation defaults to disabled unless `--enable`
is explicit. The cadence bootstrap creates templates but activates none.

## Dependencies

Dependencies are tenant-scoped directed edges between arbitrary pipelines; additions that introduce
a cycle are rejected. `ALL_SUCCESS` requires every relevant upstream execution to succeed,
`ANY_SUCCESS` requires at least one, and `ALWAYS` waits for terminal upstream state but runs despite
failure. Downstream work remains waiting while an upstream execution is absent or non-terminal.
Upstream and downstream cron timestamps need not match: the worker considers the latest upstream
execution inside the downstream run's configurable `dependency_window_seconds` (seven days by
default). Set a tighter window for high-frequency pipelines.
Manual runs, explicit retries, and backfills are operator-directed and do not implicitly wait on
the scheduled graph.

## Completion, retries, reconciliation, and backfills

Completion is separate from process exit. `SUCCEEDED_COMPLETE` and
`SUCCEEDED_NO_DATA_EXPECTED` satisfy an obligation. Provider-pending or partial results remain open
for reconciliation. GSC uses revision-aware recent-window collection; GA4 uses a shorter recent
window. PageSpeed LAB success remains valid when CrUX reports `NO_FIELD_DATA_AVAILABLE`.

Schedules select configurable retry profiles: `DAILY_FREE_API`, `WEEKLY_FREE_API`,
`PAID_BOUNDED`, or `LOCAL_DETERMINISTIC`. Failure categories distinguish transient network,
429/5xx, provider-pending, authentication/authorization, configuration, rights, budget, invalid
request, abandoned execution, and internal failure. Terminal categories stop automatically. Paid
pipelines are forcibly capped to the paid profile even if misconfigured, and every attempt still
passes existing rights and budget checks.

Backfills require both start and end dates, reject reverse or unbounded ranges, are limited to 367
days per request, and retain `trigger_type=BACKFILL`. The fixed collector adapter adds date bounds
to supported collector invocations. Rights and budget checks run before every execution.

## Freshness

Freshness is updated by executions, not inferred from table row presence. It records the last
attempt, last success, expected next execution, SLA, stale timestamp, and consecutive failures.
Only successful completion advances `last_successful_at`. The worker periodically evaluates SLAs
and opens a deduplicated `STALE_SOURCE` alert.

System health reports source/data health separately from automation health. Source health uses the
latest ingestion, provider reporting period, configured freshness SLO, and staleness. Automation
health uses schedule state, executor liveness, next due time, obligations, retries, and orchestration
run count. Thus successful manual ingestion no longer implies scheduler reliability, and an enabled
schedule with no live executor is explicitly `EXECUTOR_OFFLINE`.

## Liveness and abandoned work

The combined local scheduler/worker publishes separate leased `SCHEDULER` and `WORKER` heartbeats.
Attempt leases allow a later worker pass to classify a dead process as `ABANDONED`, preserve the
failed attempt, and retry within policy. The database queue and uniqueness constraints prevent two
workers from claiming the same pending run or creating the same obligation.

## Cost governance

Budgets can scope tenant, site, source, pipeline, and schedule. Each may define daily, monthly, and
per-run limits. Estimated cost is checked before the handler runs. A rejection records a blocked
execution and `BUDGET_EXCEEDED` alert. Successful runs append their actual cost—including zero-cost
collectors—to the ledger. Currency mismatches fail closed rather than combining currencies.

## Operational alerts

Rights blocks, budget blocks, dependency failures, malformed configuration, terminal pipeline
failure, and staleness create persistent alerts. A partial unique index allows only one open alert
per tenant and deterministic key; repeated observations increment its count. Alerts can be resolved
through the CLI. Notification delivery is intentionally deferred.

## Local operation

```bash
docker compose up -d db
source .venv/bin/activate
alembic upgrade head
gis-seed --hostname vahomemath.com
gis-orchestrator seed-vahomemath --confirm-disabled
gis-orchestrator list --tenant vahomemath
gis-orchestrator worker --once
```

Use `gis-orchestrator schedule`, `enable`, and `budget` only after reviewing configuration, rights,
credentials, target bounds, and maximum provider cost. Run the long-lived worker with a process
supervisor on the Mac Studio. Restart is safe because queue claims are transactional and occurrence
identity is unique.

Useful recovery commands:

```bash
gis-orchestrator status --tenant vahomemath
gis-orchestrator history --tenant vahomemath
gis-orchestrator alerts --tenant vahomemath
gis-orchestrator retry --tenant vahomemath --execution <uuid>
gis-orchestrator obligations --tenant vahomemath --overdue
gis-orchestrator obligations --tenant vahomemath --id <uuid>
gis-orchestrator catch-up --tenant vahomemath
gis-orchestrator liveness
```

## Default VAHomeMath cadence

The idempotent bootstrap supplies disabled templates for daily GSC, daily GA4, daily dbt after
upstreams, daily priority SERPs, weekly external search, weekly competitive content, weekly
competitive technology, and weekly PageSpeed/CrUX. Paid DataForSEO templates are always disabled.
First-party telemetry remains event-driven. Operators may add weekly lower-priority SERP or monthly
broader content/technology schedules using the same pipeline definitions and different targets.

Templates intentionally require connection IDs and collector arguments before activation. The
bootstrap never creates credentials, performs requests, or enables production recurrence.

## Rights and provenance

When a schedule uses a source connection, the worker evaluates normalized-retention rights before
dispatch and blocks `UNKNOWN` or `DENIED`. The underlying collector then performs its existing,
authoritative rights, tenant, provenance, cost, and request-safety checks. Orchestration records link
the initiating schedule and attempt to the connection, rights policy, ingestion run, and upstream
execution; it is not an enforcement bypass.

## Analytics

dbt exposes staged runs/attempts and marts for daily success rate, duration, retries, failures,
backfills, actual source cost, budget utilization, and current freshness. Metabase presentation is
out of scope.

## Known limitations

- The local worker uses PostgreSQL polling. Attempt leases recover process death, but long handlers
  do not yet renew their lease mid-call; handlers longer than the lease need a future heartbeat hook.
- Completion contracts are extensible metadata contracts. Current collectors expose safe default,
  provider-pending, and PageSpeed LAB/no-field semantics; richer provider finality signals should be
  added when each upstream exposes a trustworthy finalization marker.
- The built-in collector adapter supports the current allowlisted GIS CLIs. New pipelines must add a
  reviewed handler rather than storing arbitrary shell commands.
- Backfill flags are appropriate for collectors that accept `--start-date`/`--end-date`; other
  pipelines need a purpose-built handler.
- Alert delivery, production process supervision, cloud autoscaling, and commercial billing are not
  implemented.
- Cadence templates are deliberately inactive and incomplete until an operator supplies connections,
  targets, rights approval, and budget limits.
## Operational timing and activity (Epic 16B.2)

`duration_seconds` in operational API summaries now means the sum of complete
attempt durations, never original start to recovered completion. Missing attempt
intervals produce unknown runtime. Wall-clock resolution, recovery latency and
obligation lateness are separate fields. Historical timestamps are unchanged.
See [the timing contract](provider-operations.md#timing-contract).

Provider activity groups retries under their durable obligation, preserving one
row per target obligation. A recovered incident is excluded from current incidents
but retained in 30-day reliability counts. Small samples use counts, not rates.
No dbt mart changes are required; operational counts come directly from the same
durable obligation records and do not depend on an asynchronous mart refresh.
