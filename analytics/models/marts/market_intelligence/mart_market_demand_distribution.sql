select tenant_id, site_id, market_definition_id, market_definition_version,
       effective_date as date, segment_type, segment_key, query_count,
       provider_reported_search_volume,
       provider_reported_search_volume/sum(provider_reported_search_volume) over (
         partition by tenant_id,site_id,market_definition_id,market_definition_version,effective_date
       ) as provider_reported_demand_share,
       case when provider_reported_search_volume is null then 'NO_PROVIDER_VOLUME_DATA'
            else 'PROVIDER_REPORTED_INCOMPLETE' end as demand_semantics
from {{ ref('stg_market_segment_observations') }}
