with periods as (
  select current_date - 27 as current_start, current_date as current_end,
         current_date - 55 as prior_start, current_date - 28 as prior_end,
         28 as period_days
), scoped as (
  select d.tenant_id, d.site_id, p.period_days,
         sum(d.organic_clicks) filter (where d.date between p.current_start and p.current_end and d.search_data_available) as current_organic_clicks,
         sum(d.organic_clicks) filter (where d.date between p.prior_start and p.prior_end and d.search_data_available) as prior_organic_clicks,
         sum(d.sessions) filter (where d.date between p.current_start and p.current_end and d.analytics_data_available) as current_sessions,
         sum(d.sessions) filter (where d.date between p.prior_start and p.prior_end and d.analytics_data_available) as prior_sessions,
         sum(d.conversions) filter (where d.date between p.current_start and p.current_end and d.telemetry_data_available) as current_conversions,
         sum(d.conversions) filter (where d.date between p.prior_start and p.prior_end and d.telemetry_data_available) as prior_conversions
  from {{ ref('mart_executive_site_daily') }} d cross join periods p
  where d.date between p.prior_start and p.current_end group by 1,2,3
)
select *, current_organic_clicks-prior_organic_clicks as organic_click_change,
       current_sessions-prior_sessions as session_change,
       current_conversions-prior_conversions as conversion_change,
       'EQUIVALENT_COMPLETE_28_DAY_PERIODS' as comparison_semantics
from scoped
