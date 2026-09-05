with vehicle_positions as (

    select
        snapshot_folder,
        snapshot_timestamp_utc,
        route_id,
        entity_id,
        vehicle_id,
        vehicle_timestamp_utc
    from {{ ref('stg_vehicle_positions') }}
    where route_id is not null

),

route_snapshot_counts as (

    select
        snapshot_folder,
        min(snapshot_timestamp_utc) as snapshot_timestamp_utc,
        route_id,
        count(*) as vehicle_count,
        count(distinct vehicle_id) as distinct_vehicle_count,
        count(vehicle_timestamp_utc) as observed_vehicle_sequence_count
    from vehicle_positions
    group by 1, 3

),

sequenced_vehicles as (

    select
        snapshot_folder,
        route_id,
        vehicle_timestamp_utc,
        lag(vehicle_timestamp_utc) over (
            partition by snapshot_folder, route_id
            order by vehicle_timestamp_utc, vehicle_id, entity_id
        ) as previous_vehicle_timestamp_utc
    from vehicle_positions
    where vehicle_timestamp_utc is not null

),

vehicle_spacing as (

    select
        snapshot_folder,
        route_id,
        date_diff(
            'second',
            previous_vehicle_timestamp_utc,
            vehicle_timestamp_utc
        ) / 60.0 as vehicle_spacing_minutes
    from sequenced_vehicles
    where previous_vehicle_timestamp_utc is not null

),

route_snapshot_spacing as (

    select
        snapshot_folder,
        route_id,
        avg(vehicle_spacing_minutes) as avg_vehicle_spacing_minutes,
        min(vehicle_spacing_minutes) as min_vehicle_spacing_minutes,
        max(vehicle_spacing_minutes) as max_vehicle_spacing_minutes,
        coalesce(stddev_samp(vehicle_spacing_minutes), 0.0) as headway_variance_minutes
    from vehicle_spacing
    group by 1, 2

)

select
    route_snapshot_counts.snapshot_folder,
    route_snapshot_counts.snapshot_timestamp_utc,
    route_snapshot_counts.route_id,
    route_snapshot_counts.vehicle_count,
    route_snapshot_counts.distinct_vehicle_count,
    route_snapshot_counts.observed_vehicle_sequence_count,
    case
        when route_snapshot_counts.distinct_vehicle_count < 2 then null
        else route_snapshot_spacing.avg_vehicle_spacing_minutes
    end as avg_vehicle_spacing_minutes,
    case
        when route_snapshot_counts.distinct_vehicle_count < 2 then null
        else route_snapshot_spacing.min_vehicle_spacing_minutes
    end as min_vehicle_spacing_minutes,
    case
        when route_snapshot_counts.distinct_vehicle_count < 2 then null
        else route_snapshot_spacing.max_vehicle_spacing_minutes
    end as max_vehicle_spacing_minutes,
    case
        when route_snapshot_counts.distinct_vehicle_count < 2 then null
        else route_snapshot_spacing.headway_variance_minutes
    end as headway_variance_minutes,
    case
        when route_snapshot_counts.distinct_vehicle_count < 2 then 'insufficient_data'
        when route_snapshot_spacing.headway_variance_minutes <= 5 then 'stable'
        when route_snapshot_spacing.headway_variance_minutes > 5
            and route_snapshot_spacing.headway_variance_minutes <= 15 then 'variable'
        when route_snapshot_spacing.headway_variance_minutes > 15 then 'highly_variable'
        else 'insufficient_data'
    end as headway_reliability_status
from route_snapshot_counts
left join route_snapshot_spacing
    on route_snapshot_counts.snapshot_folder = route_snapshot_spacing.snapshot_folder
    and route_snapshot_counts.route_id = route_snapshot_spacing.route_id
