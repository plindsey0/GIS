with ga4 as (
  select tenant_id, site_id, observed_date as date,
    {{ classify_channel('provider_channel', 'source', 'medium') }} as gis_channel,
    provider_channel, source, medium, sum(sessions) as sessions,
    sum(active_users) as active_users, sum(new_users) as new_users,
    sum(engaged_sessions) as engaged_sessions, sum(key_events) as key_events,
    0::bigint as first_party_sessions, 0::bigint as conversions
  from {{ ref('stg_ga4_acquisition') }} group by 1, 2, 3, 4, 5, 6, 7
), fp as (
  select s.tenant_id, s.site_id, s.analytical_date as date, s.gis_channel,
    '(first-party only)'::text as provider_channel, s.initial_utm_source as source,
    s.initial_utm_medium as medium, 0::numeric as sessions, 0::numeric as active_users,
    0::numeric as new_users, 0::numeric as engaged_sessions, 0::numeric as key_events,
    count(distinct s.session_id) as first_party_sessions,
    count(distinct c.conversion_id) as conversions
  from {{ ref('int_session_entry') }} s
  left join {{ ref('stg_conversions') }} c
    on c.tenant_id = s.tenant_id and c.site_id = s.site_id and c.session_id = s.session_id
  group by 1, 2, 3, 4, 5, 6, 7
)
select *, {{ safe_divide('engaged_sessions', 'sessions') }} as engagement_rate
from (select * from ga4 union all select * from fp) combined
