select
  e.id as event_row_id, e.event_id, e.tenant_id, e.site_id, e.session_id,
  e.calculator_run_id, e.event_name, e.event_version, e.occurred_at, e.received_at,
  (e.occurred_at at time zone s.timezone)::date as analytical_date,
  e.page_url, e.page_path, e.event_properties, e.sequence_number,
  e.data_source_connection_id as connection_id, e.rights_policy_id
from {{ source('gis_core', 'event') }} e
join {{ source('gis_core', 'site') }} s
  on s.tenant_id = e.tenant_id and s.id = e.site_id
