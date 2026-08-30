select d.*,
       row_number() over (partition by site_id, domain, technology_id, detection_scope order by observed_at, observation_id) as observation_sequence,
       lag(detected_version) over (partition by site_id, domain, technology_id, detection_scope order by observed_at, observation_id) as previous_version
from {{ ref('stg_technology_detections') }} d
where collection_status='SUCCESS' and presence_status='PRESENT'
