select
    source_feed,
    stop_id,
    count(*) as duplicate_count
from {{ ref('stg_stops') }}
group by 1, 2
having count(*) > 1
