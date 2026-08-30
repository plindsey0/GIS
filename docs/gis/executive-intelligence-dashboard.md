# GIS Executive Intelligence Dashboard

## Purpose and executive questions

`GIS Executive Intelligence` is the reproducible command center for the standalone GIS. It keeps three questions visibly separate: how the owned site is performing, what is observable around it, and whether GIS itself has current, usable evidence. An operator should be able to identify performance direction, competitive changes, evidence coverage, operational health, governance blockers, cost, and unsupported capabilities without knowing provider names.

The lifecycle is **OBSERVE → UNDERSTAND → DETECT → RECOMMEND → INTERVENE → MEASURE → LEARN**. Current production models support OBSERVE and UNDERSTAND. Detection, recommendations, interventions/experiments, outcomes, and learning remain explicitly `NOT_IMPLEMENTED`; the dashboard does not fabricate their KPIs.

## Information architecture

The main page contains restrained status KPIs, owned growth trends, an equivalent-period comparison, cross-domain competitive facts, recent changes, descriptive gaps, capability coverage, operations, governance, cost, and future-layer states. Supporting dashboards expose competitive evidence and operations/governance detail.

The provisioned collection tree is `GIS` with `Executive`, `Growth Performance`, `Search Intelligence`, `Competitive Intelligence` (`Content`, `Technology`, `Authority`, `Events`), `Operations`, `Governance`, `Cost`, and `Diagnostics` children. This structure allows progressive disclosure from summary to analytical detail to source evidence.

## Executive semantic layer and grains

| Model | Grain | Meaning |
|---|---|---|
| `mart_executive_site_daily` | tenant, site, date | Owned search, behavior, and conversion facts with source-availability flags |
| `mart_executive_period_comparison` | tenant, site | Trailing 28 dates versus the immediately preceding 28 dates |
| `mart_executive_search_position` | tenant, site, date, device | Observed tracked-query position only |
| `mart_executive_competitive_position` | tenant, site, date, domain, evidence domain, source system | Long-form domain-specific competitive facts |
| `mart_executive_recent_events` | competitive event | Event materiality, confidence, and evidence kept distinct |
| `mart_intelligence_coverage` | tenant, site, capability | Capability structure plus derived operational state |
| `mart_executive_operations` | tenant, site | Current freshness, schedule, failure, and alert summary |
| `mart_executive_governance` | tenant, site | Product-governance policy coverage |
| `mart_executive_cost` | tenant, site, month, currency | Observed ledger cost or explicit unknown cost |

The layer reuses `mart_site_daily`, SERP visibility, external-search visibility and gaps, content/technology domain and gap marts, authority domain/gap marts, competitive-event timeline, and Epic 18.5 operations marts. Each source is reduced to its declared grain before any join; heterogeneous competitor facts use a long-form union instead of a fanout-prone wide join. Provider-specific authority metrics remain a JSON object keyed by provider and metric. There is no universal authority, competitor, growth, or significance score.

## Metric contracts

`analytics/seeds/executive_metric_contracts.csv` is the machine-readable KPI contract. Each entry declares display name, source model, grain, unit, semantic class, time and comparison behavior, and caveats. Important definitions include:

- `organic_clicks` and `organic_impressions`: GSC-measured daily totals when GSC coverage exists.
- `organic_ctr`: clicks divided by impressions; null when the denominator is absent or zero.
- `search_position`: impression-weighted provider-reported average; lower is better.
- `conversion_rate`: first-party conversions divided by first-party sessions; it does not assert causal attribution.
- `tracked_query_top_10_rate`: top-ten presence within the observed tracked-query set, not the whole market.
- `material_event_count`: events whose semantic class is material; confidence is a separate column.
- `monthly_provider_cost`: ledger-observed cost. No ledger row means `UNKNOWN`, not zero.
- `pipeline_freshness_rate`: fresh monitored pipelines divided by monitored pipelines; disabled schedules are not failures.

## Capability registry and status precedence

`analytics/seeds/intelligence_capability_registry.csv` describes stable capability structure, lifecycle stage, associated pipeline, freshness expectation, and whether dashboard rights are required. It never stores current operational state. Evidence, connections, schedules, executions, alerts, and effective policy decisions determine state.

Precedence is deterministic:

