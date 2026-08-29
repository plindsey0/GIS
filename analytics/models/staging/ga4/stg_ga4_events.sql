select
  id as observation_id, tenant_id, site_id, observed_date, event_name,
  landing_page, page_path, session_default_channel_group as provider_channel,
  device_category as device, country, event_count, total_users,
  event_count_per_user, key_events,
  data_source_connection_id as connection_id, rights_policy_id,
  observed_at, ingested_at
from {{ source('gis_raw', 'ga4_event_observation') }}
where effective_end is null
