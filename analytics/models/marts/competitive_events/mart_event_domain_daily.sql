select tenant_id, site_id, event_time::date as date, event_domain,
       count(*) as event_count, count(distinct subject_key) as affected_subjects
from {{ ref('stg_competitive_events') }} where status = 'ACTIVE'
group by 1,2,3,4
