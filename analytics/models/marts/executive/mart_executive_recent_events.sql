select tenant_id, site_id, competitive_event_id, public_id, event_time,
       event_domain, event_type, subject_type, subject_key, subject_domain, subject_url,
       semantic_class, confidence, magnitude, magnitude_unit, status,
       evidence_count, minimum_evidence_confidence,
       true as is_material, 'MATERIAL_BY_VERSIONED_SYNTHESIS_POLICY' as materiality_status,
       'MATERIALITY_AND_CONFIDENCE_ARE_DISTINCT' as interpretation
from {{ ref('mart_competitive_event_timeline') }}
