select tenant_id, site_id, observed_at::date as date,
       count(distinct domain) as observed_domains,
       count(distinct technology_id) as unique_technologies,
       count(distinct category) as unique_categories
from {{ ref('stg_technology_detections') }} where presence_status='PRESENT'
group by 1,2,3
