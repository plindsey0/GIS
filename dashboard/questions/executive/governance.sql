select policy_count, reviewed_policy_count, dashboard_allowed_policy_count,
       unknown_dashboard_rights_count, prohibited_dashboard_rights_count, governance_semantics
from gis_analytics.mart_executive_governance
where 1=1 [[and tenant_id::text={{tenant_id}}]] [[and site_id::text={{site_id}}]]
[[and current_date >= {{start_date}}]] [[and current_date <= {{end_date}}]]
