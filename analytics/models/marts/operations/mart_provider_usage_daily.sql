select
  u.tenant_id,
  u.site_id,
  u.provider_id,
  p.provider_key,
  date_trunc('day', u.occurred_at)::date as usage_date,
  u.currency,
  sum(u.request_count) as request_count,
  sum(u.unit_count) as unit_count,
  sum(coalesce(u.actual_cost, u.estimated_cost, u.reserved_cost, 0)) as governed_cost,
  count(*) filter (where u.cost_semantics = 'PROVIDER_REPORTED') as provider_reported_events,
  count(*) filter (where u.status = 'RESERVED') as active_reservations
from {{ source('gis_core', 'provider_usage_event') }} u
join {{ source('gis_core', 'provider_definition') }} p on p.id = u.provider_id
where u.status in ('RESERVED', 'SUCCEEDED')
group by 1,2,3,4,5,6
