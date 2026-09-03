select
    cast(snapshot_timestamp_utc as timestamp) as snapshot_timestamp_utc,
    cast(snapshot_folder as varchar) as snapshot_folder,
    cast(entity_id as varchar) as entity_id,
    cast(trip_id as varchar) as trip_id,
    cast(route_id as varchar) as route_id,
    cast(vehicle_id as varchar) as vehicle_id,
    cast(stop_time_updates as varchar) as stop_time_updates,
    to_timestamp(try_cast("timestamp" as bigint)) at time zone 'UTC' as trip_update_timestamp_utc
from {{ source('raw', 'raw_trip_updates') }}
