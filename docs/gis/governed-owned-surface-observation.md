# Governed owned-surface observation

Epic 28B lets GIS observe one explicitly authorized URL owned by a configured site. It
does not crawl recursively, execute scripts, call an LLM, evaluate search intent, judge
content quality, verify calculator correctness, or create an intervention.

```text
Owned Surface
→ Governed Collection
→ Retrieval/Render
→ Deterministic Extraction
→ Immutable Observation
→ Quality + Provenance
→ Governed Evidence
→ Evidence-Gap Reassessment Eligibility
```

## Knowledge boundary

The raw observation records retrieval facts and the existing normalized content tables
record deterministically extracted facts. `owned_surface_observation_detail` records
explicit assessments such as whether an observed canonical equals the normalized URL.
Neither layer asserts that a page satisfies a query, should be changed, is accessible,
or implements analytics or calculator logic correctly. Those are later semantic or
specialist assessments.

## Authorization and retrieval

Collection accepts exactly one active, human-governed URL `CollectionTarget`, one scoped
analytical entity, the target site's direct-HTTP connection, and the configured site.
Tenant/site/entity scope and the site's normalized hostname must all match. The direct
retriever permits only HTTP(S), resolves every hop to public IP space, rejects URL
credentials and localhost/private/reserved targets, limits redirects to four, limits the
response to 2 MiB, and accepts HTML only. The production adapter is constructed with the
owned hostname allow-list, so an off-site redirect is rejected before the second request.
No cookies, authorization state, or sensitive headers are persisted. Relevant normalized
retrieval headers are allow-listed; `X-Robots-Tag` is retained for assessment.

The initial implementation is static HTTP (`NOT_RENDERED_STATIC_HTTP`). It never runs page
JavaScript. Rendered-browser and customer-provided artifacts can later implement the same
retrieval interface without changing persistence or evidence contracts.

An operator-authorized invocation is:

```bash
GIS_PAID_EXECUTION_DISABLED=1 gis-content-intelligence collect-owned-surface \
  --connection <direct-http-connection-uuid> \
  --site <site-uuid> \
  --collection-target <active-url-target-uuid> \
  --analytical-entity <analytical-entity-uuid>
```

This is intentionally not a scheduler or discovery command. Run it only after approving
the exact target. Tests use local byte fixtures and fake retrievers; they never invoke this
production HTTP adapter.

## Extraction, limits, and history

The shared deterministic HTML parser extracts title, meta description, canonical, robots,
bounded headings and visible text, internal/external links, schema types, forms, controls,
labels, output regions, images/alt presence, semantic landmarks, known analytics script
presence, and declared `data-event` hooks. Owned evidence further bounds visible text to
12,000 characters, controls/images to 100 each, and instrumentation signals to 50. Raw HTML
is governed by the existing retention policy and is not copied into intelligence packets.

Every changed response creates a new immutable content observation. Hashes independently
cover raw response bytes, normalized visible content, important structure, and metadata.
The owned detail points to its predecessor and classifies deterministic change as first,
unchanged, raw-only, metadata, content, structure, or a combination. The classification
does not say whether a change is beneficial. An unchanged recollection remains an audited
ingestion run but does not duplicate normalized facts.

## Quality, rights, provenance, and evidence

Each qualifying observation produces an `OWNED_SURFACE_CONTENT` evidence package and
quality run using the existing provenance and rights systems. Identity, freshness,
completeness, method/scope compatibility, rights usability, and temporal continuity are
recorded separately. A 2xx observation with visible content may be `USABLE_LIMITED`;
truncated, empty, 4xx/5xx, missing-render, missing-canonical, and other limitations remain
explicit. Rights that do not permit derivative evidence make the package blocked/unknown
and prevent reassessment readiness.

The Epic 27D packet builder includes only scoped, selected, rights-usable packages. It adds
a typed `OWNED_SURFACE_OBSERVATION` reference backed by the governing package plus a compact
summary of URL, time/status, canonical/indexability, title/meta/headings, bounded content,
controls, schema, instrumentation, fingerprints/change state, quality, provenance, and
limitations. Existing tenant/site/entity, package-lineage, provenance, and reference
allow-lists remain authoritative.

A matching open `TARGET_PAGE_CONTENT_OBSERVATION` gap is not closed by collection. A usable
observation annotates the linked gap with the candidate package/observation and marks it
reassessment-ready. Deterministic `SATISFIED`, `PARTIALLY_SATISFIED`, or insufficient gap
resolution belongs to Epic 28E.

## Workbench

Collection-target detail displays newest owned observations without per-record database
queries: identity/time/change, HTTP/final/canonical/indexability signals, title/meta,
headings/content preview/schema/internal links, controls and instrumentation, quality,
limitations, rights/provenance lineage, and associated gaps. UUIDs, fingerprints, and full
technical provenance are grouped as technical detail. Controls and analytics hooks are
clearly observations, not proof of behavior.

## Deferred work

Rendered browser capture and deeper accessibility/instrumentation assessment belong to
future Epic 28C/28D work. Generalized evidence-gap adjudication belongs to Epic 28E. Bounded
multi-page crawling, semantic intent resolution, autonomous collection, and autonomous
downstream action are explicit non-goals.
