# Emerging Demand Intelligence

Epic 26 is the deterministic intelligence layer between Market Intelligence, Collection Planning, and future opportunity detection. It describes changes in stored, observable demand without deciding what the organization should do.

> **Newly observed demand is not necessarily newly emerging demand.**

> **Emerging Demand describes changes in observable demand. It does not determine whether those changes constitute a growth opportunity.**

## Semantics and boundaries

Provider-reported volume is primary demand evidence only within its recorded provider, metric, geography, language, device, resolution, method version, and market-definition version. Metrics from different providers are retained as separate series and are never averaged into a universal demand score. GSC impressions are an owned-property exposure signal, not total market demand. SERP occurrence and competitor activity can corroborate a conclusion but do not establish demand magnitude.

V1 materializes already-stored External Search keyword-volume rows for market-scoped collection targets. It performs no retrieval. Market Intelligence, Collection Planning, GSC, SERP, and competitive assets are registered in lineage; only semantically compatible primary-demand series establish directional classifications, while the others remain coverage or corroborating extension points.

Missing evidence remains unknown. A stored zero is meaningful only when a provider explicitly reported zero. `FIRST_OBSERVED` means GIS first saw the evidence; it does not mean demand began then. Explicit coverage states distinguish `NOT_COLLECTED`, `NOT_OBSERVED`, `NO_DEMAND_OBSERVED`, `INSUFFICIENT_HISTORY`, partial coverage, and collection-regime changes.

## Historical model and provenance

`gis_raw.demand_observation` is append-oriented and revision-aware. A compatible series has identical source, metric, unit, resolution, geography, language, device, method/version, entity, and market-definition version. `observation_key` identifies the logical provider observation; `content_hash` identifies its revision. Current revisions have no `effective_end`.

`demand_analysis_run` fingerprints current allowed evidence plus policy version. The same evidence and policy is a no-op. Each `demand_signal` links through `demand_signal_evidence` to its source observations. Changed evidence or policy produces a new reproducible run rather than rewriting prior conclusions.

Derivative creation fails closed through the existing rights-policy model. Evidence whose derivative-creation right is unknown or denied is excluded and recorded in run metadata. Existing reviewed rights policies are not modified.

## Temporal analysis

Policy `EMERGING_DEMAND_V1` supports named 7-, 28-, and 90-day windows as extension points, but calculations use the actual source resolution. Monthly evidence is never given pseudo-daily precision.

Velocity is `(current value - prior comparable value) / elapsed days`. Relative change is omitted when the prior denominator is zero. Acceleration requires at least three comparable points and is the change in consecutive velocities divided by elapsed days. Sustained directional classification requires at least four continuous observations.

## Classification policy

The ontology includes `FIRST_OBSERVED`, `EMERGING`, `GROWING`, `ACCELERATING`, `DECELERATING`, `DECLINING`, `STABLE`, `SPIKE`, `REVERSAL`, and `INSUFFICIENT_HISTORY`. V1 only emits states deterministically supported by available history.

V1 uses documented thresholds:

- directional relative change: 15 percent;
- stable band: 5 percent;
- acceleration: 0.005 source units per day squared;
- spike: current value above rolling median plus three median absolute deviations;
- minimum velocity history: two points;
- minimum acceleration history: three points;
- minimum sustained classification history: four points.

Emergence additionally requires sustained positive comparable-period movement from a demonstrably low observed baseline. Absence before collection began is never treated as absence of demand. Changed cadence, target activation within the evidence window, incompatible context, or discontinuous collection suppresses directional classification as insufficient history. This deliberately favors false negatives over manufactured trends.

Evidence strength is categorical rather than a universal score: `INSUFFICIENT`, `LIMITED`, `SUPPORTED`, or `STRONGLY_SUPPORTED`. It is based on historical depth, continuity, and distinct corroborating roles. Primary demand, owned-site support, competitive support, and collection-coverage evidence remain separate facts.

## Topics, segments, and markets

The schema supports query, deterministic topic, market-segment, and market signals. Topics and segments must reuse frozen Epic 11 membership and method versions. Overlapping memberships must be resolved before aggregation to prevent double counting. Market outputs must state partial coverage and never extrapolate a sampled subset into total market growth.

## Collection Planning feedback

Demand analysis writes `change_signal` evidence to the existing collection target evidence model. It may also create a `demand_validation_request` describing the target, reason, desired evidence capability, urgency, expiration, originating signal, and provenance. This is a planning input only.

Emerging Demand never mutates a schedule, activates a collector, calls a provider, or spends budget. Epic 10.5 remains responsible for rights checks, cost estimation, budget decisions, cadence, and explicit plan application.

No events are emitted in V1. The existing synthesized event model is explicitly competitive-event scoped, so inserting internal demand signals there would contaminate its semantics. Durable `demand_signal` rows are the factual event-like interface until a general internal intelligence-event path exists.

## Orchestration and CLI

The disabled `emerging_demand` weekly template depends on Market Intelligence and Collection Planning with `ALWAYS` semantics so optional sparse evidence does not permanently block analysis. It is not enabled by bootstrap.

```bash
gis-emerging-demand analyze --tenant-id UUID --site-id UUID --market-id UUID --dry-run
gis-emerging-demand inspect --tenant-id UUID --site-id UUID
gis-emerging-demand emerging --tenant-id UUID --site-id UUID
gis-emerging-demand accelerating --tenant-id UUID --site-id UUID
gis-emerging-demand declining --tenant-id UUID --site-id UUID
gis-emerging-demand spikes --tenant-id UUID --site-id UUID
gis-emerging-demand validation-requests --tenant-id UUID --site-id UUID
gis-emerging-demand reprocess --tenant-id UUID --site-id UUID --market-id UUID
```

All output is JSON-safe for UUIDs, timestamps, dates, decimals, and enums. Analysis and estimation make zero provider calls. `--dry-run` rolls back derived writes.

## Analytics and dashboard

Five staging models preserve observations, runs, signals, evidence links, and validation requests. Ten marts expose query history/trends, deterministic topic/segment/market series, emerging, acceleration, spike, decline, and evidence-coverage views without fanout. The focused dashboard labels first-observed evidence separately and surfaces partial coverage.

## Current limitations and downstream use

The initial local dataset may have insufficient compatible history. Correct output is `FIRST_OBSERVED`, `INSUFFICIENT_HISTORY`, `NOT_COLLECTED`, `PARTIAL_COVERAGE`, or `UNKNOWN`; the system does not fabricate observations to populate dashboards.

Future Evidence Quality may assess source reliability, completeness, consistency, and entity resolution. Future Opportunity Detection may consume the factual signal, velocity, acceleration, market context, evidence strength, and coverage. Neither layer should reinterpret provider metrics as universal demand. Google Trends and other sensors remain provider-neutral extension points and require separate rights, credentials, and cost review.
