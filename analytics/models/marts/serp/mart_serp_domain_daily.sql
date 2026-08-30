select *, organic_positions::numeric / nullif(sum(organic_positions) over (
  partition by tenant_id, site_id, observed_date, normalized_query, device
), 0) as organic_position_share
from {{ ref('int_serp_domain_daily') }}
