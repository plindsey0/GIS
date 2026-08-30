select
    id as observation_id,
    tenant_id,
    site_id,
    ingestion_run_id,
    data_source_connection_id,
    rights_policy_id,
    rights_policy_version,
    observation_type,
    target_domain,
    country_code,
    location_code,
    location_name,
    language_code,
    device,
    observed_date,
    observed_at,
    provider_reported_cost,
    estimated_cost,
    items_returned
from {{ source('gis_raw', 'external_search_observation') }}
where effective_end is null
