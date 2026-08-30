with policies as (
  select tenant_id,
         count(*) as policy_count,
         count(*) filter (where reviewed_at is not null) as reviewed_policy_count,
         count(*) filter (where derived_display_allowed='ALLOWED' and aggregation_allowed='ALLOWED') as dashboard_allowed_policy_count,
         count(*) filter (where derived_display_allowed='UNKNOWN' or aggregation_allowed='UNKNOWN') as unknown_dashboard_rights_count,
         count(*) filter (where derived_display_allowed='PROHIBITED' or aggregation_allowed='PROHIBITED') as prohibited_dashboard_rights_count
  from {{ source('gis_core', 'data_rights_policy') }} group by 1
), scopes as (
  select tenant_id, id as site_id from {{ source('gis_core', 'site') }}
)
select s.tenant_id, s.site_id, coalesce(p.policy_count,0) as policy_count,
       coalesce(p.reviewed_policy_count,0) as reviewed_policy_count,
       coalesce(p.dashboard_allowed_policy_count,0) as dashboard_allowed_policy_count,
       coalesce(p.unknown_dashboard_rights_count,0) as unknown_dashboard_rights_count,
       coalesce(p.prohibited_dashboard_rights_count,0) as prohibited_dashboard_rights_count,
       'REVIEWED_PRODUCT_GOVERNANCE_NOT_LEGAL_APPROVAL' as governance_semantics
from scopes s left join policies p using (tenant_id)
