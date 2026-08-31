select date, observed_hhi, effective_participant_count, top_1_share,
       top_3_share, top_5_share, observed_participant_count, long_tail_share, semantics
from gis_analytics.mart_market_concentration_daily where 1=1
[[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and date >= {{start_date}}]] [[and date <= {{end_date}}]] order by date
