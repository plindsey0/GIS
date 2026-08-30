with members as (
  select c.id as cohort_id, c.tenant_id, c.site_id, c.frozen_at,
         o.domain, o.ownership_class
  from {{ source('gis_core', 'competitive_content_cohort') }} c
  join {{ source('gis_core', 'competitive_content_cohort_member') }} m on m.cohort_id=c.id
  join {{ source('gis_raw', 'competitive_content_observation') }} o on o.id=m.observation_id
), member_counts as (
  select cohort_id,
         count(distinct domain) as cohort_domain_count,
         count(distinct domain) filter (where ownership_class='COMPETITOR') as competitor_domain_count
  from members
  group by 1
), candidates as (
  select m.*, mc.cohort_domain_count, mc.competitor_domain_count,
         d.observation_id, d.observed_at, d.technology_id, d.technology_slug,
         d.technology_name, d.category, d.detected_version, d.semantic_class,
         row_number() over (partition by m.cohort_id, m.domain, d.technology_id order by d.observed_at desc) as recency
  from members m
  join member_counts mc on mc.cohort_id=m.cohort_id
  join {{ ref('stg_technology_detections') }} d
    on d.site_id=m.site_id and d.domain=m.domain and d.observed_at <= m.frozen_at
  where d.presence_status='PRESENT'
)
select * from candidates where recency=1
