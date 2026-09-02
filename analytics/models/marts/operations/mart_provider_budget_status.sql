with month_usage as (
  select tenant_id, site_id, provider_id, currency, sum(governed_cost) as month_spend
  from {{ ref('mart_provider_usage_daily') }}
  where usage_date >= date_trunc('month', current_date)::date
  group by 1,2,3,4
)
select
  policy.tenant_id,
  policy.site_id,
  provider.provider_key,
  policy.status,
  policy.master_enabled,
  policy.currency,
  coalesce(usage.month_spend, 0) as month_spend,
  policy.monthly_soft_budget,
  policy.monthly_hard_budget,
  case
    when provider.is_commercial and policy.monthly_hard_budget is null then 'BLOCKED_NO_BUDGET'
    when policy.monthly_hard_budget is not null and coalesce(usage.month_spend, 0) >= policy.monthly_hard_budget then 'HARD_LIMIT_REACHED'
    when policy.monthly_soft_budget is not null and coalesce(usage.month_spend, 0) >= policy.monthly_soft_budget then 'SOFT_LIMIT_REACHED'
    else 'WITHIN_LIMIT'
  end as budget_state
from {{ source('gis_core', 'provider_collection_policy') }} policy
join {{ source('gis_core', 'provider_definition') }} provider on provider.id = policy.provider_id
left join month_usage usage using (tenant_id, site_id, provider_id, currency)
