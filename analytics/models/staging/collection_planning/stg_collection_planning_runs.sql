select id as planning_run_id, tenant_id, site_id, market_definition_id,
       market_definition_version, policy_id, policy_version, evaluated_at, fingerprint,
       target_count, proposed_monthly_cost, currency, metadata, created_at
from {{ source('gis_core', 'collection_planning_run') }}
