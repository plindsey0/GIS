# Market Intelligence

## Purpose and architectural position

Market Intelligence is GIS's historical EVIDENCE/UNDERSTANDING layer above SERP, external search, content, technology, authority, and competitive-event evidence and below Emerging Demand and Opportunity Detection. It describes an explicitly defined observable digital/search market. It does not decide what to pursue, recommend work, estimate economic TAM/SAM/SOM, or make causal claims.

An observable digital/search market is not necessarily an economic market. Search visibility is not revenue market share, competitor labels are analytical rather than business or legal conclusions, and no opportunity scoring occurs in Epic 11.

## Definition of a GIS market

`gis_core.market_definition` is one immutable analytical scope version. The `(tenant_id, site_id, slug, version)` key identifies it; `supersedes_id`, `effective_at`, and `superseded_at` preserve lineage. Creating a changed definition creates a new row/version and freezes a new member list. Existing observations continue to reference their exact definition ID and version.

`market_definition_member` stores typed included/excluded identities, optional weights, rank, effective window, and provenance. The first supported construction method uses frozen `TRACKED_QUERY` identities. The schema also admits query patterns, topics, domains, pages, competitors, and manual seeds without changing historical rows. Historical comparisons across different definition IDs/versions are not treated as market change.

## Observation and provenance semantics

`gis_raw.market_observation` is a revision-aware synthesis envelope for a definition/date/geography/language/device/method. It records configured and observed query counts, coverage status, source counts, effective rights policy/version, content identity, cost, and source-policy provenance. Identical reruns are idempotent; changed evidence closes the prior effective row and appends a revision.

Participant, segment, and metric observations are typed child facts. They preserve method and semantic class rather than placing stable concepts in JSON. `market_metric_definition` gives every canonical metric a durable name, formula description, unit, method key/version, and semantic class.

The initial service synthesizes stored evidence only. It makes no provider calls. SERP observations/results provide measured organic participation. External-search rankings contribute provider-reported search volume only when already stored. GSC impressions are intentionally excluded from total market demand: they are owned-property performance, not total demand.

## Demand and visibility methods

Implemented measures include:

- `OBSERVED_QUERY_COUNT` and `OBSERVED_DOMAIN_COUNT`: measured within the frozen query universe.
- `TOTAL_PROVIDER_SEARCH_VOLUME`: provider-reported, deduplicated by normalized query, incomplete, and null when unavailable.
- Reciprocal-rank visibility: each organic position contributes `1 / rank`; domain share is its weight divided by total observed weight. Method `RECIPROCAL_RANK_VISIBILITY:1.0.0` is GIS-derived and does not predict clicks.
- Provider-volume-weighted visibility: provider search volume multiplied by reciprocal rank. It remains separate and null without provider volume.
- Owned visibility share: owned domain reciprocal-rank share within the defined observed universe. This is not economic or revenue market share.

No provider traffic estimate is treated as analytics ground truth. Future Similarweb/Ahrefs/Semrush/DataForSEO Labs fields can retain provider and methodology without changing the current method.

## Participant and competitor model

Participants are normalized SERP hostnames using the existing SERP ownership taxonomy. Continuous query overlap is retained alongside deterministic labels:

- `OWNED`: existing SERP ownership identifies the site.
- `DIRECT`: at least two observed queries and overlap at least 0.50.
- `ADJACENT`: overlap at least 0.20.
- `PERIPHERAL`: narrower positive overlap.
- `UNKNOWN`: insufficient evidence.

`EMERGING` is reserved for a future comparable-history rule and is not inferred from one snapshot. One SERP appearance cannot produce `DIRECT`. These thresholds are `QUERY_OVERLAP_THRESHOLDS:1.0.0` and are factual labels, not strategic judgments.

Participant facts include query/page/appearance counts, top-3/top-10/top-20 appearances, both visibility methods, overlap, first/last observation, and ownership. Content, technology, authority, and event marts remain available for descriptive downstream joins; they are not collapsed into an overall competitor score.

## Concentration and fragmentation

Observed HHI is `sum(visibility_share²)`. Effective participant count is `1 / HHI`. Analytical marts also expose top-1/top-3/top-5 share, observed participant count, median share, long-tail share, recurring domains, average queries per domain, and domain concentration. These describe the observed SERP universe and must not be interpreted as economic concentration or an antitrust conclusion.

## Segments and intent

The initial segment model uses deterministic, versioned lexical intent rules for informational, navigational, commercial investigation, transactional, tool/calculator, research/data, local, and unknown queries. The classification is explicitly `HEURISTIC`; original tracked-query identities remain intact. Segment marts expose observed query/participant count, optional provider-reported volume, and observed visibility HHI. They never rank segments as opportunities.

