select i.tenant_id, i.site_id, i.primary_opportunity_id, o.*
from {{ ref('stg_interventions') }} i join {{ ref('stg_intervention_outcomes') }} o using (intervention_id)
