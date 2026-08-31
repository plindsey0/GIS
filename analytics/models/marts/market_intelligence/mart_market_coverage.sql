select tenant_id, site_id, market_definition_id, market_definition_version,
       effective_date as date, configured_query_count, observed_query_count,
       configured_query_count-observed_query_count as missing_query_count,
       query_coverage_rate, coverage_status, source_coverage,
       (source_coverage->>'serp_observations')::integer as serp_observation_count,
       (source_coverage->>'external_rankings')::integer as external_ranking_count,
       case when observed_query_count=0 then 'NO_DATA' else 'AVAILABLE' end as data_availability
from {{ ref('stg_market_observations') }}
