select d.tenant_id, d.site_id, d.domain, d.observed_at, d.technology_slug,
       d.category, e.*
from {{ source('gis_raw', 'technology_evidence') }} e
join {{ ref('stg_technology_detections') }} d on d.detection_id=e.detection_id
