# Governed evidence-gap adjudication

Epic 28E adds a deterministic, provider-free decision layer between evidence collection and downstream intelligence reassessment. Collection completion is never treated as proof that a gap is closed.

Each adjudication is tenant/site scoped, immutable, versioned, and linked to the exact governed evidence packages and reference IDs evaluated. Exact replay is idempotent; a changed evidence state creates a new current version linked to its predecessor.

## Outcomes

- `SATISFIED` requires exact identity and scope, usable rights, compatible methods, adequate freshness, supported sufficiency, capability-specific evidence, and no unresolved material conflict. It is the only outcome that closes the gap.
- `PARTIALLY_SATISFIED` preserves useful but limited, stale, incomplete, or not-yet-ready evidence without overstating it.
- `STILL_INSUFFICIENT` keeps the gap open when the required claim cannot be supported.
- `CONFLICTING_EVIDENCE` exposes material governed disagreement for review.
- `BLOCKED` exposes hard rights, scope, identity, method, or policy constraints.

Owned-page observation does not establish query intent or ranking merit. Exact-query SERP observation does not establish page quality or intent satisfaction, and absence within collected depth is not absence from search. Query/page association, targeting, and intent satisfaction remain separate assertions.

## Operator workflow

1. Open an evidence-gap detail to inspect its required capability and collection lineage.
2. Submit only already-persisted governed evidence package and reference IDs to `POST /api/v1/evidence/gaps/{gap_id}/adjudications` with `tenant_id` and `site_id` scope.
3. Inspect current status, reasons, accepted and rejected evidence, checks, limitations, remaining requirements, conflicts, and recommended next action.
4. Add an append-only `CONFIRM`, `DISAGREE`, or `NEEDS_MORE_EVIDENCE` review at `POST /api/v1/evidence/gap-adjudications/{adjudication_id}/reviews` when human review is required.
5. Read the current decision at `GET /api/v1/evidence/gaps/{gap_id}/current-adjudication`, immutable history at `GET /api/v1/evidence/gaps/{gap_id}/adjudications`, or filter current adjudications at `GET /api/v1/evidence/gap-adjudications` by outcome, capability, entity, market, review state, or reassessment eligibility.

Read APIs never collect evidence, invoke an LLM/provider, create an experiment, or create an intervention. Adjudication itself performs no network operation and cannot start collection. Technical IDs and fingerprints remain available in collapsed secondary detail in the Workbench.

## Reassessment governance

Only a valid `SATISFIED` adjudication sets `EvidenceGap.resolved_at`. A linked collection requirement is reconciled through the same adjudicator. For semantic interpretations that require human review, deterministic satisfaction may close the evidence gap while downstream intelligence use remains gated until a `CONFIRM` review. Reviews never rewrite the deterministic outcome or prior review history.
