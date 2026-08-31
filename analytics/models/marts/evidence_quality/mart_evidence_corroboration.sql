select tenant_id, site_id, condition_key, corroboration, source_independence,
       independent_source_count, count(*) as package_count
from {{ ref('mart_evidence_quality_current') }} group by 1, 2, 3, 4, 5, 6

