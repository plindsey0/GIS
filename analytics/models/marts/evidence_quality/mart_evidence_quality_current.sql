with ranked as (
  select *, row_number() over (
    partition by tenant_id, site_id, analytical_entity_id, condition_key,
                 market_definition_id, market_definition_version
    order by created_at desc, evidence_package_id desc
  ) as rn
  from {{ ref('mart_evidence_quality_history') }}
)
select * from ranked where rn = 1

