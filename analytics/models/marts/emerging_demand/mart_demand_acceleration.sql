select * from {{ ref('mart_demand_query_trend') }} where signal_type = 'ACCELERATING'

