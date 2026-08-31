select tenant_id, site_id, market_definition_id, market_definition_version,
       effective_date as date, segment_type, segment_key, segment_label,
       query_count, participant_count, provider_reported_search_volume,
       observed_visibility_hhi, method_key, method_version, semantic_class,
       'DESCRIPTIVE_SEGMENT_NOT_OPPORTUNITY' as semantics
from {{ ref('stg_market_segment_observations') }}
