with runs as (
  select tenant_id, site_id, analytical_date as date, calculator_type,
    count(*) as calculator_starts,
    count(*) filter (where calculator_completed) as calculator_completions,
    sum(recalculation_count) as calculator_recalculations,
    count(distinct session_id) filter (where calculator_completed) as completion_sessions,
    count(*) filter (where cta_clicked) as cta_clicks,
    count(*) filter (where lead_form_started) as lead_form_starts,
    count(*) filter (where lead_form_completed) as lead_form_completions,
    count(*) filter (where converted) as conversions,
    percentile_cont(0.5) within group (order by recalculation_count) as median_recalculations_per_run
  from {{ ref('int_calculator_funnel') }} group by 1, 2, 3, 4
), views as (
  select tenant_id, site_id, analytical_date as date,
    coalesce(event_properties ->> 'calculator_type', 'unknown') as calculator_type,
    count(*) as calculator_views
  from {{ ref('stg_events') }} where event_name = 'calculator_view' group by 1, 2, 3, 4
), keys as (
  select tenant_id, site_id, date, calculator_type from runs union
  select tenant_id, site_id, date, calculator_type from views
)
select k.*, coalesce(v.calculator_views, 0) as calculator_views,
  coalesce(r.calculator_starts, 0) as calculator_starts,
  coalesce(r.calculator_recalculations, 0) as calculator_recalculations,
  coalesce(r.calculator_completions, 0) as calculator_completions,
  coalesce(r.completion_sessions, 0) as completion_sessions,
  coalesce(r.cta_clicks, 0) as cta_clicks, coalesce(r.lead_form_starts, 0) as lead_form_starts,
  coalesce(r.lead_form_completions, 0) as lead_form_completions,
  coalesce(r.conversions, 0) as conversions,
  {{ safe_divide('r.calculator_starts', 'v.calculator_views') }} as view_to_start_rate,
  {{ safe_divide('r.calculator_completions', 'r.calculator_starts') }} as start_to_complete_rate,
  {{ safe_divide('r.cta_clicks', 'r.calculator_completions') }} as complete_to_cta_rate,
  {{ safe_divide('r.lead_form_completions', 'r.cta_clicks') }} as cta_to_lead_rate,
  {{ safe_divide('r.conversions', 'r.calculator_starts') }} as start_to_conversion_rate,
  r.median_recalculations_per_run
from keys k left join runs r using (tenant_id, site_id, date, calculator_type)
left join views v using (tenant_id, site_id, date, calculator_type)
