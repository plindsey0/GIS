select id as recommendation_id, run_id as recommendation_run_id, tenant_id, site_id,
 opportunity_id, analytical_entity_id, market_definition_id, market_definition_version,
 status::text as status, summary, assumptions_json, limitations_json, identity_hash,
 created_at, updated_at
from {{ source('gis_core', 'recommendation') }}
