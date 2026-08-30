select a.tenant_id, a.site_id, a.domain, a.observed_at::date as date,
       a.technology_slug as technology_a, b.technology_slug as technology_b,
       a.observation_id
from {{ ref('stg_technology_detections') }} a
join {{ ref('stg_technology_detections') }} b
  on b.observation_id=a.observation_id and b.technology_slug > a.technology_slug
where a.presence_status='PRESENT' and b.presence_status='PRESENT'
