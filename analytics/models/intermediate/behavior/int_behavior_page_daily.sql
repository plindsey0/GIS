with ga4 as (
  select tenant_id, site_id, observed_date as date,
    {{ page_key('site_id', normalize_path('landing_page')) }} as page_key,
    sum(sessions) as ga4_sessions, sum(engaged_sessions) as ga4_engaged_sessions,
    sum(key_events) as ga4_key_events
  from {{ ref('stg_ga4_landing_pages') }} group by 1, 2, 3, 4
), fp_sessions as (
  select tenant_id, site_id, analytical_date as date, page_key,
    count(*) as first_party_sessions
  from {{ ref('int_session_entry') }} group by 1, 2, 3, 4
), fp_events as (
  select e.tenant_id, e.site_id, e.analytical_date as date,
    {{ page_key('e.site_id', normalize_path('coalesce(e.page_path, s.landing_path)')) }} as page_key,
    count(distinct e.calculator_run_id) filter (where e.event_name = 'calculator_start') as calculator_starts,
    count(distinct e.calculator_run_id) filter (where e.event_name = 'calculator_complete') as calculator_completions,
    count(*) filter (where e.event_name = 'cta_click') as cta_clicks,
    count(*) filter (where e.event_name = 'lead_form_complete') as lead_form_completions
  from {{ ref('stg_events') }} e
  join {{ ref('stg_sessions') }} s using (tenant_id, site_id, session_id)
  group by 1, 2, 3, 4
), conversions as (
  select tenant_id, site_id, analytical_date as date, page_key, count(*) as conversions
  from {{ ref('int_conversion_funnel') }} group by 1, 2, 3, 4
), keys as (
  select tenant_id, site_id, date, page_key from ga4 union
  select tenant_id, site_id, date, page_key from fp_sessions union
  select tenant_id, site_id, date, page_key from fp_events union
  select tenant_id, site_id, date, page_key from conversions
)
select k.*, coalesce(g.ga4_sessions, 0) as ga4_sessions,
  coalesce(g.ga4_engaged_sessions, 0) as ga4_engaged_sessions,
  {{ safe_divide('g.ga4_engaged_sessions', 'g.ga4_sessions') }} as ga4_engagement_rate,
  coalesce(g.ga4_key_events, 0) as ga4_key_events,
  coalesce(s.first_party_sessions, 0) as first_party_sessions,
  coalesce(e.calculator_starts, 0) as calculator_starts,
  coalesce(e.calculator_completions, 0) as calculator_completions,
  coalesce(e.cta_clicks, 0) as cta_clicks,
  coalesce(e.lead_form_completions, 0) as lead_form_completions,
  coalesce(c.conversions, 0) as conversions
from keys k
left join ga4 g using (tenant_id, site_id, date, page_key)
left join fp_sessions s using (tenant_id, site_id, date, page_key)
left join fp_events e using (tenant_id, site_id, date, page_key)
left join conversions c using (tenant_id, site_id, date, page_key)
