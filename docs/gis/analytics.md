# GIS analytical transformation layer

## Ownership and execution

The dbt Core project lives in `analytics/` and runs directly against PostgreSQL. Alembic owns
`gis_core` and `gis_raw`; dbt reads those schemas and exclusively owns derived relations in:

- `gis_staging`: views with current provider rows and lightly renamed canonical entities;
- `gis_intermediate`: views containing page identity, channel, daily source, and funnel logic;
- `gis_analytics`: rebuilt tables designed for Metabase and rule-engine consumption.

Full refresh tables are intentionally used at current scale. Rebuilding naturally incorporates
provider revisions and late-arriving telemetry without fragile incremental windows.

## Source and staging models

Sources include GSC and all three GA4 observation tables from `gis_raw`, plus tenant, site, domain,
source, connection, rights, session, event, calculator run, and conversion tables from `gis_core`.

Provider staging selects only `effective_end is null`. It never treats old revisions as additional
activity. First-party staging derives an analytical date by converting UTC occurrence/start time to
the site's IANA timezone. GSC and GA4 retain their provider reporting dates; they are not shifted.

Staging views are:

- `stg_gsc_search_observations`
- `stg_ga4_landing_pages`, `stg_ga4_acquisition`, `stg_ga4_events`
- `stg_sessions`, `stg_events`, `stg_calculator_runs`, `stg_conversions`

## Page identity

`int_page_identity` creates a lightweight analytical identity rather than a permanent Page entity.
It removes schemes and hosts from path identity, strips query strings/fragments, converts empty
paths to `/`, removes trailing slashes except for `/`, and preserves path case. Hosts are lowercased
and retained when GSC supplies an absolute URL. The stable key is:

```text
md5(site_id + "|" + normalized_path)
```

All joins also include tenant and site. Thus an absolute GSC URL, GA4 landing path, and first-party
path can map together without joining one tenant's paths to another tenant. Original provider
values remain available in the mapping view.

## Channel classification

Raw channel fields remain unchanged. GIS classification uses this deterministic priority:

1. `gclid`/`msclkid`, paid-search channel, or CPC/PPC medium → `paid_search`;
2. organic-search channel or organic medium → `organic_search`;
3. social or email channel/medium;
4. explicit direct or no source/referrer → `direct`;
5. referral channel or remaining referrer → `referral`;
6. no usable values → `unknown`;
7. otherwise → `other`.

This is first-touch classification, not an attribution model. First-party acquisition rows are
kept separate from GA4 provider rows, preventing counts from being duplicated across GA4 source
and medium combinations.

## Intermediate models

- `int_page_identity`: cross-source path mapping and deterministic key.
- `int_session_entry`: session entry page and GIS channel.
- `int_calculator_funnel`: run-level exact lifecycle flags and event times.
- `int_conversion_funnel`: conversions enriched with session page/channel.
- `int_search_page_daily`: page-grain GSC totals; query/page is used only when no page-grain data
  exists for that tenant/site/date.
- `int_behavior_page_daily`: page/day GA4 and exact first-party behavior kept in separate columns.

## Analytical marts

| Mart | Grain | Purpose |
|---|---|---|
| `mart_site_daily` | tenant, site, date | Executive source-specific site performance |
| `mart_page_daily` | tenant, site, page key, date | Search, landing, product, and conversion page performance |
| `mart_keyword_daily` | tenant, site, query, date | GSC-observed query visibility |
| `mart_keyword_page_daily` | tenant, site, query, page key, date | Query/page relationship |
| `mart_acquisition_daily` | tenant, site, date, GIS/provider channel, source, medium | Provider acquisition and separate first-party entry attribution |
| `mart_calculator_performance` | tenant, site, date, calculator type | Exact product funnel and recalculation behavior |
| `mart_conversion_daily` | tenant, site, date, type, currency | Canonical conversions without mixing currencies |
| `mart_search_funnel` | tenant, site, page key, date | Observable search-to-product chain |
| `mart_data_reconciliation` | tenant, site, date | Source presence, deltas, ratios, and simple quality status |

Cross-source ratios are reconciliation indicators, not causal funnel probabilities. GSC clicks,
GA4 sessions, and exact first-party sessions remain separate even when their page/date aligns.

## Metric dictionary

| Metric | Source and definition | Grain/limitation |
|---|---|---|
| `gsc_impressions` | Sum of current GSC impressions | Provider visibility, not search volume |
| `gsc_clicks` | Sum of current GSC clicks | May omit privacy-protected detail |
| `gsc_ctr` | clicks / impressions | NULL with zero impressions; never average row CTR |
| `gsc_avg_position` | impression-weighted position | GSC reporting semantics |
| `ga4_sessions` | Sum of GA4 report sessions | Provider aggregate, not GIS sessions |
| `ga4_engaged_sessions` | Sum of GA4 engaged sessions | Provider aggregate |
| `ga4_engagement_rate` | engaged sessions / sessions | NULL with zero sessions |
| `first_party_sessions` | Count of exact canonical GIS sessions | Site-local entry date |
| `calculator_views` | Count of exact `calculator_view` events | Event count |
| `calculator_starts` | Unique runs with start | Exact first-party lifecycle |
| `calculator_completions` | Unique completed runs | Exact first-party lifecycle |
| `calculator_start_rate` | starts / first-party sessions | Page/site denominator is entry sessions |
| `calculator_completion_rate` | completed runs / started runs | NULL with zero starts |
| `cta_clicks` | Exact `cta_click` event count | May exceed sessions |
| `lead_form_completions` | Exact accepted completion event count | Not equivalent to every conversion type |
| `conversions` | Count of canonical conversion rows | Exact GIS business outcomes |
| `session_conversion_rate` | conversions / first-party sessions | NULL with zero sessions |

Undefined rates are NULL. Aggregations never average existing CTR or engagement-rate rows when
constituent counts are available. Conversion values remain grouped by currency.

## Reconciliation and rights

`mart_data_reconciliation` exposes the three organic counts, presence flags, deltas, ratios, and
statuses such as `PARTIAL_SOURCE_COVERAGE`, `HIGH_GSC_GA4_VARIANCE`, and
`HIGH_GA4_FIRST_PARTY_VARIANCE`. Disagreement is expected evidence, not automatically an error.

Marts retain tenant/site and source-presence lineage. dbt documentation supplies model ancestry.
Derived data does not acquire broader rights: downstream enforcement must evaluate every
contributing source policy.

## Tests and commands

Copy the environment-based profile once, configure the PostgreSQL variables, then run:

```bash
cp analytics/profiles.yml.example analytics/profiles.yml
export DBT_HOST=localhost DBT_PORT=5432 DBT_USER=gis DBT_PASSWORD=gis DBT_DATABASE=gis
dbt debug --project-dir analytics --profiles-dir analytics
dbt build --project-dir analytics --profiles-dir analytics
dbt test --project-dir analytics --profiles-dir analytics
dbt docs generate --project-dir analytics --profiles-dir analytics
```

Tests cover source/staging keys, accepted channels, mart keys, unique grains, metric bounds,
current provider versions, page normalization, and deterministic search-funnel arithmetic. The
fictional unit fixture preserves 10,000 GSC impressions/500 clicks, 450 GA4 sessions/300 engaged
sessions, and 420 first-party sessions/180 starts/120 completions/35 CTA clicks/15 leads/12
conversions as distinct values.

Epic 6 can connect Metabase directly to the nine `gis_analytics` tables. Epic 7 can use historical
impressions, clicks, weighted position, engagement, calculator, conversion, reconciliation, and
data-presence fields without reproducing transformation logic.
