# Competitive Event Synthesis

Epic 19 turns already-collected competitive observations into provider-neutral factual events. It does not score opportunities, recommend actions, infer causality, crawl the public web, or contact paid providers.

## Ontology and semantics

Events are tenant/site scoped and identify a normalized subject (`DOMAIN`, `PAGE`, `QUERY`, `TECHNOLOGY`, `SERP_FEATURE`, `CONTENT_COMPONENT`, `SITE`, or `COMPETITOR`). Event domains are `SERP`, `SEARCH_VISIBILITY`, `CONTENT`, `TECHNOLOGY`, `EXPERIENCE`, `DOMAIN`, and `CROSS_SOURCE`.

The initial taxonomy covers SERP entry/exit/material movement and feature changes; keyword gain/loss and visibility movement; page appearance and material content, title, metadata, heading, component, schema, and word-count changes; first technology detection, supported additions, and version changes; material experience improvement/degradation; and conservative `COMPETITOR_PAGE_EMERGENCE` association. Technology non-detection never means removal, and no `TECHNOLOGY_REMOVED` type exists.

Every event declares one of four evidence semantics:

- `MEASURED`: a directly measured value.
- `PROVIDER_REPORTED`: a provider's explicit assertion or metric.
- `GIS_DERIVED`: deterministic comparison of stored evidence.
- `HEURISTIC`: deterministic but indirect evidence; consumers must preserve the distinction.

Confidence is capped by the least-confident contributing evidence. It is not an importance score.

## Evidence, identity, and corrections

`competitive_event_evidence` links every event to exact source table/asset and record identifiers with before/after/primary/supporting roles, observation time, semantic class, confidence, connection, ingestion run, and rights references. Provider payloads are not duplicated.

Identity is SHA-256 over tenant, site, normalized subject, event type, event boundary, synthesis method/version, and sorted evidence identities. `public_id` is UUIDv5 of that identity. A database uniqueness constraint makes historical reprocessing idempotent.

Events are append-oriented. State is `ACTIVE`, `SUPERSEDED`, or `RETRACTED`; correction reason and replacement are retained. Relationships (`SUPPORTS`, `PRECEDES`, `SUPERSEDES`, `SAME_CHANGE`, `CONSTITUENT_OF`) form a tenant/site-safe event graph. Self-links and duplicates are rejected.

## Versioned materiality

The default `gis-default-materiality` policy is version `1.0.0` and stored in `competitive_event_policy`. Defaults are inspectable JSON:

- rank movement: 3 positions, or any crossing of Top 3, Top 10, or Top 20;
- word count: 100 words or 15 percent;
- visibility: 0.05 absolute or 15 percent;
- experience: LCP/FCP 250 ms, INP 50 ms, TTFB 100 ms, CLS 0.05, score metrics 0.05;
- conservative cross-source association window: 14 days;
- one invocation is bounded to 366 days.

These thresholds decide whether a factual difference is worth recording, not whether anyone should act.

## Domain comparison behavior

Domain adapters compare ordered observations inside the requested bounded window. SERP rank direction respects that a lower numeric position is better. Set differences generate keyword and feature entry/exit. Content uses versioned hashes and typed document/heading/component/schema evidence. Technology emits only positive detection, addition, and version evidence. Experience knows whether lower or higher is better for each typed metric. Cross-source emergence requires compatible page-first-observed and SERP-entry evidence for the same tenant/site/page inside the configured window, and stores both events as constituents without a causal claim.

## Rights and provenance

Derived events never receive broader permissions than their evidence. Evidence-level rights references remain traversable through observation, ingestion run, connection, and source. Multiple or incomplete policies produce an effective `UNKNOWN`; downstream uses requiring explicit permission must fail closed. Synthesis itself has provider cost zero.

## Operations and CLI

Epic 18.5's existing orchestrator owns execution. The `competitive_events` pipeline depends on SERP, external-search, content, and technology pipelines and is seeded **disabled**. No second scheduler is introduced.

```bash
gis-orchestrator seed-vahomemath --confirm-disabled
gis-competitive-events types
gis-competitive-events synthesize --tenant vahomemath --site vahomemath --start-date 2026-08-01 --end-date 2026-08-30 --domains SERP CONTENT
gis-competitive-events reprocess --tenant vahomemath --site vahomemath --start-date 2026-01-01 --end-date 2026-08-30
gis-competitive-events timeline --tenant vahomemath --site vahomemath --domain CONTENT
gis-competitive-events inspect EVENT_UUID
gis-competitive-events evidence EVENT_UUID
gis-competitive-events relationships EVENT_UUID
```

All output is JSON and safely serializes UUIDs, dates/times, decimals, and enums.

## Analytics and limitations

dbt exposes an active-event timeline, evidence/confidence, daily domain/type counts, competitor/page/query activity, and seven-day event velocity. It intentionally contains no opportunity or importance score.

The initial engine only asserts changes supported by structured historical observations. Missing observations are not negative evidence, cross-source association is not causality, and rights `UNKNOWN` is not permission. Epic 7 may later consume these events for opportunity detection without changing this factual layer.
