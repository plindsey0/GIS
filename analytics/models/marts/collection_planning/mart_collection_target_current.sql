with ranked as (
  select *, row_number() over (partition by target_id order by evaluated_at desc, decision_id desc) as rn
  from {{ ref('mart_collection_target_history') }}
)
select * from ranked where rn=1
