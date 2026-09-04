with trip_snapshot_base as (

    select
        snapshot_folder,
        min(snapshot_timestamp_utc) as snapshot_timestamp_utc,
        trip_id,
        any_value(realtime_route_id) as route_id,
        any_value(vehicle_id) as vehicle_id,
        any_value(trip_headsign) as trip_headsign,
        any_value(direction_id) as direction_id,
        any_value(schedule_match_status) as schedule_match_status
    from {{ ref('int_trip_schedule_vs_actual') }}
    group by 1, 3

),

realtime_stop_updates as (

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
        arrival_delay_seconds,
        departure_time_utc,
        departure_delay_seconds
    from {{ ref('int_realtime_stop_time_updates') }}

),

scheduled_stop_times as (

    select
        trip_id,
        stop_id,
        stop_sequence,
        try_cast(split_part(arrival_time, ':', 1) as integer) * 3600
            + try_cast(split_part(arrival_time, ':', 2) as integer) * 60
            + try_cast(split_part(arrival_time, ':', 3) as integer) as arrival_seconds_after_midnight,
        try_cast(split_part(departure_time, ':', 1) as integer) * 3600
            + try_cast(split_part(departure_time, ':', 2) as integer) * 60
            + try_cast(split_part(departure_time, ':', 3) as integer) as departure_seconds_after_midnight
    from {{ ref('stg_stop_times') }}
    where trip_id in (
        select distinct trip_id
        from realtime_stop_updates
    )

),

stop_level_delays as (

    select
        realtime_stop_updates.snapshot_folder,
        realtime_stop_updates.snapshot_timestamp_utc,
        realtime_stop_updates.trip_id,
        realtime_stop_updates.arrival_time_utc,
        realtime_stop_updates.departure_time_utc,
        realtime_stop_updates.arrival_delay_seconds,
        realtime_stop_updates.departure_delay_seconds,
        coalesce(
            scheduled_by_sequence.arrival_seconds_after_midnight,
            scheduled_by_stop.arrival_seconds_after_midnight
        ) as arrival_seconds_after_midnight,
        coalesce(
            scheduled_by_sequence.departure_seconds_after_midnight,
            scheduled_by_stop.departure_seconds_after_midnight
        ) as departure_seconds_after_midnight,
        scheduled_by_sequence.trip_id is not null
            or scheduled_by_stop.trip_id is not null as matched_scheduled_stop,
        case
            when coalesce(
                scheduled_by_sequence.trip_id,
                scheduled_by_stop.trip_id
            ) is not null
            and coalesce(
                scheduled_by_sequence.arrival_seconds_after_midnight,
                scheduled_by_sequence.departure_seconds_after_midnight,
                scheduled_by_stop.arrival_seconds_after_midnight,
                scheduled_by_stop.departure_seconds_after_midnight
            ) is null
                then true
            else false
        end as schedule_time_parse_failed,
        case
            when realtime_stop_updates.arrival_delay_seconds is not null
                then cast(realtime_stop_updates.arrival_delay_seconds as double) / 60.0
            when realtime_stop_updates.arrival_time_utc is not null
                and coalesce(
                    scheduled_by_sequence.arrival_seconds_after_midnight,
                    scheduled_by_stop.arrival_seconds_after_midnight
                ) is not null
                then date_diff(
                    'second',
                    date_trunc('day', realtime_stop_updates.arrival_time_utc - interval 4 hours)
                        + interval 4 hours
                        + coalesce(
                            scheduled_by_sequence.arrival_seconds_after_midnight,
                            scheduled_by_stop.arrival_seconds_after_midnight
                        ) * interval 1 second,
                    realtime_stop_updates.arrival_time_utc
                ) / 60.0
        end as estimated_arrival_delay_minutes,
        case
            when realtime_stop_updates.departure_delay_seconds is not null
                then cast(realtime_stop_updates.departure_delay_seconds as double) / 60.0
            when realtime_stop_updates.departure_time_utc is not null
                and coalesce(
                    scheduled_by_sequence.departure_seconds_after_midnight,
                    scheduled_by_stop.departure_seconds_after_midnight
                ) is not null
                then date_diff(
                    'second',
                    date_trunc('day', realtime_stop_updates.departure_time_utc - interval 4 hours)
                        + interval 4 hours
                        + coalesce(
                            scheduled_by_sequence.departure_seconds_after_midnight,
                            scheduled_by_stop.departure_seconds_after_midnight
                        ) * interval 1 second,
                    realtime_stop_updates.departure_time_utc
                ) / 60.0
        end as estimated_departure_delay_minutes
    from realtime_stop_updates
    left join scheduled_stop_times as scheduled_by_sequence
        on realtime_stop_updates.trip_id = scheduled_by_sequence.trip_id
        and realtime_stop_updates.stop_sequence = scheduled_by_sequence.stop_sequence
        and (
            realtime_stop_updates.stop_id is null
            or realtime_stop_updates.stop_id = scheduled_by_sequence.stop_id
        )
    left join scheduled_stop_times as scheduled_by_stop
        on realtime_stop_updates.trip_id = scheduled_by_stop.trip_id
        and realtime_stop_updates.stop_sequence is null
        and realtime_stop_updates.stop_id = scheduled_by_stop.stop_id

),

