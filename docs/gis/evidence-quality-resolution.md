# Evidence Quality, Identity, and Resolution

Epic 26.5 is GIS's deterministic trust layer. It resolves what stored evidence refers to and packages the support, limitations, provenance, rights, coverage, compatibility, independence, corroboration, and conflicts for a factual analytical claim. It does not decide whether a condition is valuable or recommend an action.

> **Multiple derived observations from the same root source do not constitute independent corroboration.**

> **Evidence quality describes the support for an analytical claim; it does not determine the business value of that claim.**

## Analytical identity

`analytical_entity` provides tenant/site-scoped identities for sites, domains, URLs, queries, topics, versioned markets, and versioned market segments. It intentionally excludes people, sessions, IP addresses, browser fingerprints, and cross-site individual identity.

Every entity records a canonical key, normalization method and version, analytical scope, optional source reference, and explanatory metadata. Identity is distinct from normalization: two normalized resources are not declared equivalent without a supported assertion.

### Domains

`DOMAIN_NORMALIZATION_V1` applies lowercase, trailing-dot removal, `www` alias normalization, and IDNA ASCII encoding. `REGISTRABLE_DOMAIN_V1` uses the bundled Public Suffix List snapshot supplied by `tldextract` with network fetching disabled.

Exact normalized hostnames may be `SAME_ENTITY`. Hosts sharing a registrable domain receive `SAME_REGISTRABLE_DOMAIN`, not automatic equivalence. Thus `blog.example.com` remains analytically distinct from `example.com`. Canonical site relationships may be asserted from existing site/domain evidence.

### URLs

`URL_NORMALIZATION_V1` normalizes scheme/host casing, default ports, fragments, trailing slashes, parameter order, and known tracking parameters. Arbitrary query parameters remain intact. A normalized URL is not the same as a resolved resource. `REDIRECTS_TO` and `CANONICAL_OF` require explicit redirect or canonical-link evidence. Conflicting redirect and canonical evidence remains `CONFLICTING`; V1 does not invent precedence.

### Queries, topics, segments, and markets

Query identity applies Unicode NFKC normalization, case folding, and whitespace normalization while retaining geography, language, and device scope. Semantically similar strings remain different queries. Topic and segment identities incorporate the Epic 11 market, method, and version. Market versions remain distinct populations even when connected by supersession lineage.

## Identity assertions

`identity_assertion` is append-oriented. It records subject, object, relationship, computed and effective strength, deterministic method/version, evidence, validity interval, and optional auditable override fields. Supported relationships include same entity, alias, canonical, redirect, subdomain, same registrable domain, membership, and related-but-not-identical.

Strengths are categorical: `EXACT`, `STRONG`, `SUPPORTED`, `WEAK`, `UNRESOLVED`, and `CONFLICTING`. Changed evidence supersedes the current assertion without deleting history. Same evidence and method is a no-op.

## Multidimensional quality

Every package retains independently inspectable dimensions:

- identity resolution;
- freshness;
- completeness;
- temporal continuity;
- provenance completeness;
- source independence;
- cross-source corroboration;
- consistency;
- method compatibility;
- scope compatibility;
- rights usability.

Dimension states distinguish `UNKNOWN` from `NOT_APPLICABLE`, as well as `BLOCKED`, `LIMITED`, `SUPPORTED`, and `STRONG`. There is no universal scalar quality score.

Freshness translates the intended claim contract's recency requirement; it does not declare historical evidence false. Completeness is relative to a named expected set, never the whole web. Temporal continuity respects actual cadence, gaps, provider/method changes, collection activation, and market-version changes. Epic 18.5 remains the source for operational schedule freshness, while packages describe analytical usability.

## Source independence and corroboration

`EVIDENCE_QUALITY_V1` traces root source keys on evidence items. Repeated observations and derived signals from the same provider are `SAME_ROOT_SOURCE`, not multiple confirmations. Independence states are `SAME_ROOT_SOURCE`, `DEPENDENT_DERIVATION`, `PARTIALLY_INDEPENDENT`, `INDEPENDENT`, and `UNKNOWN`.

Corroboration never averages unlike metrics. It describes whether compatible support exists from genuinely distinct roots: `UNSUPPORTED`, `SINGLE_SOURCE`, `CORROBORATED`, `MULTI_SOURCE_CORROBORATED`, `CONFLICTING`, or `INSUFFICIENT`.

