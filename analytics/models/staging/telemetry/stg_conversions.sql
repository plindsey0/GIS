select
  c.id as conversion_row_id, c.conversion_id, c.tenant_id, c.site_id,
  c.session_id, c.calculator_run_id, c.conversion_type, c.occurred_at,
  (c.occurred_at at time zone s.timezone)::date as analytical_date,
  c.conversion_value, c.currency, c.source_event_id,
  c.data_source_connection_id as connection_id, c.rights_policy_id
from {{ source('gis_core', 'conversion') }} c
join {{ source('gis_core', 'site') }} s
  on s.tenant_id = c.tenant_id and s.id = c.site_id
