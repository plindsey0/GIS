select id as experiment_id, tenant_id, site_id, intervention_id, measurement_contract_id,
 experiment_type::text as experiment_type, status::text as status, method_version,
 invalidation_reason, planned_sample_size, observed_sample_size, contamination_json,
 created_at, updated_at from {{ source('gis_core', 'experiment') }}
