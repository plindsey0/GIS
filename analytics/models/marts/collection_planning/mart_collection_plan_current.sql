select h.tenant_id, h.site_id, h.market_definition_id, h.market_definition_version,
       h.target_id, h.target_type, h.normalized_identity, h.decision_id,
       h.priority_score, h.priority_tier, h.computed_status, h.effective_status,
       h.computed_cadence, h.effective_cadence as target_effective_cadence,
       i.plan_item_id, c.capability_key, c.evidence_product, c.pipeline_id,
       i.data_source_connection_id, i.desired_cadence, i.effective_cadence,
       i.rights_status, i.budget_decision, i.estimated_cost_per_run,
       i.estimated_runs_month, i.estimated_monthly_cost, i.currency, i.blocker,
       i.scheduled_target_id, i.applied_at, h.override_applied
from {{ ref('mart_collection_target_current') }} h
join {{ ref('stg_collection_plan_items') }} i using (decision_id)
join {{ ref('stg_collector_capabilities') }} c using (collector_capability_id)
