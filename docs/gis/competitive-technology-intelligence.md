# Competitive technology intelligence

Epic 18 records observable site and page technologies as historical evidence. It does not create an
SEO score, causal claim, purchasing recommendation, migration recommendation, or autonomous change.

## Architecture and provider strategy

```mermaid
flowchart LR
  T[Domain / SERP / content cohort] --> A[Provider-neutral collector]
  A --> R[Direct HTTP signatures or future provider adapter]
  R --> O[Versioned technology observation]
  O --> D[Canonical technology detection]
  D --> E[Versioned evidence and confidence]
  E --> M[Cohort, change, co-occurrence, and gap marts]
```

The initial adapter is `DIRECT_SIGNATURES`. It reuses Epic 17's bounded, SSRF-safe ordinary HTTP
retriever and performs no active scanning. This yields useful low-cost evidence while keeping the
canonical model independent from BuiltWith, Wappalyzer, DataForSEO, or any provider schema.

BuiltWith was evaluated as a strong future provider. Its official
[Domain API](https://api.builtwith.com/domain-api) exposes v23 JSON/XML/CSV/XLSX technology results,
provider IDs/categories and `FirstDetected`/`LastDetected`; ordinary calls support multiple domains
and the documented high-throughput mode changes payload detail and live lookup behavior. BuiltWith
also documents a separate [Change API](https://api.builtwith.com/) for additions/removals. Both require
an API key. The public [plans page](https://builtwith.com/plans) advertises free individual site
lookups, but that is not treated as a promise of free API usage. API entitlements, credit pricing,
rate limits, export rights, commercial-use terms, and account-specific pricing require human review.
This evaluation was reviewed 2026-08-30. No timeless price or legal conclusion is encoded. A future
BuiltWith/Wappalyzer/BYOD adapter should resolve provider
names through `technology_alias`, retain provider identifiers/category/dates, use `PROVIDER_REPORTED`
semantics, and report dated preflight and actual costs.

## Canonical model and taxonomy

`gis_core.technology` stores a stable slug, name, vendor, product family, and extensible category.
`technology_alias` maps source-specific names without discarding the original provider label.
Confident aliases such as `GA4` and `Google Analytics 4` resolve to `google_analytics`; Google Tag
Manager remains a distinct technology. Unknown products are retained as unreviewed canonical rows
instead of being dropped or falsely merged.

The initial taxonomy covers CMS/framework/application, hosting/cloud/CDN/DNS/proxy, analytics/tag
management/observability, marketing/adtech, CRM/forms/chat/lead tools, experimentation, SEO/search,
commerce/payment, content experience, security, embedded functionality, `OTHER`, and `UNKNOWN`.
Categories are strings so future providers do not require a PostgreSQL enum migration.

`gis_raw.technology_observation` records tenant/organization/site, connection/run/policy, domain and
URL, owned/competitor class, PAGE/SITE/DOMAIN scope, timestamps, status, content hash, render mode,
cost, signature version, and revision window. `technology_detection` records canonical/provider
identity, version, provider first/last seen, scope, confidence, presence, method, and semantic class.
`technology_evidence` preserves every triggering signature and the exact signature-registry version.

## Direct detection and evidence semantics

The centralized registry contains canonical definitions and independently versioned signatures. A
signature declares its match target (`HEADER`, `HTML`, `META_GENERATOR`, `SCRIPT_URL`, or future
`COOKIE`/`DNS`), match method, technology, category, scope, confidence, semantic class, version, and
active state. Signatures are not scattered through collector logic, and later signature changes do
not rewrite historical observations.

Initial signatures cover WordPress, Next.js, React, Google Analytics, Google Tag Manager, Cloudflare,
Vercel, NGINX, HubSpot, Hotjar, Optimizely, and reCAPTCHA. Exact response headers are `MEASURED` facts.
Mapping an asset/meta/script signature to a product is `HEURISTIC`. Commercial adapter detections will
be `PROVIDER_REPORTED`; deterministic comparisons are `GIS_DERIVED`. Ambiguous text such as the word
“react” alone does not trigger a React detection.

Direct inspection observes bounded response headers, HTML/meta generator values, script and asset
references, and cookie names exposed by the ordinary response. It executes no JavaScript and makes no
additional tracking request. Server-side or JS-injected technology may remain unobserved.

## History and changes

Observation identity is site, URL, scope, and date. The content hash covers response bytes, relevant
headers, and signature version. An identical replay inserts no duplicate. Changed evidence closes the
current revision and appends an immutable version.

The change model emits `ADDED` for a technology's first comparable PRESENT observation and
`VERSION_CHANGED` only when a later explicit version differs. It never emits `REMOVED` merely because
a signature was not observed. Failed, truncated, unsupported, hidden, or non-rendered evidence means
`NOT_OBSERVED`, not ABSENT. A future provider may supply explicit absence if its methodology supports
that claim and the semantic distinction remains preserved.

## Cohorts, prevalence, co-occurrence, and gaps

Collection accepts explicit URL/domain targets, the latest controlled-SERP URLs for a tracked query,
or frozen Epic 17 content-cohort URLs. This reuses historical membership rather than creating another
incompatible cohort system. Collection and discovery are capped at 20 targets.

The cohort intermediate model selects the latest technology observation at or before the cohort's
frozen timestamp for each member domain. Marts expose exact domain and denominator counts, technology
and category prevalence, competitor footprints, exact within-observation co-occurrence pairs,
ADDED/VERSION_CHANGED evidence, and owned-versus-competitor differences. Every result is descriptive;
none asserts that a technology caused ranking, experience, or conversion outcomes.

## Rights, provenance, acquisition, and cost

Public observability is not unrestricted permission. `normalized_retention` must be `ALLOWED` before
the collector performs HTTP retrieval. `UNKNOWN` and `DENIED` fail closed. Policy owners must review
raw provider payload/evidence, normalized detections, history, aggregates, customer display, export,
RAG, AI inference, and training separately. Epic 18 changes no existing grant and encodes no legal
conclusion.

Ingestion records connection, source, acquisition method, resolved policy/version, collector/schema
version, target count, and cost. dbt registers raw, staging, intermediate, and mart lineage. A new
`direct_technology` public-web source has conservative UNKNOWN rights. BYOD commercial adapters use
tenant/site connections and secret references; credentials never enter observations or output.

Direct detection has provider cost USD 0. Infrastructure/network cost is not represented as a
provider fee. Future paid adapters must record account-specific dated unit assumptions, maximum
preflight cost, task/request/domain counts, actual provider cost, and currency. Dry-run makes no HTTP
or paid-provider call.

## CLI

```bash
gis-technology-intelligence configure --tenant vahomemath --site vahomemath
gis-technology-intelligence validate --connection <uuid>
gis-technology-intelligence estimate --targets 3
gis-technology-intelligence collect --connection <uuid> --site <uuid> \
  --domain example.com --scope DOMAIN --dry-run
gis-technology-intelligence collect --connection <uuid> --site <uuid> \
  --tracked-query-id <uuid> --top 10 --dry-run
gis-technology-intelligence collect --connection <uuid> --site <uuid> \
  --cohort-id <uuid> --top 10 --dry-run
gis-technology-intelligence inspect --observation-id <uuid>
gis-technology-intelligence technologies --site <uuid> --domain example.com
gis-technology-intelligence changes --site <uuid> --domain example.com
gis-technology-intelligence compare --owned-site-id <uuid> --cohort-id <uuid>
```

## Security and limitations

Epic 17 protections remain authoritative: HTTP(S) only, no URL credentials, DNS resolution and
blocking of localhost/private/reserved/link-local/metadata targets, redirect revalidation, bounded
timeouts/redirects/response size, permitted content types, and an explicit user agent. Epic 18 adds no
port scan, vulnerability scan, authentication attempt, CAPTCHA bypass, bot evasion, exploitation,
or broad network probing. Production should additionally restrict outbound networking to mitigate
DNS-rebinding risk.

- Raw HTTP cannot see all JavaScript-injected or server-side technology.
- Signature detection can yield false positives or negatives; evidence and confidence stay visible.
- Direct observations do not provide provider historical first/last-seen values or prove absence.
- DNS/certificate/Whois collection and commercial provider adapters remain future work.
- Cross-layer search/content/experience joins must retain legitimate dates and cohorts; no opaque
  “technology maturity” score is created.
- Epic 7 and a future AI layer may consume compact normalized evidence later. Epic 18 performs no LLM,
  embedding, RAG, recommendation, purchase decision, migration, or autonomous site operation.
