select id as evidence_package_id, quality_run_id, tenant_id, site_id,
       analytical_entity_id, evidence_contract_id, demand_signal_id,
       market_definition_id, market_definition_version, condition_key, classification,
       period_start, period_end, sufficiency, identity_resolution,
       source_independence, corroboration, rights_usability, conflict_count,
       independent_source_count, limitations_json, identity_hash, method_version, created_at
from {{ source('gis_core', 'evidence_package') }}

