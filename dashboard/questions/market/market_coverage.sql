select date, configured_query_count, observed_query_count, missing_query_count,
       query_coverage_rate, coverage_status, serp_observation_count,
       external_ranking_count, data_availability
from gis_analytics.mart_market_coverage where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]] order by date desc
