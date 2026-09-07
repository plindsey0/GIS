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
and entity ID; evidence-package IDs remain the only model-referenceable evidence IDs. Packet
inspection and Workbench rendering never construct a provider or make an LLM request.

```bash
gis-intelligence packet --tenant vahomemath --site vahomemath \
  --entity-id 947737ce-fa06-49d5-8aef-b31fb914a828
```
