select id as collector_capability_id, capability_key, pipeline_id, target_type,
       evidence_product, estimated_cost_per_run, currency, preference, active,
       configuration_json, created_at, updated_at
from {{ source('gis_core', 'collector_capability') }}
