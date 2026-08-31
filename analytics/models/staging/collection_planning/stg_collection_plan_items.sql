select id as plan_item_id, decision_id, collector_capability_id,
       data_source_connection_id, desired_cadence, effective_cadence, rights_status,
       budget_decision, estimated_cost_per_run, estimated_runs_month,
       estimated_monthly_cost, currency, blocker, scheduled_target_id, applied_at,
       explanation_json, created_at
from {{ source('gis_core', 'collection_plan_item') }}
