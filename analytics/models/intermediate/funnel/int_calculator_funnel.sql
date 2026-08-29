with event_rollup as (
  select tenant_id, site_id, session_id, calculator_run_id,
    bool_or(event_name = 'calculator_start') as calculator_started,
    bool_or(event_name = 'calculator_recalculate') as calculator_recalculated,
    bool_or(event_name = 'calculator_complete') as calculator_completed,
    bool_or(event_name = 'cta_view') as cta_viewed,
    bool_or(event_name = 'cta_click') as cta_clicked,
    bool_or(event_name = 'lead_form_start') as lead_form_started,
    bool_or(event_name = 'lead_form_complete') as lead_form_completed,
    min(occurred_at) filter (where event_name = 'calculator_start') as calculator_started_at,
    min(occurred_at) filter (where event_name = 'calculator_complete') as calculator_completed_at,
    min(occurred_at) filter (where event_name = 'cta_click') as cta_clicked_at,
    min(occurred_at) filter (where event_name = 'lead_form_complete') as lead_form_completed_at
  from {{ ref('stg_events') }} group by 1, 2, 3, 4
), conversions as (
  select tenant_id, site_id, session_id, calculator_run_id,
    true as converted, min(occurred_at) as conversion_at
  from {{ ref('stg_conversions') }} group by 1, 2, 3, 4
)
select r.tenant_id, r.site_id, r.analytical_date, r.calculator_run_id, r.session_id,
  r.calculator_type, r.started_at as session_calculator_started_at, r.completed_at,
  r.recalculation_count, coalesce(e.calculator_started, true) as calculator_started,
  coalesce(e.calculator_recalculated, false) as calculator_recalculated,
  coalesce(e.calculator_completed, r.completed_at is not null) as calculator_completed,
  coalesce(e.cta_viewed, false) as cta_viewed, coalesce(e.cta_clicked, false) as cta_clicked,
  coalesce(e.lead_form_started, false) as lead_form_started,
  coalesce(e.lead_form_completed, false) as lead_form_completed,
  coalesce(c.converted, false) as converted,
  e.calculator_started_at, e.calculator_completed_at, e.cta_clicked_at,
  e.lead_form_completed_at, c.conversion_at
from {{ ref('stg_calculator_runs') }} r
left join event_rollup e using (tenant_id, site_id, session_id, calculator_run_id)
left join conversions c using (tenant_id, site_id, session_id, calculator_run_id)
