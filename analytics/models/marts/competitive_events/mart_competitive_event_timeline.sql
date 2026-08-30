with evidence as (
    select tenant_id, site_id, competitive_event_id, count(*) as evidence_count,
           min(confidence) as minimum_evidence_confidence
    from {{ ref('stg_competitive_event_evidence') }}
    group by 1,2,3
)
select e.*, coalesce(ev.evidence_count, 0) as evidence_count, ev.minimum_evidence_confidence
from {{ ref('stg_competitive_events') }} e
left join evidence ev using (tenant_id, site_id, competitive_event_id)
where e.status = 'ACTIVE'
