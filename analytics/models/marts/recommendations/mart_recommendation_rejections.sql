select tenant_id, site_id, reason_category, count(*) as rejection_count
from {{ ref('mart_recommendation_history') }} where decision='REJECT'
group by tenant_id, site_id, reason_category
