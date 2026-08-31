select * from {{ ref('mart_market_participant_daily') }} where ownership<>'OWNED'
