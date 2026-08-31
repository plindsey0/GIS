select tenant_id, site_id, intervention_id, feasibility, measurement_readiness,
 constraints_json, risk_json from {{ ref('stg_interventions') }}
where feasibility <> 'FEASIBLE' or measurement_readiness <> 'READY'
