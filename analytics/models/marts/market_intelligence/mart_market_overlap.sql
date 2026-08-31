select tenant_id, site_id, market_definition_id, market_definition_version,
       effective_date as date, domain, ownership, participant_class,
       query_count, query_overlap_rate,
       case when ownership='OWNED' then 'OWNED'
            when query_overlap_rate>=0.5 and query_count>=2 then 'SUBSTANTIAL_OVERLAP'
            when query_overlap_rate>=0.2 then 'PARTIAL_OVERLAP'
            else 'NARROW_OVERLAP' end as overlap_class,
       'OBSERVED_QUERY_SET_ONLY' as semantics
from {{ ref('stg_market_participant_observations') }}
