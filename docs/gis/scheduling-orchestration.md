# GIS Scheduling, Orchestration, and Operations

## Architecture

PostgreSQL is the system of record for pipeline definitions, schedules, targets, dependency
edges, executions, attempts, freshness, budgets, costs, and alerts. Scheduling and execution are
separate: the scheduler materializes due occurrences as immutable execution records, while workers
claim queued work with `FOR UPDATE SKIP LOCKED`.

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
unique key, so scheduler restarts cannot create duplicates.

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

## Retries and backfills

Schedules define maximum attempts, retry delay, and optional exponential backoff. Each retry is a
new `ExecutionAttempt`; exhausting the limit produces a terminal failure and a persistent alert.

Backfills require both start and end dates, reject reverse or unbounded ranges, are limited to 367
days per request, and retain `trigger_type=BACKFILL`. The fixed collector adapter adds date bounds
to supported collector invocations. Rights and budget checks run before every execution.

## Freshness

Freshness is updated by executions, not inferred from table row presence. It records the last
attempt, last success, expected next execution, SLA, stale timestamp, and consecutive failures.
Only successful completion advances `last_successful_at`. The worker periodically evaluates SLAs
and opens a deduplicated `STALE_SOURCE` alert.

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

- The local worker uses PostgreSQL polling; it does not provide distributed rate limiting or leases
  for handlers that exceed database connection lifetimes.
- The built-in collector adapter supports the current allowlisted GIS CLIs. New pipelines must add a
  reviewed handler rather than storing arbitrary shell commands.
- Backfill flags are appropriate for collectors that accept `--start-date`/`--end-date`; other
  pipelines need a purpose-built handler.
- Alert delivery, production process supervision, cloud autoscaling, and commercial billing are not
  implemented.
- Cadence templates are deliberately inactive and incomplete until an operator supplies connections,
  targets, rights approval, and budget limits.
