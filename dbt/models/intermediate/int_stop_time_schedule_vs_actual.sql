{{ config(materialized='table') }}

with stop_level_matches as (

    select
        realtime_stop_updates.snapshot_folder,
        realtime_stop_updates.snapshot_timestamp_utc,
        realtime_stop_updates.entity_id,
        realtime_stop_updates.trip_id,
        realtime_stop_updates.route_id,
        realtime_stop_updates.vehicle_id,
        realtime_stop_updates.stop_id,
        realtime_stop_updates.stop_sequence,
        realtime_stop_updates.arrival_time_utc,
        realtime_stop_updates.arrival_delay_seconds,
        realtime_stop_updates.departure_time_utc,
        realtime_stop_updates.departure_delay_seconds,
        scheduled_stop_times.arrival_seconds_after_midnight,
        scheduled_stop_times.departure_seconds_after_midnight,
        scheduled_stop_times.trip_id is not null as matched_scheduled_stop
    from {{ ref('int_realtime_stop_time_updates') }} as realtime_stop_updates
    left join {{ ref('int_scheduled_stop_times_normalized') }} as scheduled_stop_times
        on realtime_stop_updates.trip_id = scheduled_stop_times.trip_id
        and realtime_stop_updates.stop_sequence = scheduled_stop_times.stop_sequence
        and realtime_stop_updates.stop_id = scheduled_stop_times.stop_id

),

estimated_delays as (

    select
        *,
        case
            when matched_scheduled_stop
                and coalesce(arrival_seconds_after_midnight, departure_seconds_after_midnight) is null
                then true
            else false
        end as schedule_time_parse_failed,
        case
            when arrival_delay_seconds is not null
                then cast(arrival_delay_seconds as double) / 60.0
            when arrival_time_utc is not null
                and arrival_seconds_after_midnight is not null
                then date_diff(
                    'second',
                    date_trunc('day', arrival_time_utc - interval 4 hours)
                        + interval 4 hours
                        + arrival_seconds_after_midnight * interval 1 second,
                    arrival_time_utc
                ) / 60.0
        end as estimated_arrival_delay_minutes,
        case
            when departure_delay_seconds is not null
                then cast(departure_delay_seconds as double) / 60.0
            when departure_time_utc is not null
                and departure_seconds_after_midnight is not null
                then date_diff(
                    'second',
                    date_trunc('day', departure_time_utc - interval 4 hours)
                        + interval 4 hours
                        + departure_seconds_after_midnight * interval 1 second,
                    departure_time_utc
                ) / 60.0
        end as estimated_departure_delay_minutes
    from stop_level_matches

)

select
    snapshot_folder,
    snapshot_timestamp_utc,
    entity_id,
    trip_id,
    route_id,
    vehicle_id,
    stop_id,
    stop_sequence,
    arrival_time_utc,
    departure_time_utc,
    arrival_seconds_after_midnight,
    departure_seconds_after_midnight,
    matched_scheduled_stop,
    schedule_time_parse_failed,
    estimated_arrival_delay_minutes,
    estimated_departure_delay_minutes,
    coalesce(estimated_arrival_delay_minutes, estimated_departure_delay_minutes) as estimated_delay_minutes
from estimated_delays
