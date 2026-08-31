select tenant_id, site_id, market_definition_id, market_definition_version,
       effective_date as date, domain, ownership,
       visibility_share as reciprocal_rank_visibility_share,
       volume_weighted_visibility_share as provider_volume_weighted_visibility_share,
       'RECIPROCAL_RANK_VISIBILITY' as visibility_method,
       '1.0.0' as visibility_method_version,
       case when volume_weighted_visibility_share is null then 'NO_PROVIDER_VOLUME_DATA'
            else 'PROVIDER_REPORTED_VOLUME_WEIGHTED' end as volume_semantics
from {{ ref('stg_market_participant_observations') }}
