# Opportunity detection

An opportunity is an evidence-supported condition that may warrant consideration. It is not a recommendation to act.

Epic 7 deterministically evaluates versioned Evidence Quality packages and records inspectable conditions, evaluation history, supporting evidence, lifecycle state, materiality components, priority components, and operator dismissals. It performs no provider calls and prescribes no action.

## Ontology and grain

Families are demand, visibility, competitive, content, authority, experience, market structure, and intelligence gap. The initial enabled registry contains `EMERGING_DEMAND_VISIBILITY_GAP`, `DEMAND_ACCELERATION_GAP`, and `HIGH_VALUE_EVIDENCE_GAP`. Authority, experience, competitive, content, and market-structure detectors are omitted until their evidence can be joined through a suitable evidence contract without bypassing the trust boundary.

Identity is tenant + site + market/version + opportunity type + analytical entity + evidence period + detector version. The canonical entity is the Epic 26.5 `analytical_entity`; no parallel identity system exists. Reprocessing identical evidence under `OPPORTUNITY_DETECTOR_V1` is a no-op.

## Trust, materiality, and priority

Each detector names an Evidence Quality contract. Rights other than `USABLE` and compatible unresolved conflicts prevent activation. `SUPPORTED` and `STRONGLY_SUPPORTED` may activate the two demand detectors; `LIMITED` may only produce `WATCHING`. Missing values are not treated as zero. Materiality and sorting priority remain separate named components, not probability, ROI, or a universal score.

The demand/visibility detectors additionally require the resolved entity metadata to state `owned_visibility=LOW`. A demand signal alone, including GSC impressions alone, cannot create these opportunities. Intelligence gaps remain visibly classified as evidence-collection questions and cannot be mistaken for website changes.

## Lifecycle

Computed states are `DETECTED`, `ACTIVE`, `WATCHING`, `RESOLVED`, `EXPIRED`, and `SUPERSEDED`; `DISMISSED` is an operator state. Dismissal preserves the computed state and an append-oriented override record; restore returns to that computed state. Missing, stale, or stopped collection never resolves an opportunity. Future evaluations may resolve only with sufficient comparable evidence. `detected_at` is deliberately separate from nullable `condition_first_observed_at`.

Evaluation history is kept in `opportunity_evaluation`; each qualifying evaluation references its Evidence Quality package through `opportunity_evidence`. Internal lifecycle history stays here rather than contaminating competitor-event semantics.

## CLI and operations

```bash
gis-opportunities types
gis-opportunities detect --tenant-id UUID --site-id UUID --dry-run
gis-opportunities list --tenant-id UUID --site-id UUID
gis-opportunities dismiss --opportunity-id UUID --reason "not in current scope"
gis-opportunities restore --opportunity-id UUID
```

All output is JSON. The disabled daily orchestration template depends on Market Intelligence, Collection Planning, Emerging Demand, and Evidence Quality with `ALWAYS` dependency semantics so sparse optional sources do not permanently block evaluation. Detection reads stored evidence, costs $0, and never enables collection.

The dbt products document current state, history, daily counts, family, market/version, entity, evidence trust, gaps, and resolution. The executive dashboard presents factual conditions, support, and limitations without recommended actions.

## Downstream contracts and limitations

Epic 9A can reference opportunity ID, analytical entity, machine-readable condition, package lineage, type, market context, materiality, priority, and limitations. Epic 8 can consume the same structure without parsing prose. Later learning can use immutable evaluations, dismissals, and detector versions to assess persistence and false positives.

Absence of detected opportunities means no configured detector qualified under the available evidence; it does not mean no growth opportunities exist.
