select tenant_id, site_id, event_time::date as date, event_domain,
       count(*) as events_today,
       sum(count(*)) over (partition by tenant_id, site_id, event_domain order by event_time::date rows between 6 preceding and current row) as events_trailing_7d
from {{ ref('stg_competitive_events') }} where status = 'ACTIVE'
group by 1,2,3,4
