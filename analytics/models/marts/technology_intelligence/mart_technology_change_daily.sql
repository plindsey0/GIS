select tenant_id, site_id, domain, observed_at::date as date,
       technology_slug, category, detected_version, previous_version,
       case when observation_sequence=1 then 'ADDED'
            when detected_version is not null and detected_version is distinct from previous_version then 'VERSION_CHANGED'
       end as change_type,
       'GIS_DERIVED_COMPARABLE_PRESENT_OBSERVATIONS' as semantics
from {{ ref('int_technology_history') }}
where observation_sequence=1
   or (detected_version is not null and detected_version is distinct from previous_version)
