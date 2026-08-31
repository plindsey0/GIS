select id as demand_signal_evidence_id, signal_id, demand_observation_id, role,
       source_system, evidence_key, semantic_class, metadata, created_at
from {{ source('gis_core', 'demand_signal_evidence') }}

