select id as lifecycle_event_id, intervention_id, from_status::text as from_status,
 to_status::text as to_status, actor, reason, occurred_at
from {{ source('gis_core', 'intervention_lifecycle_event') }}
