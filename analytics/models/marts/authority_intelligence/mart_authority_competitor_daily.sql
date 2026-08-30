select tenant_id, site_id, provider, observed_date as date, target_domain, ownership,
       sum(backlink_count) as backlink_count,
       count(distinct referring_domain) as referring_domain_count,
       sum(followed_count) as followed_count, sum(nofollow_count) as nofollow_count
from {{ ref('stg_referring_domain_observations') }}
where ownership in ('OWNED','COMPETITOR')
group by 1,2,3,4,5,6
