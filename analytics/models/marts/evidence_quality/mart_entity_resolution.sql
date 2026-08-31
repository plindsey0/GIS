select s.tenant_id, s.site_id, a.identity_assertion_id, a.relationship,
       a.computed_strength, a.effective_strength, a.resolution_method,
       a.method_version, a.status, a.effective_start, a.effective_end,
       s.entity_type as subject_type, s.canonical_key as subject_key,
       o.entity_type as object_type, o.canonical_key as object_key
from {{ ref('stg_identity_assertions') }} a
join {{ ref('stg_analytical_entities') }} s on s.analytical_entity_id = a.subject_entity_id
join {{ ref('stg_analytical_entities') }} o on o.analytical_entity_id = a.object_entity_id

