with members as (
  select * from {{ ref('int_competitive_cohort_evidence') }}
), competitor_topics as (
  select m.cohort_id, t.normalized_term,
         count(distinct t.observation_id) as competitor_page_count
  from members m
  join {{ ref('stg_competitive_content_topics') }} t on t.observation_id=m.observation_id
  where m.ownership_class='COMPETITOR'
  group by 1,2
), cohort_counts as (
  select cohort_id, count(*) filter (where ownership_class='COMPETITOR') as competitor_count
  from members group by 1
), owned_topics as (
  select distinct m.cohort_id, t.normalized_term
  from members m
  join {{ ref('stg_competitive_content_topics') }} t on t.observation_id=m.observation_id
  where m.ownership_class='OWNED'
)
select c.cohort_id, c.normalized_term, c.competitor_page_count, n.competitor_count,
       c.competitor_page_count::numeric / nullif(n.competitor_count,0) as competitor_prevalence,
       (o.normalized_term is null) as absent_from_owned,
       'OBSERVED_DIFFERENCE_NOT_RECOMMENDATION' as semantics
from competitor_topics c
join cohort_counts n on n.cohort_id=c.cohort_id
left join owned_topics o on o.cohort_id=c.cohort_id and o.normalized_term=c.normalized_term
