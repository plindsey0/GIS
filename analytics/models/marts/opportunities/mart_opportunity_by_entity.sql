select tenant_id, site_id, analytical_entity_id, family, status, count(*) as opportunity_count
from {{ ref('stg_opportunities') }} group by 1,2,3,4,5
