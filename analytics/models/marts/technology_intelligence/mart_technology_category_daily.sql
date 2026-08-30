select tenant_id, site_id, domain, observed_at::date as date, category,
       count(distinct technology_id) as technology_count
from {{ ref('stg_technology_detections') }} where presence_status='PRESENT'
group by 1,2,3,4,5
