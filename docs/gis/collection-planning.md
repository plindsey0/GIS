# Collection Planning and Target Management

## Purpose and boundary

Collection Planning is the deterministic control plane between a versioned Market Intelligence definition and GIS orchestration. It discovers scoped targets, explains the value of acquiring more evidence, selects compatible collectors, forecasts cost, evaluates rights and budgets, and produces desired collection state. It does not execute provider calls during planning and does not recommend a growth action.

**Collection priority represents the value of acquiring additional intelligence, not the value of taking a growth action.**

The flow is market definition → discovery evidence → target → immutable evaluation → target×collector plan item → explicit apply → disabled scheduler target/template → operator activation → later ingestion evidence. Planning state is operational evidence, not competitor behavior, so this epic does not create Competitive Events for internal planner changes.

## Target ontology and identity

`collection_target` supports `QUERY`, `DOMAIN`, `URL`, and `TOPIC`. Every target belongs to one tenant, site, market-definition ID, and frozen market-definition version. Identity is a SHA-256 digest over that scope, type, normalized value, and query geography/language/device. Queries reuse SERP normalization; domains and URLs reuse existing GIS normalization. Provider identifiers never become canonical identities.

Lifecycle states are `CANDIDATE`, `ACTIVE`, `DORMANT`, `PAUSED`, `REJECTED`, and `RETIRED`. Discovery never directly activates paid collection. Retirement preserves targets, evidence, decisions, and observations.

## Discovery and provenance

The v1 discovery service consumes stored evidence only:

- Frozen Market Intelligence tracked-query members establish primary market relevance.
- GSC observations nominate measured owned queries and retain clicks/impressions as metadata; they do not become total market demand.
- SERP results nominate observed participant domains and ranking URLs.
- Market participant observations provide derived market-overlap evidence.
- Operators may add small `HUMAN_SUPPLIED` seeds with actor and reason.

The evidence model is provider-neutral and admits external search, content, technology, authority, and competitive-event evidence without changing target identity. Each evidence link records its source, observation identifier, timestamp, semantic class, signal, value, and metadata without copying raw payloads. Content/technology/authority/event evidence can be attached conservatively as those local datasets become populated; detection alone is never treated as business relevance.

## Priority policy

`COLLECTION_PRIORITY_V1` stores component values and missing components separately. Unknown is never converted to zero. The v1 known-signal normalized weighted formula is:

| Component | Weight |
|---|---:|
| Market relevance | 0.30 |
| Owned-site signal | 0.20 |
| Competitor signal | 0.15 |
| Change signal | 0.10 |
| Information gap | 0.15 |
| Strategic human seed | 0.10 |

Only available components participate in the denominator. This avoids penalizing a target merely because a provider is absent. Scores map to `CRITICAL` (≥0.90), `HIGH` (≥0.75), `MEDIUM` (≥0.55), `LOW` (≥0.35), or `DISCOVERY`; no evidence maps to `DORMANT`. The score, components, unknown list, evidence count, policy version, and explanation are persisted for every decision.

Activation requires at least two independent evidence records and score ≥0.65. Active targets demote below 0.35; dormant targets reactivate at ≥0.70. The separate thresholds provide deterministic hysteresis. Rejected/retired targets never reactivate automatically.

## Cadence and collector selection

`COLLECTION_CADENCE_V1` maps critical/high/medium/low/discovery/dormant to daily/twice-weekly/weekly/monthly/on-demand/none. Actual cron lives in the established scheduler. Collector capabilities map target type to a pipeline and evidence product:

- Query: SERP and external search
- Domain: external search, technology, and authority
- URL: content, technology, and experience
- Topic: deliberately has no direct collector in v1

Capabilities are provider-neutral and use existing pipelines, sources, connections, and credential references. A target can have multiple plan items. An unavailable optional collector remains explicitly blocked without invalidating another eligible collector.

## Rights, budgets, and costs

The planner uses the effective connection policy and requires normalized retention to be explicitly `ALLOWED`. `DENIED` and `UNKNOWN` fail closed. Discovery rights and future collection rights remain distinct.

