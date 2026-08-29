select tenant_id, site_id, analytical_date as date, conversion_type,
  count(*) as conversions, count(distinct session_id) as sessions_with_conversion,
  count(distinct calculator_run_id) as calculator_runs_with_conversion,
  currency, sum(conversion_value) as conversion_value
from {{ ref('stg_conversions') }}
group by 1, 2, 3, 4, 8