## Compatibility and conflicts

Compatibility is evaluated before contradiction. Comparable claims require the same resolved target, metric semantics, unit, market version, and compatible geography, language, device, period, and resolution. Results are `COMPATIBLE`, `PARTIALLY_COMPATIBLE`, `INCOMPATIBLE`, or `UNKNOWN`.

Opposing directions among compatible provider-volume claims may be a conflict. GSC impressions increasing while provider search volume declines is not automatically a conflict because the metrics describe different phenomena. Proprietary authority metrics such as Domain Rating, Domain Authority, and Authority Score remain provider-specific and are never collapsed into one measure.

## Rights usability

The existing provenance rights evaluator remains authoritative. Packages express `USABLE`, `BLOCKED`, `PARTIALLY_USABLE`, or `UNKNOWN` for the requested derivative use. Unknown fails closed. Reviewed rights policies are never changed by assessment.

## Evidence contracts and packages

`evidence_contract` is a named, versioned evidence requirement. Initial contracts cover demand emergence, acceleration, decline, market visibility change, competitor page change, and authority change. Requirements state minimum primary evidence/history, identity, compatibility, freshness, coverage, independence, and blocking conflicts.

`evidence_package` has the grain:

`tenant × site × analytical entity × condition × period × market version × contract version × assessment evidence state`

It links the resolved entity and factual condition to package items, quality dimensions, root sources, categorical sufficiency, corroboration, compatible conflicts, rights, and limitations. `INSUFFICIENT`, `LIMITED`, `SUPPORTED`, and `STRONGLY_SUPPORTED` are contract-specific support states—not truth probabilities.

Epic 7 can request the package for condition X, entity Y, and market Z rather than reconstructing raw provenance. Epic 8 can later consume the same package with explicit limitations, preventing unknown evidence from becoming false and single-source evidence from becoming established fact.

## Emerging Demand and Collection Planning

Epic 26 classifications remain factual outputs. Evidence Quality adds qualification, for example `classification=ACCELERATING` with `sufficiency=LIMITED`; it does not erase or silently change the classification.

When a contract is unmet, `evidence_gap` records the missing evidence and writes an `information_gap` signal into the existing Collection Planning evidence model. This never calls a provider, estimates truth, spends budget, changes cadence, or activates a schedule. Epic 10.5 retains all collection decisions.

## Orchestration and CLI

The weekly `evidence_quality` pipeline template is disabled. It has non-blocking `ALWAYS` dependencies on Market Intelligence, Collection Planning, Emerging Demand, Competitive Events, and Authority Intelligence so sparse optional sources do not prevent assessment.

```bash
gis-evidence-quality resolve --tenant-id UUID --site-id UUID --type DOMAIN --value blog.example.com --other-value example.com
gis-evidence-quality assess --tenant-id UUID --site-id UUID --dry-run
gis-evidence-quality explain PACKAGE_UUID
gis-evidence-quality conflicts --tenant-id UUID --site-id UUID
gis-evidence-quality corroboration --tenant-id UUID --site-id UUID
gis-evidence-quality gaps --tenant-id UUID --site-id UUID
gis-evidence-quality contracts --tenant-id UUID --site-id UUID
```

Output is JSON-first and supports UUIDs, timestamps, dates, decimals, and enums. Assessment makes zero provider calls.

## Analytics, dashboard, and provenance

Eight staging models and nine marts expose current/history packages, sufficiency, conflicts, corroboration, gaps, entity resolution, root-source independence, and contract status without fanout. The executive dashboard receives a compact trust summary; the detailed GIS Evidence Quality dashboard exposes dimensions without a universal score.

Registered lineage follows real stored assets from provider/demand evidence and collection/market identities through normalized entities and assertions into packages and planning gaps. It does not manufacture lineage between unrelated sources.

## Sparse-data behavior and limitations

With no compatible current evidence, assessment produces no positive packages. Where a package exists but history, independence, provenance, freshness, or rights are unknown, it remains `UNKNOWN`, `LIMITED`, or `INSUFFICIENT`. No corroboration or conflict is fabricated for dashboard population.

V1 packages Epic 26 demand signals first. The schema and initial contracts support later adapters for market, competitive-content/event, and authority claims, but those provider-specific adapters should be added only when their comparable claim grains are explicit. No probabilistic matching, embeddings, LLM resolution, personal identity, provider purchasing, opportunity logic, or recommendations are included.
