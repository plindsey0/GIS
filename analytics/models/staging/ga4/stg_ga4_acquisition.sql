select
  id as observation_id, tenant_id, site_id, observed_date,
  session_default_channel_group as provider_channel,
  session_source as source, session_medium as medium,
  session_campaign as campaign, device_category as device, country,
  sessions, active_users, new_users, engaged_sessions, engagement_rate,
  event_count, key_events, data_source_connection_id as connection_id,
  rights_policy_id, observed_at, ingested_at
from {{ source('gis_raw', 'ga4_acquisition_observation') }}
where effective_end is null
