# Epic 26B: opportunity qualification and market resolution

## Finding

Epic 26A's zero-opportunity result was correct, but its three detectors all described temporal demand claims. Applying those policies to every package produced 60 classification failures (20 packages × 3 incompatible temporal classifiers), 40 missing-visibility metadata failures (20 × 2 visibility detectors), and 10 sufficiency failures. Counts describe individual failed gates, not failed packages.

## Claim-specific qualification

Detector version `OPPORTUNITY_DETECTOR_V2` declares `CROSS_SECTIONAL`, `LONGITUDINAL`, or `COMPOSITE` claim semantics and an explicit temporal requirement. Coverage and current-demand gaps can use trustworthy current-state evidence. Emerging demand and acceleration still require multiple observations; one observation can never establish velocity. Competitive Gap is defined but inactive until governed competition and coverage resolution are available. Declining demand, position movement, competitor change, and technology change remain explicitly unsupported rather than guessed.

## Deterministic market resolution

`MARKET_CONCEPT_RESOLVER_V1` creates a derived read model:

`raw query → normalized query → intent/modifiers → canonical concept → topic`

It preserves each raw target ID and every collection-evidence reference. Rules normalize known calculator misspellings and abbreviations while retaining year, military-service, geographic, and intent variants. Closing costs, affordability, funding fee, entitlement, residual income, DTI, VA payment, and BAH are separate concepts. Filename/path-like values such as `"bah-ascii-2026.zip"` are marked `SOURCE_ARTIFACT`; they are not deleted.

## Coverage and Market State

Coverage requires an explicit governed asset-to-concept assertion. No match means `UNKNOWN`, never `NO_COVERAGE`. A deterministic match records the method and matching assets. Opportunity diagnostics combine demand classification, sufficiency, source independence, rights, conflicts, resolved concept, coverage, visibility, and competition dimensions without collapsing them into an opaque score. Each value retains its evidence/package or raw-target provenance.

## Bootstrap readiness and planning

Bootstrap Readiness separates `WAITING_FOR_HISTORY` from blockers that time cannot fix. WAIT is valid only when additional already-authorized observations can satisfy the sole failed temporal gate. Coverage, metadata, classification, unsupported semantics, or missing sources receive distinct bounded actions. Plans remain advisory: they make no calls and change no targets, schedules, budgets, rights, or authorizations.

## Future governed reasoning boundary

A future `OpportunityPackage` may contain the opportunity ID/class, canonical concept, deterministic claim, detector, supporting evidence and provenance, inspectable market/coverage/competition/demand/temporal state, unknowns, rights constraints, sufficiency explanation, and permitted downstream uses. Epic 26B neither constructs an external prompt nor invokes an LLM.

## Limitations and next step

The current repository has no governed VAHomeMath asset-to-concept inventory, so absence of a mapping remains unknown. Sparse temporal history still blocks velocity claims. Competition claims remain inactive until current competitive evidence is resolvable at concept scope. Once real evidence qualifies a deterministic opportunity, the next appropriate stage is Epic 27 governed recommendation reasoning—not autonomous execution.
