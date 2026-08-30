select o.tenant_id, o.site_id, o.tracked_query_id, o.observed_at, o.domain,
       o.ownership_class, c.*
from {{ source('gis_raw', 'competitive_content_component') }} c
join {{ ref('stg_competitive_content_observations') }} o on o.observation_id=c.observation_id
