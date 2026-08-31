select date, segment_type, segment_label, query_count, participant_count,
       provider_reported_search_volume, observed_visibility_hhi, semantic_class, semantics
from gis_analytics.mart_market_segment_daily where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]]
order by date desc, query_count desc
