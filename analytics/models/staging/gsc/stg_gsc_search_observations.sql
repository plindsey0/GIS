select
  id as observation_id, tenant_id, site_id, observed_date, query,
  lower(regexp_replace(trim(query), '\\s+', ' ', 'g')) as normalized_query, page,
  country, device, search_appearance, search_type, collection_grain,
  clicks, impressions, ctr, position,
  data_source_connection_id as connection_id, rights_policy_id,
  observed_at, ingested_at
from {{ source('gis_raw', 'gsc_search_observation') }}
where effective_end is null
