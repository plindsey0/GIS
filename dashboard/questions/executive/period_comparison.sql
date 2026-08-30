select period_days, current_organic_clicks, prior_organic_clicks, organic_click_change,
       current_sessions, prior_sessions, session_change,
       current_conversions, prior_conversions, conversion_change, comparison_semantics
from gis_analytics.mart_executive_period_comparison
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]]
