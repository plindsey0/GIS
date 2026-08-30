with counts as (
  select cohort_id, max(cohort_domain_count) as cohort_domain_count
  from {{ ref('int_technology_cohort_evidence') }} group by 1
), prevalence as (
  select cohort_id, tenant_id, site_id, frozen_at::date as date,
         technology_slug, technology_name, category,
         count(distinct domain) as domain_count
  from {{ ref('int_technology_cohort_evidence') }}
  group by 1,2,3,4,5,6,7
)
select p.*, c.cohort_domain_count,
       p.domain_count::numeric / nullif(c.cohort_domain_count,0) as descriptive_prevalence
from prevalence p join counts c using (cohort_id)
