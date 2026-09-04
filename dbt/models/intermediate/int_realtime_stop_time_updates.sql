select
    trip_updates.snapshot_folder,
    trip_updates.snapshot_timestamp_utc,
    trip_updates.entity_id,
    trip_updates.trip_id,
    trip_updates.route_id,
    trip_updates.vehicle_id,
    json_extract_string(stop_update.value, '$.stop_id') as stop_id,
    try_cast(json_extract(stop_update.value, '$.stop_sequence') as integer) as stop_sequence,
    to_timestamp(try_cast(json_extract(stop_update.value, '$.arrival_time') as bigint)) at time zone 'UTC'
        as arrival_time_utc,
    try_cast(json_extract(stop_update.value, '$.arrival_delay') as integer) as arrival_delay_seconds,
    to_timestamp(try_cast(json_extract(stop_update.value, '$.departure_time') as bigint)) at time zone 'UTC'
        as departure_time_utc,
    try_cast(json_extract(stop_update.value, '$.departure_delay') as integer) as departure_delay_seconds,
    try_cast(json_extract(stop_update.value, '$.arrival_time') as bigint) is not null
        as stop_update_has_arrival_time,
    try_cast(json_extract(stop_update.value, '$.departure_time') as bigint) is not null
        as stop_update_has_departure_time,
    try_cast(json_extract(stop_update.value, '$.arrival_delay') as integer) is not null
        as stop_update_has_arrival_delay,
    try_cast(json_extract(stop_update.value, '$.departure_delay') as integer) is not null
        as stop_update_has_departure_delay
from {{ ref('stg_trip_updates') }} as trip_updates,
    json_each(trip_updates.stop_time_updates) as stop_update
where trip_updates.stop_time_updates is not null