Known-free local collectors explicitly forecast `$0`. A paid pipeline whose configured default is zero is treated as **unknown cost**, not free. Per-run and monthly limits reuse `cost_budget`; incompatible currency or exceeded limits produces `BUDGET_BLOCKED`. Forecast marts preserve known cost and unknown-cost item counts separately.

Target-level explanations distinguish `BLOCKED_BY_RIGHTS`, `BUDGET_BLOCKED`, `NO_PROVIDER`, `INSUFFICIENT_EVIDENCE`, `UNKNOWN_COST`, and operator pause. A high computed priority remains visible even when effective state is paused.

## Plan versus apply

`plan` creates an immutable, fingerprinted planning run and target decisions. Identical evidence, policy, override, and collector state returns the existing run rather than producing churn. Computed status/cadence remain separate from effective status/cadence.

`apply` is explicit. It updates the target's current lifecycle and reconciles plan items into existing `scheduled_target` records. Planner-created schedule templates are always `DISABLED` and labeled `requires_operator_activation`; apply never enables a production schedule. Scheduler state remains authoritative for execution, while planning remains authoritative for desired state. Every reconciled target records its planning-decision ID and applying actor.

## Human overrides

Overrides support force-active, force-paused, force-retired, priority, cadence, and collector. They record actor, reason, time, forced value, clearing actor/time, and remain in history. The planner continues to store its unmodified computed result alongside the effective overridden result. Overrides cannot make unknown/denied rights or unknown/exceeded cost silently permissible.

## CLI

The JSON-first command is `gis-collection-planning`:

```bash
gis-collection-planning discover <market-definition-uuid> --dry-run
gis-collection-planning plan <market-definition-uuid> --dry-run
gis-collection-planning explain <target-uuid>
gis-collection-planning costs <planning-run-uuid>
gis-collection-planning blockers <planning-run-uuid>
gis-collection-planning apply <planning-run-uuid> --actor operator --dry-run
```

Additional commands are `seed`, `evaluate`, `inspect`, `targets`, `candidates`, `history`, `collectors`, `override`, and `clear-override`. Dry-run rolls back all writes and makes zero provider calls. Work is bounded to 10,000 discovery/evaluation rows and list output is capped.

## Analytics and dashboard

Staging models expose targets, evidence, runs, decisions, plan items, capabilities, and overrides. Marts provide current targets, immutable history, current target×capability plan, priority distribution, cost forecast, blockers, known-target market coverage, and provider mix. `KNOWN_TARGET_COVERAGE` never claims discovery completeness; `MARKET_DISCOVERY_COMPLETENESS` remains `UNKNOWN`.

The capability registry and reproducible `GIS Collection Planning` dashboard show target state, priorities, blockers, overrides, and known/unknown forecast cost. Raw credentials and payloads are never displayed.

## Minimal bootstrap

1. Create or select a frozen Epic 11 market definition.
2. Optionally register a few human seeds—never a hard-coded VA-specific list.
3. Run `discover --dry-run`, inspect, then persist discovery.
4. Run `plan --dry-run` and inspect `explain`, `costs`, and `blockers`.
5. Apply an approved run explicitly.
6. Review disabled scheduler templates, connections, rights, and budgets.
7. Enable only the specific schedules approved for production.

## Limitations and extension points

V1 discovery directly operationalizes market members, GSC, SERP, market participants, and human seeds. Local external-search, content, technology, authority, and event datasets may be sparse; their identifiers can already be attached as evidence without schema redesign. Provider cost is frequently unknown until a real price is configured, which intentionally blocks activation. Topic collection has no direct collector.

Epic 26 can add emerging-demand evidence components; Epic 7 and Epic 8 can request evidence without changing priority semantics; Epic 9A can create monitoring targets; Epic 27 can compare historical collection decisions with later decision value. No LLM, learned ranking, opportunity score, intervention, publishing action, or decision-value optimization is implemented here.
