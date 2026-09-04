# Epic 16B.4.4 — BuiltWith temporal intelligence

## Root cause and retained evidence

The successful `vahomemath.com` Domain API v23 response already retained useful
technology-level dates. Each path contains a `Technologies` array whose entries carry
integer `FirstDetected` and `LastDetected` values in Unix epoch milliseconds. The result
and path objects also carry integer `FirstIndexed` and `LastIndexed` values, but those
describe BuiltWith's indexing of the result/path rather than the lifetime of an individual
technology. They remain raw evidence and are not promoted into a technology detection.

The original `provider_date` implementation accepted only offset-bearing ISO strings.
It consequently returned `None` for the v23 millisecond integers and populated normalized
detection dates with null values. The response did not contain a verified current/live
presence flag. The evidence also includes a provider last-detected value later than the
GIS collection timestamp. GIS preserves and labels that anomaly; it does not reinterpret
it as current presence.

## Temporal semantics

- **Provider first observed** is the earliest valid technology `FirstDetected` value
  among every retained evidence item resolved to the canonical technology.
- **Provider last observed** is the latest valid technology `LastDetected` value among
  those evidence items.
- **Collection observed at** is `TechnologyObservation.collected_at`.
- **Current presence** remains `UNKNOWN`. Historical evidence is not a live assertion.

The parser accepts v23 Unix epoch milliseconds and offset-bearing ISO timestamps,
normalizes both to UTC, rejects Boolean values, second-resolution numbers, malformed
values, and naive timestamps, and never substitutes path index dates. Original values
remain unchanged in `TechnologyEvidence.evidence_value` and the observation payload.

Repeated paths or provider signatures that resolve to one canonical technology retain
separate evidence records. Their summary uses earliest-first/latest-last. This preserves
the successful 25-provider-record to 24-canonical-detection accounting, including both
Google Analytics signatures.

## Implementation and backfill

Prospective collection now uses the corrected parser with the existing
`TechnologyDetection.provider_first_seen_at` and `provider_last_seen_at` columns. No
schema migration is required. A tenant/site-scoped command derives the same summary from
immutable retained evidence:

```bash
# Preview only: no provider request and no writes
GIS_PAID_EXECUTION_DISABLED=1 .venv/bin/gis-builtwith backfill-temporal \
  --tenant vahomemath --site vahomemath

# Explicitly update only derived detection summaries
GIS_PAID_EXECUTION_DISABLED=1 .venv/bin/gis-builtwith backfill-temporal \
  --tenant vahomemath --site vahomemath --apply
```

Both modes report detections examined/changed, evidence items with usable dates,
application state, and zero provider calls. The transformation reads only retained
`TechnologyEvidence`; it does not rewrite observations, payloads, evidence, runs, usage,
configuration, rights, schedules, targets, obligations, account telemetry, or DataForSEO.

## Domain intelligence and drill-down

The domain page now places a deterministic Technology Intelligence Summary above the
evidence facets and provider-category cards. Existing categories map generically to
application/framework, cloud/hosting, CDN, DNS, analytics/measurement,
tag management, advertising/conversion, SSL/security, registrar, mobile, and other
dimensions. This is
evidence coverage, not verified current deployment.

Detection cards show provider first/last observed, explicitly show current presence as
Unknown, and flag dates later than collection. Drill-down separates provider evidence
from canonical interpretation and includes evidence identifiers, domain, source,
observation and run IDs, rights, acquisition method, payload hash, schema version, and
collection timestamp. Raw path/detection evidence remains rights-governed.

## Semantic classification decision

No new ontology was introduced. BuiltWith categories include technologies,
infrastructure, capabilities, and inferred properties; forcing them into a small semantic
type set without a reviewed mapping would create false precision. Provider categories
remain authoritative evidence, while summary dimensions are explicitly a presentation
interpretation.

## Tests and historical safety

Coverage verifies v23 nested milliseconds, strict parsing, missing/malformed values,
path-date exclusion, earliest/latest aggregation, multiple signatures under one canonical
technology, unknown current state, generic grouping, drill-down provenance,
rights-governed raw display, preview-first backfill, and unchanged evidence counts.
Workbench tests cover the summary, temporal values, anomaly disclosure, empty state, and
semantic detail.

Protected-table fingerprints are recorded before real-database backfill. Only the two
derived timestamp fields on explicitly reported `gis_raw.technology_detection` rows may
differ afterward; its row count and every source/provenance/control table must remain
unchanged.

## Remaining limitations and follow-on

BuiltWith history cannot establish current deployment, explain a provider future-date
anomaly, or supply dates omitted by the response. A future reviewed technology-ontology
epic can add evidence-backed semantic types without losing provider categories. A later
multi-observation temporal-resolution epic can model intervals and corroborate current
state from repeated observations or an explicitly verified provider signal.
