# BuiltWith rights evidence — operator review required

Research date: 2026-09-04. Recommendations only, not approved policy or legal advice.

## First-party provisions and GIS interpretation

[Terms, updated March 6, 2026](https://builtwith.com/terms), §§3, 6–8, 10:
private internal API-data storage and internal analytics are supported, subject to
licensed access. Resale, public distribution, database reconstruction, competing
services and transfer to third-party analytics providers are restricted. Internal AI
is conditional, not unrestricted permission. **GIS's eventual multi-customer technology
intelligence role needs clarification; do not equate that with one organization's
private internal use.** PAYG entitlement should be verified against the account agreement.

| Intended use | Recommended state pending human review | Confidence / qualification |
| --- | --- | --- |
| Private raw retention | ALLOWED candidate | High textual support; confirm licensed internal scope |
| Normalized historical retention | ALLOWED candidate | Medium inference from private storage; not database reconstruction |
| Deterministic internal analysis | ALLOWED candidate | High, internal scope only |
| Aggregation / private derived display | UNKNOWN | Medium; scope and competing-product restrictions need review |
| Broad commercial use, external display, redistribution | UNKNOWN / PROHIBITED for prohibited distribution | Do not grant broad reuse |
| Third-party processing, cross-tenant learning | UNKNOWN | Restricted transfers and competitive-use risk |
| AI inference / training | UNKNOWN | Conditional internal permission insufficient for a broad GIS grant |
| Attribution / fixed retention duration | UNKNOWN | No general duration or blanket attribution determination |

[Privacy policy](https://builtwith.com/privacy), updated March 24, 2026: describes
BuiltWith's own personal-data processing and minimization. It does not independently
license downstream GIS uses. Confidence: high. Keep downstream permissions UNKNOWN
unless supported by the governing agreement. The collector requests privacy-reducing
flags; these are not rights grants.

[Domain API documentation](https://api.builtwith.com/domain-api) describes technical
access and refers users to standard terms. API functionality is not an independent
grant. Confidence: high.

## Required rights and approval

Source inspection confirms that TECHNOLOGY_PROFILE checks only `raw_retention` and
`normalized_retention` before dispatch. Both must evaluate ALLOWED. Other unknown uses
do not block this collector; they remain restricted for future downstream processing.

System → Sources → BuiltWith → Review rights exposes compatibility fields and every
effective permitted-use grant. Grants take precedence; set the two retention grants
explicitly rather than merely changing legacy fields. DENIED in grant storage is the
equivalent of PROHIBITED in compatibility fields and UI.

Record a unique policy version, reviewer, documented basis, license/reference,
jurisdiction and retention decisions. Approval creates a new tenant policy and grants,
linked through `supersedes_policy_id`; only the selected connection pointer changes.
Historical observations, ingestion, schedules and policies are not rewritten. Shared
source defaults and other connections are untouched. Reviews are effective immediately;
future-dated activation is not supported. This does not activate or queue collection.

The Workbench separates the effective policy from proposed edits, highlights the two
collection-critical grants, summarizes every changed grant and shows which rights blockers
would resolve. Its final confirmation is an in-application governance step. After commit,
the Workbench reads the policy and source state back from the API; it does not treat an
optimistic browser update as proof of persistence. History preserves effective, superseded,
and initial unreviewed versions as the canonical audit trail.

Approvals are guarded by the effective policy ID captured when the form opens. If another
review wins first, the stale form is rejected and its entries remain available for comparison.
Validation and database failures are explicit and never activate a partial policy. Correct a
highlighted field, or for a stale review close and reopen the form before submitting again.
Reusing any earlier version label is rejected.

Only raw and normalized retention determine BuiltWith rights readiness. Clearing those
blockers does not establish credential acceptance or Domain API entitlement, activate a
capability, authorize a target, change limits, release the process hold, or execute a request.
Account telemetry is never refreshed by opening or approving this form. Policy changes
themselves consume zero BuiltWith credits.

Do not approve disputed uses simply to clear a blocker. Obtain BuiltWith clarification
for GIS's intended deployment boundary where necessary.
