select
    cast(snapshot_timestamp_utc as timestamp) as snapshot_timestamp_utc,
    cast(snapshot_folder as varchar) as snapshot_folder,
    cast(entity_id as varchar) as entity_id,
    cast(vehicle_id as varchar) as vehicle_id,
    cast(trip_id as varchar) as trip_id,
    cast(route_id as varchar) as route_id,
    try_cast(latitude as double) as latitude,
    try_cast(longitude as double) as longitude,
    try_cast(bearing as double) as bearing,
    try_cast(speed as double) as speed,
    try_cast(current_stop_sequence as integer) as current_stop_sequence,
    cast(current_status as varchar) as current_status,
    to_timestamp(try_cast("timestamp" as bigint)) at time zone 'UTC' as vehicle_timestamp_utc
from {{ source('raw', 'raw_vehicle_positions') }}
