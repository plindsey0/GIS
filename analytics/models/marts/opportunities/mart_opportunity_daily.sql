select tenant_id, site_id, detected_at::date as date, status, priority, count(*) as opportunity_count
from {{ ref('stg_opportunities') }} group by 1,2,3,4,5
