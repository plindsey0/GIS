select i.tenant_id, i.site_id, i.intervention_id, i.primary_opportunity_id,
 h.lifecycle_event_id, h.from_status, h.to_status, h.actor, h.reason, h.occurred_at
from {{ ref('stg_interventions') }} i join {{ ref('stg_intervention_lifecycle') }} h using (intervention_id)
