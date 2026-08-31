select p.tenant_id, p.site_id, c.contract_key, c.contract_version,
       p.sufficiency, count(*) as package_count,
       sum(case when p.conflict_count > 0 then 1 else 0 end) as conflicting_packages,
       sum(case when p.rights_usability <> 'USABLE' then 1 else 0 end) as rights_limited_packages
from {{ ref('stg_evidence_packages') }} p
join {{ ref('stg_evidence_contracts') }} c using (evidence_contract_id)
group by 1, 2, 3, 4, 5
