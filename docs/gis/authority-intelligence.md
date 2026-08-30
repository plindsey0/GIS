# Authority Intelligence

Authority Intelligence is a provider-neutral evidence layer for historical backlinks, referring domains, page-level link attraction, and provider-specific authority metrics. It records observed conditions; it does not recommend outreach, link building, content, or public-relations actions.

## Essential semantic limits

1. **Authority is not a directly observed universal quantity.** It is an analytical construct.
2. Provider authority metrics are not interchangeable. A provider's Domain Rating, Authority Score, Domain Authority, Trust Flow, or similar metric remains keyed to that provider and methodology.
3. Absence from a backlink provider does not prove that a link does not exist.
4. Non-detection does not equal link loss. Loss requires an explicit provider `OBSERVED_LOST` state or a future documented comparable-complete-snapshot method.
5. Authority differences are descriptive facts, not recommendations.
6. Correlation between links, content, and rankings does not establish causality.

No universal GIS authority score exists.

## Provider-neutral architecture

`AuthorityProvider` accepts a bounded `AuthorityRequest` and returns a canonical `AuthorityCollection`. The interface supports future DataForSEO Backlinks, Ahrefs, Semrush, Majestic, Moz, and customer-import adapters without changing storage. Epic 20 implements a JSON import/fixture adapter and a documented normalization contract; it deliberately performs no live provider request.

Connections reuse `DataSourceConnection`, secret references, ingestion runs, source acquisition methods, cost accounting, rights policies, budgets, and orchestration. Credentials remain outside normal database fields.

## Ontology and storage

Targets are `DOMAIN` or `PAGE`. Ownership is `OWNED`, `COMPETITOR`, `OTHER`, or `UNKNOWN`, resolved from canonical GIS site/domain records.

`gis_raw.authority_observation` is the revision-aware provider envelope. Its deterministic identity uses site, provider, target type, normalized target, effective observation date, and scope. Content hashes make exact replay idempotent; provider revisions close the prior effective interval rather than overwriting it.

`gis_raw.authority_metric_observation` preserves metric provider, key/name, value, known scale, unit, methodology version, and semantic class. Provider metrics are never converted into a common score. Canonical factual counts may be `MEASURED` or `GIS_DERIVED`; proprietary provider metrics are `PROVIDER_REPORTED`.

`gis_raw.backlink_observation` records normalized source/target URLs and domains, stable provider-or-structural identity, link state, relation attributes, follow state, sponsored/UGC status, link type, first/last seen times, anchor evidence, semantics, and provenance.

`gis_raw.referring_domain_observation` deterministically groups links by referring domain inside a provider observation. It retains backlink/follow/nofollow counts and first/last appearance.

Link states are:

- `OBSERVED_ACTIVE`: explicitly present.
- `OBSERVED_NEW`: provider explicitly reports new.
- `OBSERVED_LOST`: provider explicitly reports lost.
- `UNKNOWN`: insufficient state semantics.

Snapshots are provider-dependent and may be partial. Different providers' counts must remain qualified by provider and scope.

## Anchor evidence

The versioned deterministic classifier emits `BRAND`, `EXACT_MATCH`, `PARTIAL_MATCH`, `URL`, `GENERIC`, `IMAGE_OR_EMPTY`, `OTHER`, or `UNKNOWN` with confidence. Classification is heuristic evidence. Normalized anchor hashes can support pattern analysis. Raw anchor text is retained only when `RAW_RETENTION` is explicitly allowed and collection opts in; otherwise the raw text is discarded.

## Derived measures

GIS-derived calculations include explicit-new/lost and net velocity, referring-domain overlap/gaps, page link counts, and HHI concentration. HHI is `sum((links from domain / all links)^2)`; diversification is `1 - HHI`. These transparent measures are not equivalent to proprietary provider authority metrics.

Frozen competitive-content cohorts remain the reproducible cohort source. Authority rows keep historical target ownership and dates; a later live competitor-set change does not rewrite earlier evidence.

## Rights, provenance, and cost

Before calling a provider, collection requires explicit `ALLOWED` decisions for `NORMALIZED_RETENTION` and `COMMERCIAL_USE`. Optional raw anchor retention also requires `RAW_RETENTION`. `UNKNOWN` and `DENIED` fail closed before any provider call. No source policy is automatically broadened.

Every observation links tenant, organization, site, source connection, ingestion run, rights policy/version, provider task, collection version, timestamps, bounds, costs, and metadata. Downstream derivative events conservatively aggregate rights through Epic 19.

Dry-run estimation never contacts a provider. Collection records pre-request estimates, provider-reported cost, currency, requests, received/inserted/revised/rejected counts. Orchestrated paid collection remains subject to Epic 18.5 budgets.

## Bounds and CLI

Collection requires one explicit target, a row limit (default 1,000; maximum 10,000), and a pagination limit (default 10; maximum 100). One CLI estimate supports at most 25 targets. There is no broad crawler or uncontrolled pagination.

```bash
gis-authority-intelligence configure --connection UUID --provider dataforseo
gis-authority-intelligence validate --fixture authority-export.json
gis-authority-intelligence estimate --targets 2 --rows 1000 --pages 10 --unit-cost 0
gis-authority-intelligence collect --tenant vahomemath --site vahomemath \
  --connection UUID --target-type DOMAIN --target vahomemath.com \
  --rows 1000 --pages 10 --fixture authority-export.json --dry-run
gis-authority-intelligence inspect OBSERVATION_UUID
gis-authority-intelligence backlinks --tenant vahomemath --site vahomemath
gis-authority-intelligence referring-domains --tenant vahomemath --site vahomemath
gis-authority-intelligence domains --tenant vahomemath --site vahomemath
gis-authority-intelligence pages --tenant vahomemath --site vahomemath
gis-authority-intelligence competitors --tenant vahomemath --site vahomemath
gis-authority-intelligence compare --tenant vahomemath --site vahomemath
gis-authority-intelligence changes --tenant vahomemath --site vahomemath
```

All output is JSON and serializes UUID, datetime/date, Decimal, and enum values without revealing credentials.

## Analytics

dbt provides:

- `mart_authority_domain_daily`
- `mart_authority_page_daily`
- `mart_referring_domain_daily`
- `mart_authority_competitor_daily`
- `mart_authority_gap`
- `mart_authority_velocity`
- `mart_authority_concentration`
- `mart_page_link_attraction`

The gap mart labels observed referring domains `SHARED`, `OWNED_ONLY`, or `COMPETITOR_ONLY`; it does not label any domain an outreach target. Page link attraction is descriptive and makes no causal claim about content.

## Competitive events and orchestration

Epic 19 gains an `AUTHORITY` domain with backlink/referring-domain first-observed, gained, and explicitly lost events plus material provider-metric changes. The materiality policy is version `1.1.0`; authority metrics require an absolute change of 1 or relative change of 10 percent. Missing links never synthesize loss.

Epic 18.5 seeds `authority_intelligence` as a paid-provider-capable, **disabled** weekly template and adds it as an optional upstream dependency of `competitive_events`. No schedule is activated by Epic 20.

## Limitations and operational validation

The shipped provider path accepts fixture/customer JSON and therefore validates normalization without provider cost. A reviewed live adapter should first be exercised against a non-production tenant with an explicitly reviewed policy, secret-manager credential reference, one domain, one page, a small row/page limit, a displayed budget reservation, and dry-run output. After a single operator-approved call, inspect ingestion cost, revision history, provenance, raw-anchor behavior, marts, and generated events before considering a disabled schedule for manual enablement.
