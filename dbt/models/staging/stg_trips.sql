select
    cast(route_id as varchar) as route_id,
    cast(service_id as varchar) as service_id,
    cast(trip_id as varchar) as trip_id,
    cast(trip_headsign as varchar) as trip_headsign,
    try_cast(direction_id as integer) as direction_id,
    cast(shape_id as varchar) as shape_id
from {{ source('raw', 'raw_trips') }}
