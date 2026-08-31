select id as override_id, target_id, override_type, forced_priority, forced_cadence,
       forced_capability_id, actor, reason, active, cleared_at, cleared_by,
       created_at, updated_at
from {{ source('gis_core', 'collection_target_override') }}
