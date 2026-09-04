with trip_updates as (

    select
        schedule.snapshot_folder,
        schedule.snapshot_timestamp_utc,
        schedule.trip_id,
        schedule.realtime_route_id as route_id,
        schedule.vehicle_id,
        schedule.trip_headsign,
        schedule.direction_id,
        schedule.schedule_match_status,
        updates.stop_time_updates
    from {{ ref('int_trip_schedule_vs_actual') }} as schedule
    left join {{ ref('stg_trip_updates') }} as updates
        on schedule.snapshot_folder = updates.snapshot_folder
        and schedule.entity_id = updates.entity_id

),

realtime_stop_updates as (

    select
        trip_updates.snapshot_folder,
        trip_updates.snapshot_timestamp_utc,
        trip_updates.trip_id,
        trip_updates.route_id,
        trip_updates.vehicle_id,
        trip_updates.trip_headsign,
        trip_updates.direction_id,
        trip_updates.schedule_match_status,
        try_cast(json_extract(json_update.value, '$.arrival_time') as bigint) as arrival_epoch,
        try_cast(json_extract(json_update.value, '$.departure_time') as bigint) as departure_epoch,
        try_cast(json_extract(json_update.value, '$.arrival_delay') as double) / 60.0 as arrival_delay_minutes,
        try_cast(json_extract(json_update.value, '$.departure_delay') as double) / 60.0 as departure_delay_minutes
    from trip_updates,
        json_each(trip_updates.stop_time_updates) as json_update
    where trip_updates.stop_time_updates is not null

),

trip_level as (

    select
        snapshot_folder,
        min(snapshot_timestamp_utc) as snapshot_timestamp_utc,
        trip_id,
        any_value(route_id) as route_id,
        any_value(vehicle_id) as vehicle_id,
        any_value(trip_headsign) as trip_headsign,
        any_value(direction_id) as direction_id,
        any_value(schedule_match_status) as schedule_match_status,
        count(*) as stop_update_count,
        to_timestamp(min(coalesce(arrival_epoch, departure_epoch))) at time zone 'UTC' as first_realtime_stop_time_utc,
        to_timestamp(max(coalesce(departure_epoch, arrival_epoch))) at time zone 'UTC' as last_realtime_stop_time_utc,
        max(arrival_delay_minutes) as max_arrival_delay_minutes,
        max(departure_delay_minutes) as max_departure_delay_minutes,
        max(coalesce(arrival_delay_minutes, departure_delay_minutes)) as estimated_delay_minutes,
        case
            when count(coalesce(arrival_delay_minutes, departure_delay_minutes)) > 0 then 'delay_available'
            when count(coalesce(arrival_epoch, departure_epoch)) > 0 then 'delay_unavailable'
            else 'schedule_time_parse_issue'
        end as delay_data_status
    from realtime_stop_updates
    group by 1, 3

)

select
    snapshot_folder,
    snapshot_timestamp_utc,
    trip_id,
    route_id,
    vehicle_id,
    trip_headsign,
    direction_id,
    schedule_match_status,
    stop_update_count,
    first_realtime_stop_time_utc,
    last_realtime_stop_time_utc,
    max_arrival_delay_minutes,
    max_departure_delay_minutes,
    estimated_delay_minutes,
    case
        when estimated_delay_minutes is null then null
        when estimated_delay_minutes between -1 and 5 then true
        else false
    end as on_time_flag,
    delay_data_status
from trip_level
