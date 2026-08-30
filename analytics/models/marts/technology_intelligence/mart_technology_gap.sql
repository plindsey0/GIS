with counts as (
  select cohort_id, max(competitor_domain_count) as competitor_count
  from {{ ref('int_technology_cohort_evidence') }} group by 1
), cohort as (
  select cohort_id, tenant_id, site_id, technology_slug, technology_name, category,
         count(distinct domain) filter (where ownership_class='COMPETITOR') as competitor_domain_count,
         count(distinct domain) filter (where ownership_class='OWNED') as owned_domain_count
  from {{ ref('int_technology_cohort_evidence') }}
  group by 1,2,3,4,5,6
)
select c.cohort_id, c.tenant_id, c.site_id, c.technology_slug, c.technology_name, c.category,
       c.competitor_domain_count, n.competitor_count,
       c.competitor_domain_count::numeric/nullif(n.competitor_count,0) as competitor_prevalence,
       (c.owned_domain_count=0) as absent_from_owned,
       'OBSERVED_DIFFERENCE_NOT_RECOMMENDATION' as semantics
from cohort c join counts n using (cohort_id)
