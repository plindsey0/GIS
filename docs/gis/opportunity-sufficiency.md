# Opportunity sufficiency

Epic 26A adds a deterministic, read-only sufficiency layer over the published opportunity detectors. It does not add a detector, change a threshold, synthesize evidence, invoke AI, or execute collection.

`gis.opportunities.service.DETECTORS` and `OPPORTUNITY_DETECTOR_V1` remain authoritative. The read model evaluates every governed evidence package against every detector. Each condition records required and observed values, its hard-gate result, a remediation class, and a bounded next action.

Readiness is gate-aware, not a percentage: `NOT_READY`, `WAITING_FOR_HISTORY`, `COLLECTION_REQUIRED`, `PROCESSING_REQUIRED`, `NEAR_QUALIFIED`, `QUALIFIED`, or `BLOCKED`. Counts such as “five of six” aid navigation but never override a failed hard gate. `FIRST_OBSERVED` is insufficient for emergence or acceleration; additional real observations must establish longitudinal change.

## Interfaces

- `gis-opportunities detectors` lists the published inventory.
- `gis-opportunities diagnose --tenant-id … --site-id …` evaluates the complete matrix.
- `gis-opportunities candidate --tenant-id … --site-id … --package-id …` explains one candidate.
- `gis-opportunities baseline --tenant-id … --site-id …` produces a regenerable combined report.
- Workbench Opportunities shows failures, closest candidates, bounded collection actions, and the target portfolio.

Only `gis-opportunities detect` uses normal production logic to create qualified opportunities. Diagnostic commands are read-only. `READY_FOR_RECOMMENDATION` means the detector qualifies and referenced evidence is rights-usable; it does not invoke an LLM or approve action.

Diagnostics use explicit remediation classes: `WAIT`, `COLLECT`, `EXPAND_TARGETS`, `ENABLE_SOURCE`, `AUTHORIZE_TARGET`, `RESOLVE`, `DERIVE`, `FIX_PIPELINE`, `RIGHTS_BLOCKED`, `STALE`, `THRESHOLD_NOT_MET`, and `BLOCKED`. Collection and authorization remain operator decisions.
