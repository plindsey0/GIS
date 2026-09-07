# Epic 27D — Governed evidence context enrichment

Epic 27D adds a bounded entity-scoped construction mode to the existing evidence packet. It adds
no schema, collection, semantic search, clustering, provider, or execution capabilities.

```text
authoritative stored observations
  -> deterministic exact entity/query/page selection and governance filters
  -> bounded evidence packet
  -> untrusted structured LLM output
  -> deterministic ID/scope/lineage validation
  -> human decision
```

Explicit evidence-ID mode remains the reproducible path. Entity mode selects only same-tenant,
same-site, same-entity rights-usable sibling packages, keeping the latest per classification. It
requires each raw observation's policy to allow derivative creation before it can enter context. It
caps demand at 24 exact-query observations, external rankings at 5, Search Console at 10, linked-
page GA4 events at 20, owned surfaces at 5, quality dimensions at 50, and stored gaps at 25.

External-provider metrics remain labeled provider observations. GA4 counts retain their literal
low volume. An exact-query GSC or ranking URL on the site's hostname supports only
`OBSERVED_QUERY_PAGE_ASSOCIATION`; it does not establish intent satisfaction, page quality,
content coverage, conversion, or statistical significance. Broader related-query and competitor
records are excluded. Missing target-page content and exact-query SERP evidence remain explicit
gaps.

No migration was required. Existing LLM-run provider metadata records packet construction mode
and entity ID. Packet inspection and Workbench rendering never construct a provider or make an
LLM request.

## Reference validation hotfix

Enriched packets expose a typed `referenceable_evidence` allow-list. Each entry names its stable
UUID, evidence class, packet section, and governing evidence-package lineage. Opportunity output
may cite only IDs in this final constructed list. Explicit packets list only their selected package
IDs; entity-scoped packets additionally list the exact governed observations and deterministic
context records that crossed the boundary.

Persistence resolves cited enriched references back to their governing evidence packages before
writing normalized `opportunity_evidence` links. Fabricated IDs, database IDs outside the packet,
duplicate references, and references whose package lineage leaves the packet tenant/site/entity
scope fail closed. The opportunity prompt explicitly tells models to cite only listed
`reference_id` values.

```bash
gis-intelligence packet --tenant vahomemath --site vahomemath \
  --entity-id 947737ce-fa06-49d5-8aef-b31fb914a828
```
