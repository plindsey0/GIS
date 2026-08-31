select date, market_definition_id, market_definition_version, observed_query_count,
       provider_reported_search_volume, observed_domain_count, owned_visibility_share,
       observed_visibility_hhi, effective_competitor_count, direct_participant_count,
       adjacent_participant_count, query_coverage_rate, coverage_status, semantics
from gis_analytics.mart_market_daily where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]] order by date desc
