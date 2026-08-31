select tenant_id, site_id, opportunity_id, opportunity_type, status, computed_status,
       detected_at, updated_at as state_updated_at
from {{ ref('stg_opportunities') }}
where status in ('RESOLVED', 'EXPIRED', 'DISMISSED', 'SUPERSEDED')