1. `NOT_IMPLEMENTED`
2. `BLOCKED_BY_RIGHTS`
3. `FAILED`
4. `DEGRADED`
5. `STALE`
6. `DISABLED`
7. `IMPLEMENTED_NO_DATA`
8. `CONFIGURED`
9. `OPERATIONAL`

`DISABLED` means all defined schedules are intentionally disabled. It is never presented as failure. A capability with no observations is `IMPLEMENTED_NO_DATA` unless a more specific higher-precedence condition applies. A connection that exists but is not active is `CONFIGURED`. `BLOCKED_BY_BUDGET` can be introduced when the operations domain exposes a durable current budget-block state rather than inferring it from historical runs.

## No-data, sparse-data, and time semantics

Zero and absence are different. Owned daily marts expose availability booleans, KPI SQL returns null when its source is absent, coverage exposes `NO_DATA`, and cost exposes `UNKNOWN`. Fixture scarcity, one-time imports, and manual collectors are therefore visible rather than converted to zeros. Disabled paid schedules can coexist with historical evidence and are shown explicitly.

Dashboard filters support tenant, site, start date, and end date. Daily event dates retain their source/property semantics. The canonical comparison uses two adjacent, equal 28-date windows; it never compares a partial period to a full period. Site timezone is retained in the site model and upstream integrations determine business dates. Current-state cards use the filter only as an optional dashboard consistency constraint.

## Competitive, event, and gap semantics

Search coverage is observed tracked-query/provider coverage, not the whole market. Content, technology, and authority comparisons are observed facts. Gap rows say `COMPETITOR_ONLY`, `OWNED_ONLY`, `SHARED`, or `OBSERVED_DIFFERENCE_NOT_RECOMMENDATION`; they do not say opportunity, priority, recommendation, should, or fix. Event materiality and confidence remain separate. Absence of a backlink or technology observation is not converted to a loss/removal event.

## Rights and governance

The dashboard reads aggregate analytical marts and does not expose raw payloads, raw anchors, credentials, or provider responses. Capability state fails closed when the effective connection/default policy does not explicitly allow both derived display and aggregation. Governance counts preserve `ALLOWED`, `PROHIBITED`, and `UNKNOWN`; `UNKNOWN` is never permission. “Reviewed” means reviewed product-governance policy, not legal approval. This epic does not modify policy decisions.

## Cost semantics

Only existing cost-ledger rows are summed. A ledger-backed numeric zero is observed zero; missing ledger evidence is `UNKNOWN`. Paid-pipeline configuration is shown separately. Provisioning and validation make no provider calls and incur no provider cost.

## Metabase reproducibility and local setup

`dashboard/manifest.json` is the source of truth for collections, dashboards, cards, filters, and layout. SQL lives under `dashboard/questions/executive/`. `dashboard/provision.py` creates or updates collections, questions, dashboards, filters, and card placement through the API and validates every card. Repeated provisioning is idempotent by exact object name.

```bash
docker compose up -d db
alembic upgrade head
dbt seed --project-dir analytics --profiles-dir analytics
dbt build --project-dir analytics --profiles-dir analytics
docker compose up -d metabase
python dashboard/provision.py
```

Set `METABASE_ADMIN_EMAIL`, `METABASE_ADMIN_PASSWORD`, and `GIS_DB_PASSWORD` outside Git. A persisted Metabase volume keeps the credentials used at first initialization. If environment credentials drift, use the original volume credentials or deliberately reset/recreate the local volume yourself; provisioning never deletes it automatically.

## Filters and drill-down paths

Every card maps tenant/site/date filters. Supporting dashboards provide executive event → event/evidence detail, competitor → domain-specific observed facts, observed gap → source-specific gap evidence, and capability warning → operations/governance detail. Metabase native-SQL links are version-dependent, so the reproducible hierarchy and supporting dashboards provide the stable drill-down path.

## Known limitations and future integration

Evidence is sparse where collectors are manual, on-demand, unconfigured, or schedule-disabled. Paid SERP, external-search, and authority schedules remain disabled by default. Content, technology, experience, and competitive-event collectors may also require operator configuration. The dashboard truthfully displays those states.

Future epics can replace `NOT_IMPLEMENTED` registry entries with implemented structure and evidence models without redesigning the dashboard: opportunity detection populates DETECT; AI recommendations populate RECOMMEND; interventions/experiments and outcomes populate INTERVENE/MEASURE; learning populates LEARN. Market intelligence and emerging demand remain outside this epic.
