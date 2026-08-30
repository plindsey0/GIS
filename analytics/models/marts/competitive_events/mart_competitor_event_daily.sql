select tenant_id, site_id, event_time::date as date, subject_domain,
       count(*) as event_count, count(distinct event_type) as event_types
from {{ ref('stg_competitive_events') }}
where status = 'ACTIVE' and subject_domain is not null
group by 1,2,3,4
