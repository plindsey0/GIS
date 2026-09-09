# Governed investigation and collection handoff

GIS closes the evidence-learning loop without creating autonomous execution:

`authoritative evidence → evidence gap → opportunity → recommendation → proposal → human
approval → collection requirement → candidate collection plan → separately authorized
collection → observation → evidence package → deterministic reassessment → explicit
intelligence rerun`

No approval, derivation, promotion, or reassessment operation invokes an LLM, provider,
collector, crawler, browser, or intervention executor.

## Decision artifacts

- An **opportunity** is something potentially worth investigating or acting upon.
- A **recommendation** is a proposed course of action or investigation based on governed evidence.
- An **investigation proposal** reduces uncertainty through observation, collection, audit,
  verification, or analysis without intentionally changing the target system.
- An **experiment proposal** applies a bounded treatment and measures an outcome.
- An **intervention** is a separately authorized executable target-system change.

The existing proposal resource and URLs remain compatible. The additive `proposal_type` field
defaults existing and new records to `EXPERIMENT`. An operator must explicitly choose “Classify
and approve investigation”; GIS does not infer that decision from model prose or rewrite history.

## Collection artifacts and mapping

- An **evidence gap** records a known deficiency in decision evidence.
- A **collection requirement** is a governed statement of evidence GIS needs, retaining proposal,
  recommendation, opportunity, entity, gap, target, market, human-review, and rights lineage.
- A **collection plan** describes the separately reviewable provider, method, cadence, blocker,
  and cost posture.
- An **observation** is an authoritative collection result.
- An **evidence package** evaluates observations for sufficiency, quality, provenance, scope,
  and rights.

Derivation is idempotent. `OWNED_PAGE_CONTENT` maps to existing `CONTENT_URL` capability and
`EXACT_QUERY_SERP` maps to `SERP`. Exact URLs and queries are preserved; related queries are not
substituted. Unmapped needs remain `UNSUPPORTED` rather than inventing a collector.

The content mapping requests HTTP/canonical/indexability/content/title/headings and structured
data where supported. Browser interaction, formal accessibility conformance, and calculator
correctness are explicitly unsupported. SERP planning retains country, language, and device and
may surface a paid provider, but does not authorize it. Cost is `FREE_LOCAL`, `KNOWN_PAID`, or
`UNKNOWN`; prices are not fabricated.

## Human workflow

1. Explicitly classify and approve an investigation. GIS derives reviewable requirements and
   performs zero collection.
2. Inspect Collection items with origin `INTELLIGENCE_REQUESTED` and their proposal/gap lineage.
3. Promote one supported requirement to a candidate plan. Existing collection planning and all
   cost, rights, provider, and paid-execution controls remain mandatory. Applying and executing
   the plan are separate operations.
4. Once observations are packaged, explicitly reassess the requirement.

Collection merely running never closes a gap. Reassessment requires matching capability
evidence, tenant/site/entity scope, usable rights, compatible method and scope, and a `SUPPORTED`
package. Only `SATISFIED` records the package, resolves a persisted source gap, and marks the
lineage eligible for an explicit future intelligence rerun. It never calls an LLM or creates an
intervention.

Scoped review APIs are:

- `POST /api/v1/experiment-proposals/{id}/review` with `APPROVE_INVESTIGATION`
- `POST /api/v1/experiment-proposals/{id}/collection-requirements`
- `GET /api/v1/collection-requirements/{id}`
- `POST /api/v1/collection-requirements/{id}/promote`
- `POST /api/v1/collection-requirements/{id}/reassess`

The VAHomeMath acceptance scenario produces an owned-page requirement for
`https://www.vahomemath.com/va-entitlement-calculator/` and an exact-query SERP requirement for
`va down payment calculator` in US/en/desktop scope. Neither executes in this workflow.
