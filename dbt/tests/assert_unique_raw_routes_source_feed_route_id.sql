select
    source_feed,
    route_id,
    count(*) as duplicate_count
from {{ source('raw', 'raw_routes') }}
group by 1, 2
having count(*) > 1
