select
  r.id as calculator_run_id, r.tenant_id, r.site_id, r.session_id,
  r.calculator_run_key, r.calculator_type, r.started_at, r.completed_at,
  (r.started_at at time zone s.timezone)::date as analytical_date,
  r.initial_page_path, r.input_schema_version, r.result_schema_version,
  r.input_bucket_data, r.result_bucket_data, r.recalculation_count,
  r.data_source_connection_id as connection_id, r.rights_policy_id
from {{ source('gis_core', 'calculator_run') }} r
join {{ source('gis_core', 'site') }} s
  on s.tenant_id = r.tenant_id and s.id = r.site_id
