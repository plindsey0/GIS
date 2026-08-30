select event_time, event_domain, event_type, subject_domain, subject_key, semantic_class,
       confidence, magnitude, magnitude_unit, evidence_count, interpretation
from gis_analytics.mart_executive_recent_events
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and event_time::date >= {{start_date}}]] [[and event_time::date <= {{end_date}}]]
order by event_time desc limit 100
