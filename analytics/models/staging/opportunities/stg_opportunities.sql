select id as opportunity_id, tenant_id, site_id, analytical_entity_id, market_definition_id,
       market_definition_version, detector_policy_id, family::text as family,
       opportunity_type, status::text as status, computed_status::text as computed_status,
       priority::text as priority, evidence_sufficiency::text as evidence_sufficiency,
       title, condition_description, detected_at, condition_first_observed_at,
       period_start, period_end, materiality_json, priority_components_json,
       limitations_json, created_at, updated_at
from {{ source('gis_core', 'opportunity') }}
