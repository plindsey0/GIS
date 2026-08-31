select id as intervention_id, tenant_id, site_id, primary_opportunity_id, analytical_entity_id,
 intervention_type_id, market_definition_id, market_definition_version, status::text as status,
 feasibility::text as feasibility, measurement_readiness::text as measurement_readiness,
 title, parameters_json, constraints_json, risk_json, effort, estimated_cost, actual_cost,
 proposed_by, created_at, updated_at from {{ source('gis_core', 'intervention') }}