trip_delay_summary as (

    select
        snapshot_folder,
        trip_id,
        count(*) as stop_update_count,
        sum(case when matched_scheduled_stop then 1 else 0 end) as matched_stop_update_count,
        min(coalesce(arrival_time_utc, departure_time_utc)) as first_realtime_stop_time_utc,
        max(coalesce(departure_time_utc, arrival_time_utc)) as last_realtime_stop_time_utc,
        avg(coalesce(estimated_arrival_delay_minutes, estimated_departure_delay_minutes)) as avg_estimated_delay_minutes,
        max(coalesce(estimated_arrival_delay_minutes, estimated_departure_delay_minutes)) as max_estimated_delay_minutes,
        min(coalesce(estimated_arrival_delay_minutes, estimated_departure_delay_minutes)) as min_estimated_delay_minutes,
        sum(
            case
                when coalesce(estimated_arrival_delay_minutes, estimated_departure_delay_minutes) is not null then 1
                else 0
            end
        ) as estimated_delay_stop_count,
        sum(case when schedule_time_parse_failed then 1 else 0 end) as schedule_time_parse_issue_count
    from stop_level_delays
    group by 1, 2

)

select
    trip_snapshot_base.snapshot_folder,
    trip_snapshot_base.snapshot_timestamp_utc,
    trip_snapshot_base.trip_id,
    trip_snapshot_base.route_id,
    trip_snapshot_base.vehicle_id,
    trip_snapshot_base.trip_headsign,
    trip_snapshot_base.direction_id,
    trip_snapshot_base.schedule_match_status,
    coalesce(trip_delay_summary.stop_update_count, 0) as stop_update_count,
    coalesce(trip_delay_summary.matched_stop_update_count, 0) as matched_stop_update_count,
    trip_delay_summary.first_realtime_stop_time_utc,
    trip_delay_summary.last_realtime_stop_time_utc,
    trip_delay_summary.avg_estimated_delay_minutes,
    trip_delay_summary.max_estimated_delay_minutes,
    trip_delay_summary.min_estimated_delay_minutes,
    trip_delay_summary.avg_estimated_delay_minutes as estimated_delay_minutes,
    abs(trip_delay_summary.avg_estimated_delay_minutes) as delay_minutes_abs,
    case
        when trip_delay_summary.avg_estimated_delay_minutes is null then null
        when trip_delay_summary.avg_estimated_delay_minutes between -1 and 5 then true
        else false
    end as on_time_flag,
    case
        when coalesce(trip_delay_summary.estimated_delay_stop_count, 0) > 0 then 'delay_available'
        when coalesce(trip_delay_summary.matched_stop_update_count, 0) = 0 then 'delay_unavailable'
        when coalesce(trip_delay_summary.schedule_time_parse_issue_count, 0) > 0 then 'schedule_time_parse_issue'
        else 'delay_unavailable'
    end as delay_data_status,
    case
        when trip_delay_summary.avg_estimated_delay_minutes is null then 'delay_unavailable'
        when trip_delay_summary.avg_estimated_delay_minutes < -15 then 'extreme_early'
        when trip_delay_summary.avg_estimated_delay_minutes > 60 then 'extreme_late'
        else 'plausible'
    end as delay_sanity_status,
    case
        when trip_delay_summary.avg_estimated_delay_minutes is null then 'unavailable'
        when trip_delay_summary.avg_estimated_delay_minutes < -5 then 'early_more_than_5_min'
        when trip_delay_summary.avg_estimated_delay_minutes >= -5
            and trip_delay_summary.avg_estimated_delay_minutes < -1 then 'early_1_to_5_min'
        when trip_delay_summary.avg_estimated_delay_minutes >= -1
            and trip_delay_summary.avg_estimated_delay_minutes <= 5 then 'on_time'
        when trip_delay_summary.avg_estimated_delay_minutes > 5
            and trip_delay_summary.avg_estimated_delay_minutes <= 15 then 'late_5_to_15_min'
        when trip_delay_summary.avg_estimated_delay_minutes > 15
            and trip_delay_summary.avg_estimated_delay_minutes <= 30 then 'late_15_to_30_min'
        when trip_delay_summary.avg_estimated_delay_minutes > 30
            and trip_delay_summary.avg_estimated_delay_minutes <= 60 then 'late_30_to_60_min'
        when trip_delay_summary.avg_estimated_delay_minutes > 60 then 'late_over_60_min'
    end as delay_band
from trip_snapshot_base
left join trip_delay_summary
    on trip_snapshot_base.snapshot_folder = trip_delay_summary.snapshot_folder
    and trip_snapshot_base.trip_id = trip_delay_summary.trip_id
