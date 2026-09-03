select
    cast(source_feed as varchar) as source_feed,
    cast(route_id as varchar) as route_id,
    cast(agency_id as varchar) as agency_id,
    cast(route_short_name as varchar) as route_short_name,
    cast(route_long_name as varchar) as route_long_name,
    try_cast(route_type as integer) as route_type
from {{ source('raw', 'raw_routes') }}