Brand/non-brand classification is not enabled because the current site model has no canonical brand/alias registry. GIS does not infer brand identity from a title or fuzzy match. A future explicit alias source can populate `OWNED_BRAND`, `COMPETITOR_BRAND`, `NON_BRAND`, `MIXED`, and `UNKNOWN` safely.

## Coverage and history

Query coverage is observed frozen queries divided by configured frozen queries:

- `COMPLETE`: 1.0
- `PARTIAL`: at least 0.5 and below 1.0
- `SPARSE`: above zero and below 0.5
- `UNKNOWN`: no configured queries or no evidence
- `STALE`: reserved for orchestration/freshness evaluation rather than inferred from an empty date

Missing evidence is not zero. Provider search volume remains null with `NO_PROVIDER_VOLUME_DATA`. A market observation can therefore contain a measured zero participant count while still exposing weak/absent query coverage. Historical change models partition by definition ID/version and method key/version; definition changes are not silently compared.

## Rights and costs

Synthesis fails closed unless the selected synthesis policy and every contributing SERP/external-search policy explicitly allow deterministic analysis, derived storage, and aggregation. Restriction order is effectively prohibited/denied, then unknown, then allowed. Source policy IDs are retained in provenance. This epic does not change reviewed policies or grant display, publication, redistribution, export, RAG, inference, or training rights.

Stored-evidence synthesis has estimated provider cost `$0` and provider-reported cost null. Dry runs and tests make zero provider calls. Optional future enrichment must record actual cost separately.

## Orchestration

The versioned cadence adds a disabled `market_intelligence` weekly template. SERP, external search, content, technology, competitive events, and authority are recorded as `ALWAYS` dependencies: they preserve ordering/lineage but intentionally do not block synthesis when optional or paid evidence is absent. The pipeline stays operator-configured and disabled by default. It supports manual runs and bounded orchestration/backfills through the existing collector CLI adapter.

## CLI

`gis-market-intelligence` is JSON-first and supports:

- `define`, `list`, `inspect`, `members`, `validate`
- `estimate`, `observe`, `build`
- `segments`, `participants`, `visibility`, `structure`, `compare`, `history`, `coverage`

Definition and observation commands enforce tenant/site/definition scope. Definitions are bounded to 500 members; estimate is bounded to 366 dates. `--dry-run` performs no provider activity and persists nothing. UUID, date, Decimal, and enum values serialize safely, and no credentials are returned.

## dbt and dashboard integration

Staging models expose definitions, observations, participants, segments, and metrics. Market marts provide daily state, participants, method-separated visibility, concentration/fragmentation, segments, coverage, demand distribution, overlap, SERP structure, competitors, and version-safe change. Tests enforce grains, accepted semantics, versions, no-data states, and non-prescriptive labels.

Epic 20.5's capability registry now marks `MARKET_INTELLIGENCE` implemented. Runtime state is derived from actual observations, schedules, rights, freshness, failures, and alerts. The reproducible `GIS Market Intelligence` dashboard shows overview, participants/visibility, structure, segments, coverage, and comparable history; the executive page adds one compact observable-market table.

Market-level Competitive Event types are intentionally deferred until multiple comparable, sufficiently covered observations exist. Current market history is consumable by the versioned synthesis framework without inventing changes from definition drift or sparse snapshots.

## Local workflow

```bash
alembic upgrade head
dbt build --project-dir analytics --profiles-dir analytics
gis-market-intelligence define --tenant vahomemath --site vahomemath --name "VAHomeMath observable search market" --slug vahomemath-search --tracked-query <uuid> --dry-run
gis-market-intelligence observe <definition-uuid> --date YYYY-MM-DD --rights-policy <uuid> --dry-run
python dashboard/provision.py
```

Remove `--dry-run` only after reviewing the frozen members and selecting an explicitly allowed tenant policy. No provider credential is required.

## Limitations

The market is limited to the current frozen tracked-query universe and exact-date stored evidence. One SERP snapshot is not stable market truth. Provider keyword databases and search volume are incomplete; missing rows do not mean zero. External search and authority evidence may be absent locally. Content, technology, authority, and events are not yet joined into participant rows because their different grains and coverage could create misleading fanout. Similarweb, Ahrefs, Semrush, DataForSEO Labs, Google Trends, imported research, explicit brand aliases, shared-SERP clustering, and carefully versioned market events are provider-neutral future extensions—not prerequisites for a correct initial market.
