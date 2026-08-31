select tenant_id, site_id, primary_opportunity_id, status, count(*) as intervention_count
from {{ ref('stg_interventions') }} group by 1,2,3,4
