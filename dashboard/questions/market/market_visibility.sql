select date, domain, ownership, reciprocal_rank_visibility_share,
       provider_volume_weighted_visibility_share, visibility_method,
       visibility_method_version, volume_semantics
from gis_analytics.mart_market_visibility_daily where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
order by date desc, reciprocal_rank_visibility_share desc limit 100
