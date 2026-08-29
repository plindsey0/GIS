with keys as (
  select tenant_id, site_id, date, page_key from {{ ref('int_search_page_daily') }} union
  select tenant_id, site_id, date, page_key from {{ ref('int_behavior_page_daily') }}
)
select k.*, p.normalized_path, p.normalized_host,
  coalesce(s.impressions, 0) as gsc_impressions, coalesce(s.clicks, 0) as gsc_clicks,
  s.ctr as gsc_ctr, s.avg_position as gsc_avg_position,
  coalesce(b.ga4_sessions, 0) as ga4_sessions,
  coalesce(b.ga4_engaged_sessions, 0) as ga4_engaged_sessions,
  b.ga4_engagement_rate, coalesce(b.ga4_key_events, 0) as ga4_key_events,
  coalesce(b.first_party_sessions, 0) as first_party_sessions,
  coalesce(b.calculator_starts, 0) as calculator_starts,
  coalesce(b.calculator_completions, 0) as calculator_completions,
  coalesce(b.cta_clicks, 0) as cta_clicks, coalesce(b.conversions, 0) as conversions,
  {{ safe_divide('b.calculator_starts', 'b.first_party_sessions') }} as calculator_start_rate,
  {{ safe_divide('b.calculator_completions', 'b.calculator_starts') }} as calculator_completion_rate,
  {{ safe_divide('b.conversions', 'b.first_party_sessions') }} as session_conversion_rate
from keys k
left join {{ ref('int_page_identity') }} p using (tenant_id, site_id, page_key)
left join {{ ref('int_search_page_daily') }} s using (tenant_id, site_id, date, page_key)
left join {{ ref('int_behavior_page_daily') }} b using (tenant_id, site_id, date, page_key)
