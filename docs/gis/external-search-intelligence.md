# External search intelligence

Epic 16 adds provider-neutral evidence about the organic-search market beyond first-party GSC queries and controlled SERP observations. It does not score opportunities or generate recommendations.

## Architecture and canonical model

DataForSEO Labs Live is the first adapter. `ranked_keywords/live` supplies domain/page rankings and keyword context; `competitors_domain/live` supplies organic competitor overlap. Provider response shapes are normalized into:

- `gis_raw.external_search_observation`: revision-aware collection header, geography, rights, provenance, request/item counts, and cost.
- `gis_raw.external_keyword_ranking`: keyword/domain/page ranking evidence and explicitly labeled provider metrics.
- `gis_raw.external_competitor_observation`: provider competitor metrics plus separately labeled deterministic GIS strength.

An observation identity contains site, observation type, target, geography, language, device, and provider observation date. An identical replay creates no new observation. Changed content for the same identity closes the prior effective version and appends a revision. Controlled SERP evidence remains in its own tables.

Domain normalization removes scheme, port, path, leading `www`, and trailing dot, lowercases, and applies IDNA. Keyword normalization trims, case-folds, and collapses whitespace. Ranking URLs retain scheme/host/path but remove query and fragment, matching existing GIS URL semantics.

## Metric semantics

Metrics carry explicit semantic labels:

- `MEASURED`: directly observed first-party values; external provider estimates are never assigned this label.
- `PROVIDER_ESTIMATED`: DataForSEO search volume and estimated traffic/ETV.
- `PROVIDER_DERIVED`: provider CPC, relevance, intent, competition, or methodology-specific scores.
- `GIS_DERIVED`: transparent formulas, currently shared keywords divided by the larger domain footprint and search-volume divided by rank in marts.

Difficulty values are stored with `PROVIDER_DERIVED_DATAFORSEO`; they must not be compared as equivalent to future Ahrefs or Semrush scores without an explicit methodology layer. Unmapped provider fields remain in bounded provider metadata.

## Provider endpoints and cost

Both selected DataForSEO Labs endpoints are Live, one task per call, and updated from DataForSEO's search databases rather than reconstructed using controlled SERP calls:

- `POST /v3/dataforseo_labs/google/ranked_keywords/live`
- `POST /v3/dataforseo_labs/google/competitors_domain/live`

DataForSEO documents a task-plus-item pricing model. The CLI defaults, reviewed 2026-08-30, are placeholders of USD 0.012/task plus USD 0.00012/requested item and are overrideable. Provider-reported cost is stored separately from the pre-request estimate. Always run `estimate` or `--dry-run` before sync and verify current contract pricing. A limit of 10 estimates USD 0.0132; a limit of 100 estimates USD 0.024. A live sync may be billable.

## CLI

```bash
gis-search-intelligence configure --tenant TENANT --site SITE --credential-reference env:DATAFORSEO_CREDENTIAL_JSON
gis-search-intelligence validate --connection UUID
gis-search-intelligence estimate --limit 10
gis-search-intelligence keywords --connection UUID --site UUID --domain example.com --location-code 2840 --language en --limit 10 --dry-run
gis-search-intelligence competitors --connection UUID --site UUID --domain example.com --location-code 2840 --language en --limit 10 --dry-run
gis-search-intelligence sync --connection UUID --site UUID --domain example.com --location-code 2840 --kind ranked_keywords --limit 10
gis-search-intelligence inspect --limit 20
```

`validate` checks only local credential availability. It is not a provider call. `--dry-run` performs validation and cost estimation without HTTP. Credentials reuse the existing DataForSEO reference and are never printed.

## Rights, acquisition, provenance, and tenancy

Every collection resolves a tenant/site-compatible connection, source, acquisition classification, policy, and policy version. Site-scoped connections cannot cross sites; tenant-scoped connections remain possible. DataForSEO's existing policy stays `UNKNOWN`, and fail-closed evaluation remains unchanged. Access does not grant commercial use, customer display, export, RAG, AI inference, or training rights.

dbt sources register against DataForSEO and flow through staging into external keyword, domain, page, competitor, gap, and market-visibility marts. `mart_keyword_gap` joins external evidence to same-date normalized GSC and controlled SERP evidence, but deliberately does not score opportunity.

Future Semrush, Ahrefs, Similarweb, or BYOD adapters implement the provider collection contract and emit the canonical rows. They must preserve provider methodology and acquisition ownership rather than introduce new canonical columns for branded payload fields.

## Limitations

The initial adapter supports bounded current-state Labs observations, not broad pagination or historical bulk harvesting. Country-to-location discovery remains caller/configuration controlled. No live call was required during implementation; use a limit of one to ten only after a human reviews the displayed estimate and current provider pricing.
