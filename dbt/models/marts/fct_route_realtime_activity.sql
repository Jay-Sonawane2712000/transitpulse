with vehicle_activity as (

    select
        snapshot_folder,
        min(snapshot_timestamp_utc) as snapshot_timestamp_utc,
        route_id,
        count(*) as vehicle_position_count,
        count(distinct vehicle_id) as distinct_vehicle_count,
        count(distinct trip_id) as vehicle_distinct_trip_count
    from {{ ref('stg_vehicle_positions') }}
    where route_id is not null
    group by 1, 3

),

trip_update_activity as (

    select
        snapshot_folder,
        min(snapshot_timestamp_utc) as snapshot_timestamp_utc,
        route_id,
        count(*) as trip_update_count,
        count(distinct trip_id) as trip_update_distinct_trip_count
    from {{ ref('stg_trip_updates') }}
    where route_id is not null
    group by 1, 3

),

route_snapshots as (

    select
        snapshot_folder,
        snapshot_timestamp_utc,
        route_id
    from vehicle_activity

    union

    select
        snapshot_folder,
        snapshot_timestamp_utc,
        route_id
    from trip_update_activity

),

combined as (

    select
        route_snapshots.snapshot_folder,
        route_snapshots.snapshot_timestamp_utc,
        route_snapshots.route_id,
        coalesce(vehicle_activity.vehicle_position_count, 0) as vehicle_position_count,
        coalesce(trip_update_activity.trip_update_count, 0) as trip_update_count,
        coalesce(vehicle_activity.distinct_vehicle_count, 0) as distinct_vehicle_count,
        greatest(
            coalesce(vehicle_activity.vehicle_distinct_trip_count, 0),
            coalesce(trip_update_activity.trip_update_distinct_trip_count, 0)
        ) as distinct_trip_count
    from route_snapshots
    left join vehicle_activity
        on route_snapshots.snapshot_folder = vehicle_activity.snapshot_folder
        and route_snapshots.route_id = vehicle_activity.route_id
    left join trip_update_activity
        on route_snapshots.snapshot_folder = trip_update_activity.snapshot_folder
        and route_snapshots.route_id = trip_update_activity.route_id

)

select
    snapshot_folder,
    snapshot_timestamp_utc,
    route_id,
    vehicle_position_count,
    trip_update_count,
    distinct_vehicle_count,
    distinct_trip_count,
    vehicle_position_count > 0 as has_vehicle_positions,
    trip_update_count > 0 as has_trip_updates,
    vehicle_position_count + trip_update_count as total_realtime_records,
    case
        when trip_update_count = 0 then 0.0
        else cast(vehicle_position_count as double) / cast(trip_update_count as double)
    end as vehicle_to_trip_update_ratio,
    case
        when vehicle_position_count > 0 and trip_update_count > 0 then 'active_with_both_feeds'
        when vehicle_position_count > 0 and trip_update_count = 0 then 'active_vehicle_only'
        when vehicle_position_count = 0 and trip_update_count > 0 then 'active_trip_updates_only'
        else 'inactive_or_missing'
    end as route_activity_status
from combined
