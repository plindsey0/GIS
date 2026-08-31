select date, market_definition_version, hhi_change, owned_visibility_share_change,
       domain_count_change, provider_search_volume_change, comparability_status
from gis_analytics.mart_market_change where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]] order by date desc
