select i.tenant_id, i.site_id, i.intervention_id, e.planned_at, e.actual_started_at,
 e.actual_completed_at, e.executor_type, e.status as execution_status,
 e.actual_parameters_json, e.artifact_reference, e.notes
from {{ ref('stg_interventions') }} i
join {{ source('gis_core', 'intervention_execution') }} e on e.intervention_id=i.intervention_id
