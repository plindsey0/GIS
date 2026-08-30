# SERP and experience intelligence

Epic 15 adds provider-neutral, historical search-result and web-experience observations. DataForSEO is the first SERP adapter; PageSpeed Insights supplies CrUX field data and Lighthouse lab data. Provider payloads are normalized before persistence, so another approved provider can implement the same service boundary without changing analytical tables.

## Canonical model

```mermaid
erDiagram
  TENANT ||--o{ SITE : owns
  SITE ||--o{ TRACKED_QUERY : tracks
  DATA_SOURCE ||--o{ DATA_SOURCE_CONNECTION : provides
  DATA_SOURCE_CONNECTION ||--o{ INGESTION_RUN : executes
  TRACKED_QUERY ||--o{ SERP_OBSERVATION : observed_as
  INGESTION_RUN ||--o{ SERP_OBSERVATION : records
  SERP_OBSERVATION ||--o{ SERP_RESULT : contains
  INGESTION_RUN ||--o{ EXPERIENCE_OBSERVATION : records
  DATA_RIGHTS_POLICY ||--o{ SERP_OBSERVATION : governs
  DATA_RIGHTS_POLICY ||--o{ EXPERIENCE_OBSERVATION : governs
```

Tracked-query uniqueness uses tenant, site, normalized query, engine, country, location, language, and device. Normalization trims, case-folds, and collapses whitespace; analytical GSC matching applies the same exact normalization and deliberately does not fuzzy match.

SERP observations are append-oriented. Recollection of the same tracked query, UTC observation date, device, and location closes the previous effective record and inserts a new current revision. Result URLs must be absolute HTTP(S); query strings and fragments are removed for deterministic comparison. Domains already attached to the site are `OWN_SITE`; domains marked `COMPETITOR` are `KNOWN_COMPETITOR`; all others are `OTHER`.

Canonical feature values are `ORGANIC`, `PAID`, `FEATURED_SNIPPET`, `AI_ANSWER`, `PEOPLE_ALSO_ASK`, `LOCAL_PACK`, `IMAGE`, `VIDEO`, `SHOPPING`, `KNOWLEDGE_PANEL`, `NEWS`, `DISCUSSION_FORUM`, `RELATED_SEARCH`, `SITELINK`, `MAP`, `OTHER`, and `UNKNOWN`. The adapter maps DataForSEO types deterministically and retains the original type. New nonempty types become `OTHER`, never organic; absent types become `UNKNOWN`.

## Collection and cost control

DataForSEO uses the Google Organic live advanced endpoint. Connections retain only a credential reference. For the CLI, `env:VARIABLE` points to ignored JSON containing `login` and `password`. The request preserves device, language, location, and requested depth. Collection metadata records provider task ID/cost, collector version, query, depth, source acquisition method, and policy version. Errors store their class only, preventing provider messages from leaking credentials.

Cost estimation is configuration-driven. `--unit-cost` is cost per provider task; the CLI default is **USD 0.002**, an operational placeholder last reviewed 2026-08-29, not a claim about current DataForSEO pricing. Monthly cadence multipliers are 1 for one-time, 4.345 for weekly, and 30 for daily. Formula: `ceil(queries × cadence multiplier) × unit cost`. Confirm current contract pricing before collection.

```bash
gis-serp configure --tenant vahomemath --site vahomemath --credential-reference env:DATAFORSEO_CREDENTIAL_JSON
gis-serp validate --connection UUID
gis-serp add --tenant vahomemath --site vahomemath --query "VA loan calculator" --device mobile --location-code 2840 --depth 20 --cadence WEEKLY
gis-serp list --tenant vahomemath --site vahomemath
gis-serp estimate --queries 100 --cadence WEEKLY --unit-cost 0.002
gis-serp sync --connection UUID --query-id UUID
gis-serp inspect --limit 10
```

Use an external scheduler to invoke active daily or weekly query sets. The epic intentionally adds no scheduler. Tests use fixtures and never make billable requests.

## Experience semantics

PageSpeed responses are split into CrUX `FIELD` observations and Lighthouse `LAB` observations. `URL` and `ORIGIN` scopes and `MOBILE`/`DESKTOP` form factors remain explicit. Field distributions retain good, needs-improvement, and poor proportions. A valid response without CrUX or Lighthouse metrics becomes `INSUFFICIENT_DATA`, not a failed run. Transport/provider errors yield a failed ingestion run.

CWV classification uses the documented 75th-percentile boundaries: LCP good at ≤2.5s and poor above 4s; INP good at ≤200ms and poor above 500ms; CLS good at ≤0.1 and poor above 0.25. Boundary values remain in the better category.

```bash
gis-experience configure --tenant vahomemath --site vahomemath --credential-reference env:PAGESPEED_API_KEY
gis-experience validate --connection UUID
gis-experience sync --connection UUID --target https://vahomemath.com/calculator --form-factor MOBILE --scope URL
gis-experience inspect --limit 20
```

PageSpeed may be called without an API key for limited use; omit the credential reference. Never place a key in connection JSON.

## Analytics and provenance

Staging models expose current SERP revisions, results, and experience observations. Intermediate models aggregate query/day, domain/day, and feature presence. Marts are:

- `mart_serp_query_daily`: own rank/presence, counts, diversity, feature density, visibility, and top-10 churn.
- `mart_serp_domain_daily`: best rank and transparent organic-position share.
- `mart_serp_visibility_daily`: site/day rollup.
- `mart_serp_feature_daily`: canonical feature presence.
- `mart_page_experience`: pivoted LCP, INP, CLS and classifications by period/type/scope/device.
- `mart_search_experience`: exact-query GSC metrics, best observed owned result, and same-date URL experience.

Top-10 churn is `1 - current top-10 URLs also present in the prior observation / current top-10 URL count`. It is null without a prior observation. This is a descriptive measure, not anomaly detection. Search/experience joins are correlational and make no causal ranking claim.

Run `dbt build`, then register the generated manifest:

```bash
gis-provenance register-dbt --manifest analytics/target/manifest.json
gis-provenance trace gis_analytics.mart_serp_query_daily
```

The trace follows dbt dependencies to `gis_raw.serp_observation`/`serp_result`, then DataForSEO. Experience raw assets link to PageSpeed. Sources use the seeded unreviewed policy: every permission remains `UNKNOWN` until a reviewed policy is attached, so governed downstream use fails closed.

## Limitations and extension

The initial adapter uses synchronous live tasks and does not retry automatically; scheduled orchestration may retry failed queries independently. A single CLI invocation collects one query, making partial-batch behavior an orchestration concern. Raw provider payloads are not retained, only small diagnostic metadata. Future providers should implement the provider protocol and canonical taxonomy; future opportunity rules may consume these marts but do not belong in this epic.
