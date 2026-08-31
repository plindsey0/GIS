# Intervention and experiment foundation

An intervention is a structured, measurable change or action. It is not a recommendation and does not imply authorization to execute.

Epic 9A defines the deterministic contract between an evidence-backed opportunity and possible future execution. It does not choose an intervention, call AI, approve work, execute changes, enable collection, or mutate customer sites. Every intervention directly references its Epic 7 opportunity and resolved analytical entity while preserving the market/version context used at creation.

## Ontology and approval boundary

The conservative registry includes content update, metadata change, page-experience improvement, CTA change, and evidence-collection expansion contracts. Each versioned definition declares applicable entity types, required typed parameters, supported metrics, execution mode, and `HUMAN_APPROVAL_REQUIRED` autonomy. AI recommendations may eventually create proposals but can never approve or execute them.

Lifecycle states are draft, proposed, approved, rejected, scheduled, in progress, completed, cancelled, measuring, measured, and archived. Valid transitions are explicit and append an audit event. Approval requires an actor. Rejection differs from cancellation, and intervention completion does not resolve the originating opportunity.

## Hypothesis and measurement

The hypothesis records a target metric, expected direction, resolved entity, and evidence rationale. It expresses an expectation, never a causal claim or guaranteed lift. Numeric magnitude remains nullable.

Measurement contracts are versioned and record a fixed pre-period baseline, explicit post period, washout days, comparison method, freshness, exclusions, and minimum evidence. Metrics retain provider-specific semantics and roles: primary, secondary, or guardrail. Baseline materialization reads only stored evidence; insufficient evidence returns `INSUFFICIENT_BASELINE` with a null value rather than zero.

Experiments remain separate from interventions. The schema supports observational before/after, A/B, holdout, matched-control, and time-series designs, but Epic 9A performs no assignment, power analysis, significance testing, or causal attribution. Privacy-preserving telemetry is unchanged.

Execution records distinguish intended parameters from what actually happened and allow manual, GIS-internal, GitHub, CMS, or external artifact references without implementing those integrations. Feasibility and measurement readiness are separate categorical states; unknown never means feasible or ready. Costs, effort, constraints, and multidimensional risks remain explicit and nullable rather than becoming an ROI or opaque score.

Outcomes are append-oriented and preserve baseline/post values, valid changes, evidence sufficiency, completeness, method version, and limitations. `causal_attribution` is always false in this epic. Observed post-intervention change does not by itself establish causal impact.

## Operations and interfaces

`gis-interventions types` and `gis-interventions metrics` expose machine-readable registries. List, lifecycle, baseline, blocker, readiness, history, and outcome commands return JSON. The disabled daily measurement pipeline depends on Opportunity Detection and performs no autonomous execution or provider collection. Missing measurement evidence must flow through Collection Planning in later implementation.

dbt marts expose current contracts, lifecycle history, type/opportunity summaries, readiness, execution, outcomes, experiments, and blockers without fanout. The executive dashboard labels outcomes as observed and does not imply impact caused.

Epic 8 can query valid types, parameters, metrics, constraints, feasibility, and readiness to build human-reviewed candidates. Epic 9B can extend experiment arms, assignments, statistical methods, and attribution. Epic 27 can learn from opportunity, proposal, approval, execution fidelity, observed outcome, evidence, effort, and latency history.

With sparse data GIS reports zero interventions and experiments, and insufficient baselines. It never creates examples merely to populate a dashboard.
