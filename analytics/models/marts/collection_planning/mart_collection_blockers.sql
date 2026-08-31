select tenant_id, site_id, market_definition_id, market_definition_version,
       target_id, target_type, normalized_identity, priority_tier,
       capability_key, rights_status, budget_decision, blocker,
       estimated_monthly_cost, currency
from {{ ref('mart_collection_plan_current') }} where blocker<>'NONE'
