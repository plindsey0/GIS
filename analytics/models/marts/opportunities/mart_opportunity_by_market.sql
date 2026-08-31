select tenant_id, site_id, market_definition_id, market_definition_version, status,
       count(*) as opportunity_count
from {{ ref('stg_opportunities') }} group by 1,2,3,4,5
