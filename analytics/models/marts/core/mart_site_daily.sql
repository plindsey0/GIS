with gsc as (
  select tenant_id, site_id, date, sum(impressions) as gsc_impressions,
    sum(clicks) as gsc_clicks,
    {{ safe_divide('sum(avg_position * impressions)', 'sum(impressions)') }} as gsc_avg_position
  from {{ ref('int_search_page_daily') }} group by 1, 2, 3
), ga4 as (
  select tenant_id, site_id, observed_date as date, sum(sessions) as ga4_sessions,
    sum(active_users) as ga4_active_users, sum(new_users) as ga4_new_users,
    sum(engaged_sessions) as ga4_engaged_sessions
  from {{ ref('stg_ga4_acquisition') }} group by 1, 2, 3
), fp as (
  select tenant_id, site_id, analytical_date as date, count(*) as first_party_sessions
  from {{ ref('stg_sessions') }} group by 1, 2, 3
), events as (
  select tenant_id, site_id, analytical_date as date,
    count(*) filter (where event_name = 'calculator_view') as calculator_views,
    count(distinct calculator_run_id) filter (where event_name = 'calculator_start') as calculator_starts,
    count(distinct calculator_run_id) filter (where event_name = 'calculator_complete') as calculator_completions,
    count(*) filter (where event_name = 'cta_click') as cta_clicks,
    count(*) filter (where event_name = 'lead_form_complete') as lead_form_completions
  from {{ ref('stg_events') }} group by 1, 2, 3
), conversions as (
  select tenant_id, site_id, analytical_date as date, count(*) as conversions
  from {{ ref('stg_conversions') }} group by 1, 2, 3
), keys as (
  select tenant_id, site_id, date from gsc union select tenant_id, site_id, date from ga4 union
  select tenant_id, site_id, date from fp union select tenant_id, site_id, date from events union
  select tenant_id, site_id, date from conversions
)
select k.*, coalesce(g.gsc_impressions, 0) as gsc_impressions,
  coalesce(g.gsc_clicks, 0) as gsc_clicks,
  {{ safe_divide('g.gsc_clicks', 'g.gsc_impressions') }} as gsc_ctr, g.gsc_avg_position,
  coalesce(a.ga4_sessions, 0) as ga4_sessions, coalesce(a.ga4_active_users, 0) as ga4_active_users,
  coalesce(a.ga4_new_users, 0) as ga4_new_users,
  coalesce(a.ga4_engaged_sessions, 0) as ga4_engaged_sessions,
  {{ safe_divide('a.ga4_engaged_sessions', 'a.ga4_sessions') }} as ga4_engagement_rate,
  coalesce(f.first_party_sessions, 0) as first_party_sessions,
  coalesce(e.calculator_views, 0) as calculator_views,
  coalesce(e.calculator_starts, 0) as calculator_starts,
  coalesce(e.calculator_completions, 0) as calculator_completions,
  coalesce(e.cta_clicks, 0) as cta_clicks,
  coalesce(e.lead_form_completions, 0) as lead_form_completions,
  coalesce(c.conversions, 0) as conversions,
  {{ safe_divide('e.calculator_starts', 'f.first_party_sessions') }} as calculator_start_rate,
  {{ safe_divide('e.calculator_completions', 'e.calculator_starts') }} as calculator_completion_rate,
  {{ safe_divide('c.conversions', 'f.first_party_sessions') }} as session_conversion_rate,
  array_remove(array[
    case when g.tenant_id is null then 'MISSING_GSC' end,
    case when a.tenant_id is null then 'MISSING_GA4' end,
    case when f.tenant_id is null then 'MISSING_FIRST_PARTY' end
  ], null) as data_quality_flags
from keys k
left join gsc g using (tenant_id, site_id, date)
left join ga4 a using (tenant_id, site_id, date)
left join fp f using (tenant_id, site_id, date)
left join events e using (tenant_id, site_id, date)
left join conversions c using (tenant_id, site_id, date)
