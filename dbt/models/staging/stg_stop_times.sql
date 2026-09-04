select
    cast(source_feed as varchar) as source_feed,
    cast(trip_id as varchar) as trip_id,
    cast(arrival_time as varchar) as arrival_time,
    cast(departure_time as varchar) as departure_time,
    cast(stop_id as varchar) as stop_id,
    try_cast(stop_sequence as integer) as stop_sequence,
    try_cast(pickup_type as integer) as pickup_type,
    try_cast(drop_off_type as integer) as drop_off_type,
    try_cast(timepoint as integer) as timepoint
from {{ source('raw', 'raw_stop_times') }}
