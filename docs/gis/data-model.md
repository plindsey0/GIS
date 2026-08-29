# GIS foundation data model

```mermaid
erDiagram
    TENANT ||--o{ ORGANIZATION : owns
    TENANT ||--o{ SITE : owns
    ORGANIZATION ||--o{ SITE : contains
    SITE ||--o{ DOMAIN : identifies
    TENANT ||--o{ DATA_SOURCE_CONNECTION : owns
    SITE o|--o{ DATA_SOURCE_CONNECTION : scopes
    DATA_SOURCE ||--o{ DATA_SOURCE_CONNECTION : provides
    DATA_RIGHTS_POLICY o|--o{ DATA_SOURCE : defaults
    DATA_RIGHTS_POLICY o|--o{ DATA_SOURCE_CONNECTION : overrides
    DATA_SOURCE_CONNECTION ||--o{ INGESTION_RUN : executes
    TENANT ||--o{ INGESTION_RUN : owns
    SITE o|--o{ INGESTION_RUN : scopes
    INGESTION_RUN ||--o{ GSC_SEARCH_OBSERVATION : records
    DATA_SOURCE_CONNECTION ||--o{ GSC_SEARCH_OBSERVATION : sources
    DATA_RIGHTS_POLICY ||--o{ GSC_SEARCH_OBSERVATION : governs
    INGESTION_RUN ||--o{ GA4_LANDING_PAGE_OBSERVATION : records
    INGESTION_RUN ||--o{ GA4_ACQUISITION_OBSERVATION : records
    INGESTION_RUN ||--o{ GA4_EVENT_OBSERVATION : records
    SITE ||--o{ SESSION : receives
    SESSION ||--o{ EVENT : contains
    SESSION ||--o{ CALCULATOR_RUN : contains
    CALCULATOR_RUN o|--o{ EVENT : relates
    EVENT o|--o| CONVERSION : produces
```

## Tables

`tenant` is the security and ownership boundary. Its globally unique slug is a stable lookup
key and status is explicitly managed.

`organization` groups sites within a tenant. Its slug is unique within that tenant.

`site` represents a web property or product. Sites belong to an organization in the same
tenant, have a canonical URL and business timezone, and have tenant-local unique slugs.

`domain` records hostnames historically associated with a site. The same hostname can be
modeled intentionally for different tenants/sites, while duplicates within one site are
rejected. A partial unique index permits only one primary domain per site.

`data_rights_policy` records machine-readable rights. Every permission uses `ALLOWED`,
`PROHIBITED`, or `UNKNOWN`; missing knowledge can never silently become permission. Null is
reserved for genuinely inapplicable metadata such as an unknown retention period or absent
license URL. This epic stores policy metadata but does not implement enforcement.

`data_source` is the extensible provider registry. Keys are unique strings; adding a provider
does not require changing an enum. `source_type` provides broad operational classification.

`data_source_connection` associates a source with a tenant and optionally a site. Configuration
is JSONB, credentials are references, and sync timestamps support later connector operations.
The optional rights policy overrides the source default.

`ingestion_run` records collection executions with status, counts, cursor, errors, and timing.
Successful, partial, and failed runs all remain historical records.

`gis_raw.gsc_search_observation` stores typed Search Analytics dimensions and metrics. Its
`observation_key` is SHA-256 over tenant, site, connection, reporting date, search type,
collection grain, query, page, country, device, and search appearance. Metrics and ingestion
timestamps are deliberately excluded. A partial unique index permits one current row per key;
older provider revisions have a non-null `effective_end`. Query and page values remain faithful
text, while SHA-256 companion columns support selective lookup without indexing large text.

`observed_date` is Google's Pacific-time reporting date. `observed_at` is that reporting day's
Pacific midnight converted to UTC. `ingested_at` is the actual GIS storage time.

The three `gis_raw.ga4_*_observation` tables store typed landing-page, traffic-acquisition, and
event aggregates. They share tenant/site/connection/run/rights provenance and immutable effective
windows. Their `observed_date` uses the GA4 property's timezone and `observed_at` is that local
midnight converted to UTC. Stable keys include the complete report dimension tuple but exclude
metrics, so corrected provider values append a revision instead of changing identity.

Canonical `session`, `event`, `calculator_run`, and `conversion` tables store exact first-party
product behavior in `gis_core`. Composite foreign keys prevent tenant/site/connection mismatches.
Externally generated UUIDs make sessions, events, runs, and conversions idempotent within their
tenant/site scope. JSONB is limited to validated event-specific properties and bucketed calculator
attributes; frequently queried identity, time, path, taxonomy, and relationship fields are typed.

## Future typed observations

New observation tables should use UUID primary keys, explicit `tenant_id`, appropriate optional
`site_id`, and the provenance convention in `gis.models.ProvenanceMixin`. Add composite tenant
foreign keys so database constraints prevent cross-tenant associations. Use typed columns for
stable facts, JSONB only for provider-specific metadata, and never overwrite older observations
to represent the newest state.
