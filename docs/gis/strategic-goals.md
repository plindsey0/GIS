# Strategic goals and deterministic objective decomposition

Epic 25 gives GIS an explicit objective function while preserving human authority. A user defines and activates Business Goals. GIS may measure those goals and propose subordinate objectives only through versioned deterministic rules using governed, rights-cleared, sufficiently fresh inputs. Missing information stops decomposition; it is never replaced with zero or an assumption.

## Objective hierarchy and alignment

The semantic levels are Business Goal, Strategic Growth Goal, Channel or Market Goal, and Tactical Target. They sit above the existing Opportunity → Recommendation → Intervention → Experiment → Outcome lifecycle and do not rename it.

Alignment is a directed acyclic graph. `objective_relationship` supports many-to-many `SUPPORTS` edges, while the domain service rejects self-links and cycles. This permits one measurable improvement to support multiple higher-level outcomes.

## Authority and provenance

- `USER_DEFINED` Business Goals may be drafts or explicitly activated by an operator.
- `DETERMINISTIC` subordinate objectives begin proposed and pending approval.
- `STATISTICAL` and `AI_PROPOSED` are forward-compatible provenance labels only; database constraints prevent them becoming active authoritative objectives.
- A user override preserves both the calculated suggestion and the selected value, with rationale and audit history.

Lifecycle, progress, measurement health, decomposition state, and approval are independent fields. Measurement presentation additionally separates four questions: whether GIS supports the metric, whether the goal has an authoritative source binding, whether a current value exists, and whether that value is usable and fresh. A supported binding with no value is `INSUFFICIENT_DATA`, not a claim that the metric is unavailable. A stale target can have `UNKNOWN` progress; a valid goal can have `BLOCKED_MISSING_DATA` decomposition.

## Persisted model

- `strategic_objective`: user and derived objectives, authority, lifecycle, scope, and state.
- `objective_relationship`: queryable DAG edges.
- `objective_target`: metric-specific measurement contracts and guardrails.
- `objective_measurement`: append-oriented, idempotent target snapshots with data-asset, rights, freshness, method, and effective-version context.
- `decomposition_plan`: candidate, approved, rejected, or superseded strategic paths.
- `decomposition_rule`: versioned formulas, supported semantics, required metrics, rights/readiness policy, and approval requirement.
- `objective_derivation`: immutable historic calculation inputs, outputs, provenance, blocker, and supersession.
- `objective_audit_event`: material lifecycle, approval, target, alignment, override, and decomposition history.

The existing `intervention_metric_definition` registry is generalized for both intervention measurement and strategic objectives. It now records domain, description, directionality, aggregation, supported scopes, authoritative data asset, measurability, derivation status, and freshness expectation.

## Executable rule

`REVENUE_TO_REQUIRED_TRAFFIC` version 1 computes:

```text
required qualified visitors = monthly revenue target / revenue per qualified visitor
```

It executes only when the user has supplied a monthly revenue target and GIS has an authoritative current revenue-per-qualified-visitor measurement whose policy explicitly allows deterministic analysis and derived storage. VAHomeMath currently has no such financial measurement, so the production-safe result is `BLOCKED_MISSING_DATA` or `BLOCKED_RIGHTS`, not an invented traffic target.

Identical parent, rule version, and input measurement identity returns the same derivation. A changed input creates a new proposed subordinate objective, marks the prior derivation superseded, and preserves the unchanged Business Goal.

## API and operator workflow

The `/api/v1/goals` API supports scoped creation, listing, detail, update, activation, pause, archive, approval/rejection, targets, relationships, decomposition/recalculation, metric discovery, target measurements, and the objective map. `GET /api/v1/goals/metrics?goal_type=…` applies the versioned `goal-metric-policy-v1` policy to return explainable, availability-aware measurement recommendations. These recommendations only help the operator choose a measure; they never create a goal or claim that a target is achievable. Mutations require review or approval roles and emit audit records. There is no destructive goal delete route.

The `/goals` Workbench section is permanently available in primary navigation. Its guided six-step flow starts with plain-language business intent, recommends suitable measures, presents only supported site scope, separates measurement capability from current data, explains decomposition without requiring internal enum knowledge, and ends with distinct draft and activation decisions. Goal detail presents strategic summary, progress, measurement, decomposition, alignment, target authority, and history without exposing database identifiers. The CLI entry point remains `gis-goals`.

No Business Goals are seeded. Tests use transaction-isolated synthetic financial fixtures only.

## Future work

Statistical relationship estimation, AI-proposed candidate strategies, goal-aware opportunity prioritization, and sophisticated alternative plan generation are intentionally outside Epic 25. Future reasoning must remain provenance-labeled, evidence- and rights-governed, deterministically checked, and subject to human approval.
