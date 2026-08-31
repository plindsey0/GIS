select e.*, c.baseline_start, c.baseline_end, c.measurement_start, c.measurement_end,
 c.comparison_method, c.minimum_evidence
from {{ ref('stg_experiments') }} e join {{ ref('stg_measurement_contracts') }} c using (measurement_contract_id)
