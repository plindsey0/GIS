select p.tenant_id, p.site_id, i.evidence_package_id, i.root_source_key,
       i.independence, count(*) as evidence_item_count
from {{ ref('stg_evidence_package_items') }} i
join {{ ref('stg_evidence_packages') }} p using (evidence_package_id)
group by 1, 2, 3, 4, 5

