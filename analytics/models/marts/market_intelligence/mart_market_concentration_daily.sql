with ranked as (
  select *, row_number() over (
    partition by tenant_id,site_id,market_definition_id,market_definition_version,effective_date
    order by visibility_share desc,domain) as share_rank
  from {{ ref('stg_market_participant_observations') }}
)
select tenant_id, site_id, market_definition_id, market_definition_version,
       effective_date as date, sum(visibility_share*visibility_share) as observed_hhi,
       1/nullif(sum(visibility_share*visibility_share),0) as effective_participant_count,
       max(visibility_share) as top_1_share,
       sum(visibility_share) filter (where share_rank<=3) as top_3_share,
       sum(visibility_share) filter (where share_rank<=5) as top_5_share,
       count(*) as observed_participant_count,
       percentile_cont(0.5) within group (order by visibility_share) as median_share,
       sum(visibility_share) filter (where share_rank>5) as long_tail_share,
       'OBSERVED_MARKET_CONCENTRATION_NOT_ECONOMIC_CONCENTRATION' as semantics
from ranked group by 1,2,3,4,5
