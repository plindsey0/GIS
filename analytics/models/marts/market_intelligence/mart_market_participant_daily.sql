select tenant_id, site_id, market_definition_id, market_definition_version,
       effective_date as date, domain, ownership, participant_class, query_count,
       ranking_page_count, serp_appearance_count, top_3_appearances,
       top_10_appearances, top_20_appearances, visibility_weight, visibility_share,
       volume_weighted_visibility, volume_weighted_visibility_share,
       query_overlap_rate, first_observed_at, last_observed_at,
       classification_method, classification_version,
       'ANALYTICAL_CLASSIFICATION_NOT_BUSINESS_OR_LEGAL_CONCLUSION' as semantics
from {{ ref('stg_market_participant_observations') }}
