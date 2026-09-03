select
    source_feed || ':' || stop_id as stop_key,
    source_feed,
    stop_id,
    stop_name,
    stop_lat,
    stop_lon
from {{ ref('stg_stops') }}
