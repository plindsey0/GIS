# Exact-query SERP intelligence

Epic 28C records what a search environment returned for one exact governed query and
market scope at one point in time.

```text
Exact Query + Market
→ Governed Collection
→ Provider Observation
→ Normalization
→ Immutable SERP Snapshot
→ Quality + Provenance
→ Deterministic SERP Summary
→ Governed Evidence
→ Evidence-Gap Reassessment Eligibility
```

An observed SERP participant is not necessarily a business competitor. An observed
query-page result is not evidence that the page satisfies intent. Likewise,
`NOT_OBSERVED_WITHIN_COLLECTED_DEPTH` never means that a site does not rank.

## Identity and authorization

The existing `TrackedQuery` is the exact identity: raw and normalized query, search engine,
country, location code/name, language, device, and requested depth. Collection additionally
requires an active query `CollectionTarget`, matching analytical entity, matching market,
tenant/site-scoped DataForSEO connection, and storage-authorized rights policy. Related or
lexically similar queries cannot substitute for the target.

The existing DataForSEO adapter remains the production provider. The governed command is:

```bash
GIS_PAID_EXECUTION_DISABLED=0 gis-serp sync-exact \
  --connection <approved-dataforseo-connection-uuid> \
  --query-id <tracked-query-uuid> \
  --collection-target <active-query-target-uuid> \
  --analytical-entity <exact-query-entity-uuid>
```

This future live command remains subject to the existing provider-control policy, budget
reservation, selected connection, credentials, and paid-execution kill switch. An approved
requirement never invokes it automatically. Epic 28C implementation and tests keep
`GIS_PAID_EXECUTION_DISABLED=1` and use provider-free fixtures only.

## Normalization and immutable history

`SerpCollector` remains the ingestion boundary. It preserves provider task identity,
observation time, exact scope, rights policy/version and normalized results. Each valid
result retains absolute/group position, provider-native and normalized type, URL/hostname,
title, snippet, breadcrumb, ownership classification, and bounded provider metadata.
Unknown feature types remain `OTHER`; absent values remain null. Malformed URLs/results and
duplicate position/type/URL records are counted and excluded, never fabricated.

The additive `exact_query_serp_snapshot_detail` binds the raw observation to its authorized
target, analytical entity and market. A duplicate provider task is an audited idempotent
replay. An identical later provider observation is an immutable `UNCHANGED_RECOLLECTION`;
a changed later snapshot is preserved as `CHANGED`. Comparison reports bounded URL and
domain entries/exits, position movement, feature appearance/disappearance, and owned-site
movement with both timestamps/depths. It asserts no cause or permanence.

## Deterministic summaries

Summaries expose result count, returned depth, unique domains in top 10/20, repeated-domain
result share, result/feature composition, ten observed participant summaries, and the top
20 results plus every owned result outside that cutoff. Literal flags such as `calculator`
in a title/path and `.gov` hostname are lexical observations only. Formal stability remains
`INSUFFICIENT_HISTORY` until comparison history exists; statistical confidence is not
invented.

## Quality, rights, and evidence

Every governed snapshot creates an `EXACT_QUERY_SERP` evidence contract/package and quality
run. Identity, freshness, completeness, provenance, method/scope compatibility, rights and
temporal continuity remain separate dimensions. Requested-versus-returned depth, zero
valid results, feature absence and source limitations remain explicit. Repeated DataForSEO
snapshots are one root source and never count as independent corroboration.

Derivative-use rights gate packet exposure and gap readiness. Epic 27D receives no raw
provider payload: it receives at most three snapshot summaries, 20 top results plus owned
results, ten participant summaries, feature counts, comparison, quality and limitations.
`EXACT_QUERY_SERP_SNAPSHOT` and bounded `SERP_RESULT` IDs enter the final typed reference
allow-list with their governing package ID.

A matching open `EXACT_QUERY_SERP_COMPETITOR_EVIDENCE` gap receives candidate snapshot and
package lineage and becomes reassessment-ready only when valid results and usable rights
exist. Collection never resolves the gap; Epic 28E owns satisfied/partial/insufficient
adjudication.

## Workbench and non-goals

Collection-target detail displays query/market scope, provider/time/depth, owned visibility,
overview/domain composition, readable results, historical comparison, quality, limitations,
and associated gaps. UUIDs, hashes, provider task identity, rights and package lineage remain
inside collapsed technical details. Queries are batched per snapshot list to avoid per-row
result lookups.

Epic 28C does not cluster queries, classify intent, score content/competition, create a
recommendation or intervention, run an LLM, or autonomously collect. Epic 28D owns governed
query/page/intent resolution; Epic 28E owns evidence-gap resolution. Rendered owned-page
observation and broader automated competitive analysis remain separate capabilities.
