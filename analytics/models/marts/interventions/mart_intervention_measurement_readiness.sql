select tenant_id, site_id, measurement_readiness, feasibility, count(*) as intervention_count
from {{ ref('stg_interventions') }} group by 1,2,3,4
