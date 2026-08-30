select id as competitive_event_id, public_id, tenant_id, organization_id, site_id,
       subject_type, subject_id, subject_key, subject_domain, subject_url,
       event_domain, event_type, event_subtype, event_time, first_observed_at,
       detected_at, semantic_class, confidence, magnitude, magnitude_unit,
       status, synthesis_method, synthesis_method_version, policy_version,
       effective_rights_status, provider_cost, created_at
from {{ source('gis_core', 'competitive_event') }}
