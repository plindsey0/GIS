select tenant_id, site_id, count(*) as reviewed_count,
 count(*) filter (where decision in ('ACCEPT','PARTIAL_ACCEPT')) as accepted_count,
 case when count(*) = 0 then null else
   count(*) filter (where decision in ('ACCEPT','PARTIAL_ACCEPT'))::numeric / count(*)
 end as acceptance_rate
from {{ ref('mart_recommendation_history') }}
group by tenant_id, site_id
