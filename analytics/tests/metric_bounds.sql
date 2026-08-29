select tenant_id, site_id, date from {{ ref('mart_site_daily') }}
where gsc_impressions < 0 or gsc_clicks < 0 or ga4_sessions < 0 or first_party_sessions < 0
   or calculator_starts < 0 or calculator_completions < 0 or conversions < 0
   or gsc_ctr not between 0 and 1
   or calculator_start_rate < 0 or calculator_completion_rate not between 0 and 1
   or session_conversion_rate < 0
union all
select tenant_id, site_id, date from {{ ref('mart_search_funnel') }}
where impressions < 0 or search_clicks < 0 or ga4_landing_sessions < 0 or first_party_sessions < 0
   or search_ctr not between 0 and 1 or calculator_completion_rate not between 0 and 1
