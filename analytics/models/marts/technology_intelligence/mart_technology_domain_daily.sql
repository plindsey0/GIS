select tenant_id, site_id, domain, observed_at::date as date,
       technology_slug, technology_name, category, detected_version,
       max(confidence) as confidence, max(semantic_class) as semantic_class,
       count(distinct observation_id) as supporting_observations
from {{ ref('stg_technology_detections') }}
where presence_status='PRESENT'
group by 1,2,3,4,5,6,7,8
