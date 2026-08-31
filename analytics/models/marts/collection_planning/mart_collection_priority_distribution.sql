select tenant_id, site_id, market_definition_id, market_definition_version,
       priority_tier, effective_status, count(*) as target_count,
       avg(priority_score) as average_priority_score
from {{ ref('mart_collection_target_current') }}
group by 1,2,3,4,5,6
