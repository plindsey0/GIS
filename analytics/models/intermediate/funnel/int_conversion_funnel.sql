select c.tenant_id, c.site_id, c.analytical_date, c.conversion_id, c.conversion_type,
  c.session_id, c.calculator_run_id, c.occurred_at as conversion_at,
  c.conversion_value, c.currency, c.source_event_id,
  s.page_key, s.gis_channel
from {{ ref('stg_conversions') }} c
left join {{ ref('int_session_entry') }} s
  on s.tenant_id = c.tenant_id and s.site_id = c.site_id and s.session_id = c.session_id
