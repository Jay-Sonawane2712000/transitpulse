{{ config(materialized='table') }}

with realtime_trips as (

    select distinct trip_id
    from {{ ref('int_realtime_stop_time_updates') }}

),

scheduled_stop_times as (

    select
        stop_times.trip_id,
        stop_times.stop_id,
        stop_times.stop_sequence,
        stop_times.arrival_time,
        stop_times.departure_time,
        try_cast(split_part(stop_times.arrival_time, ':', 1) as integer) as arrival_hour,
        try_cast(split_part(stop_times.arrival_time, ':', 2) as integer) as arrival_minute,
        try_cast(split_part(stop_times.arrival_time, ':', 3) as integer) as arrival_second,
        try_cast(split_part(stop_times.departure_time, ':', 1) as integer) as departure_hour,
        try_cast(split_part(stop_times.departure_time, ':', 2) as integer) as departure_minute,
        try_cast(split_part(stop_times.departure_time, ':', 3) as integer) as departure_second
    from {{ ref('stg_stop_times') }} as stop_times
    inner join realtime_trips
        on stop_times.trip_id = realtime_trips.trip_id

)

select
    trip_id,
    stop_id,
    stop_sequence,
    arrival_time,
    departure_time,
    case
        when arrival_hour is not null
            and arrival_minute between 0 and 59
            and arrival_second between 0 and 59
            then arrival_hour * 3600 + arrival_minute * 60 + arrival_second
    end as arrival_seconds_after_midnight,
    case
        when departure_hour is not null
            and departure_minute between 0 and 59
            and departure_second between 0 and 59
            then departure_hour * 3600 + departure_minute * 60 + departure_second
    end as departure_seconds_after_midnight
from scheduled_stop_times
