select
  se.id as session_id, se.tenant_id, se.site_id, se.session_key, se.started_at, se.last_event_at,
  (se.started_at at time zone s.timezone)::date as analytical_date,
  se.landing_url, se.landing_path, se.initial_referrer_domain as referrer_domain,
  se.initial_utm_source, se.initial_utm_medium, se.initial_utm_campaign,
  se.initial_gclid, se.initial_msclkid, se.device_category, se.country_code,
  se.anonymous_visitor_key, se.data_source_connection_id as connection_id, se.rights_policy_id
from {{ source('gis_core', 'session') }} se
join {{ source('gis_core', 'site') }} s
  on s.tenant_id = se.tenant_id and s.id = se.site_id
