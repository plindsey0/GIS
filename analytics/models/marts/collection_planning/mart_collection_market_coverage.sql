select tenant_id, site_id, market_definition_id, market_definition_version,
       count(*) as known_target_count,
       count(*) filter (where effective_status='ACTIVE') as active_target_count,
       count(*) filter (where priority_tier in ('CRITICAL','HIGH')) as high_priority_target_count,
       count(*) filter (where priority_tier in ('CRITICAL','HIGH') and primary_blocker='NONE') as high_priority_unblocked_count,
       case when count(*) filter (where priority_tier in ('CRITICAL','HIGH'))=0 then null
            else count(*) filter (where priority_tier in ('CRITICAL','HIGH') and primary_blocker='NONE')::numeric /
                 count(*) filter (where priority_tier in ('CRITICAL','HIGH')) end as known_target_coverage_rate,
       'MARKET_DISCOVERY_COMPLETENESS_UNKNOWN' as discovery_completeness
from {{ ref('mart_collection_target_current') }} group by 1,2,3,4
