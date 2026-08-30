select tenant_id, site_id, domain, observed_at::date as date,
       count(distinct technology_id) as technology_count,
       count(distinct category) as category_count
from {{ ref('stg_technology_detections') }}
where ownership_class='COMPETITOR' and presence_status='PRESENT'
group by 1,2,3,4
