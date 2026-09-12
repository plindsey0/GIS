# Evidence-backed content briefs

Epic 29B turns an explicitly recommendation-ready SEO investigation into an immutable editorial draft and bounded page-change proposals. It preserves the separation:

```text
Observed fact → governed assessment → recommendation → proposed change
→ human approval → implementation → measurement
```

The initial method is deterministic and provider-free (`governed_content_brief_v1`). It uses the current Epic 29A investigation scope, current satisfied Epic 28E adjudications, usable evidence packages and typed references, the current query/page/intent assessment, and completed human reviews. It makes no provider or network call.

## Eligibility and lineage

`GET /api/v1/seo-investigations/{id}/brief-eligibility` reports every failed gate. Generation fails closed unless the investigation was explicitly marked `READY_FOR_RECOMMENDATION`, every relevant adjudication is current and satisfied, targeting and intent satisfaction are supported separately, human reviews are complete, and scoped derivative-usable references exist.

`POST /api/v1/seo-investigations/{id}/briefs/generate` is the only generation action. Exact input replay returns the same brief. Changed governed evidence creates a linked version and supersedes earlier active proposals. Reads never generate or mutate artifacts.

Each draft suggestion and proposal maps to governed evidence references or is labeled an editorial hypothesis. Claims of guaranteed ranking, traffic, conversion, revenue, rich results, user confusion, or calculator correctness are prohibited. SERP observations remain bounded by collected depth, and owned-page observations never prove product correctness.

## Review safety

Proposal reviews are append-only. Approval does not edit source code, a CMS, content, structured data, analytics, or production infrastructure. Approved proposals may only be marked ready for the later Epic 29C measurement-planning workflow. Material evidence changes invalidate approval eligibility and mark the proposal as needing reassessment.

Workbench routes:

- `/seo-investigations/{id}/briefs`
- `/seo-investigations/{id}/briefs/{brief_id}`

Proposed copy is visibly labeled as a draft. Technical fingerprints, UUID lineage, evidence packages, adjudications, and assessment identity remain collapsed by default.
