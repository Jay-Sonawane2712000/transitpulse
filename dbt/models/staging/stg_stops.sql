select
    cast(source_feed as varchar) as source_feed,
    cast(stop_id as varchar) as stop_id,
    cast(stop_name as varchar) as stop_name,
    try_cast(stop_lat as double) as stop_lat,
    try_cast(stop_lon as double) as stop_lon
from {{ source('raw', 'raw_stops') }}
