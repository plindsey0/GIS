# Epic 28D — Query ↔ Page ↔ Intent Resolution

Epic 28D answers: given the governed evidence currently available, what relationship is supported
between one exact query, one candidate page, and the user need represented by that query?

**Association ≠ Targeting ≠ Intent Satisfaction.**

- Association means the exact query and page were observed together in GSC, an external ranking,
  or an exact SERP. It is deterministic and does not establish page quality.
- Targeting is the governed semantic assessment that bounded observed page content intentionally
  addresses the query or topic.
- Intent satisfaction is the stronger assessment that the observed page appears capable of meeting
  the interpreted user need. It may be partial, unresolved, conflicting, or insufficient.

## Architecture

```text
Authoritative Query/Page/SERP Evidence
  → Deterministic Association Resolution
  → Governed Semantic Interpretation
  → Deterministic Validation
  → Versioned Query/Page/Intent Assertion
  → Human Review
  → Downstream Intelligence Context
```

The resolver accepts one exact governed QUERY entity and one URL entity in a tenant/site scope.
Referenceable evidence must resolve to usable evidence packages for that query and compatible market.
GSC, external-ranking, and SERP observations establish association independently; repeated records
from the same root source do not become independent corroboration.

Only bounded extracted page claims and bounded exact-SERP claims enter semantic context. Raw HTML,
provider payloads, hidden ranking factors, conversion claims, and arbitrary prose are excluded.
Provider-declared intent remains a provider observation and is never promoted to authoritative GIS
intent. Missing or stale page/SERP evidence supports `INSUFFICIENT_EVIDENCE`, not invention.

## Structured interpretation and validation

`query_page_intent_resolution_v1` uses the existing provider-neutral `LLMProvider`. Replay fixtures
are the offline/default test path. No Workbench read triggers interpretation. The structured output
preserves the query, candidate URL, user need, targeting and satisfaction states, supporting and
conflicting IDs, exact page/SERP claims, concise rationale, assumptions, limitations, qualitative
confidence metadata, gaps, and next resolution action.

GIS rejects changed query/URL identity, unknown references, wrong scope/market/rights, invented page
or SERP claims, association-to-satisfaction leaps, and contradictory states. Model confidence is not
a calibrated probability and no hidden chain-of-thought is stored.

## History, gaps, and human review

Assessments are immutable versions linked to normalized evidence-package lineage. New content or
SERP fingerprints mark the current result reassessment-needed; reruns are explicit and create a new
version while retaining the old one. Reviews (`CONFIRM`, `DISAGREE`, `NEEDS_MORE_EVIDENCE`) are
append-only and do not overwrite the deterministic/model result. Structured gaps remain unresolved
inputs to the existing investigation and collection workflow; collection never starts automatically.

Epic 27D packets include only a bounded relationship summary and a typed
`QUERY_PAGE_INTENT_ASSERTION` reference backed by the governing packages. They do not automatically
create opportunities, recommendations, experiments, or interventions.

The Workbench read model separates exact query, candidate page, association, targeting, satisfaction,
supporting evidence, conflicts, gaps, reassessment state, review history, and audit metadata. Full IDs
and technical lineage remain secondary details.

## Optional evidence

This baseline can consume existing content extraction and SERP observations. When the separately
developed Epic 28B owned-surface and Epic 28C exact-query snapshot models are merged, their bounded
claims and fingerprints can enter the same context/reference contract without changing the assertion
model. Absence of either correctly limits the conclusion.

## Non-goals

This epic does not add query clustering, embeddings, vector search, RAG, causal SEO analysis, ranking
factor inference, page scoring, broad competitor scoring, autonomous content recommendations,
collection, experiments, or interventions. Generalized evidence-gap resolution remains Epic 28E.
