with vehicle_counts as (

    select
        snapshot_folder,
        min(snapshot_timestamp_utc) as snapshot_timestamp_utc,
        count(*) as vehicle_record_count
    from {{ ref('stg_vehicle_positions') }}
    group by snapshot_folder

),

trip_update_counts as (

    select
        snapshot_folder,
        min(snapshot_timestamp_utc) as snapshot_timestamp_utc,
        count(*) as trip_update_record_count
    from {{ ref('stg_trip_updates') }}
    group by snapshot_folder

),

snapshots as (

    select
        snapshot_folder,
        snapshot_timestamp_utc
    from vehicle_counts

    union

    select
        snapshot_folder,
        snapshot_timestamp_utc
    from trip_update_counts

),

null_gps_counts as (

    select
        snapshot_folder,
        count(*) as null_gps_count
    from {{ ref('int_quality_null_gps') }}
    group by snapshot_folder

),

duplicate_vehicle_counts as (

    select
        snapshot_folder,
        count(*) as duplicate_vehicle_entity_count
    from {{ ref('int_quality_duplicate_vehicle_entities') }}
    group by snapshot_folder

),

duplicate_trip_update_counts as (

    select
        snapshot_folder,
        count(*) as duplicate_trip_update_entity_count
    from {{ ref('int_quality_duplicate_trip_update_entities') }}
    group by snapshot_folder

),

unmatched_trip_counts as (

    select
        snapshot_folder,
        count(*) as unmatched_realtime_trip_count
    from {{ ref('int_quality_realtime_trip_referential_integrity') }}
    group by snapshot_folder

),

freshness as (

    select
        snapshot_folder,
        gap_minutes as snapshot_gap_minutes,
        case
            when freshness_status = 'gap_exceeds_threshold' then 'late'
            else freshness_status
        end as freshness_status
    from {{ ref('int_quality_snapshot_freshness') }}

)

select
    snapshots.snapshot_folder,
    snapshots.snapshot_timestamp_utc,
    coalesce(vehicle_counts.vehicle_record_count, 0) as vehicle_record_count,
    coalesce(trip_update_counts.trip_update_record_count, 0) as trip_update_record_count,
    coalesce(null_gps_counts.null_gps_count, 0) as null_gps_count,
    coalesce(duplicate_vehicle_counts.duplicate_vehicle_entity_count, 0) as duplicate_vehicle_entity_count,
    coalesce(duplicate_trip_update_counts.duplicate_trip_update_entity_count, 0) as duplicate_trip_update_entity_count,
    coalesce(unmatched_trip_counts.unmatched_realtime_trip_count, 0) as unmatched_realtime_trip_count,
    freshness.snapshot_gap_minutes,
    freshness.freshness_status,
    case
        when coalesce(vehicle_counts.vehicle_record_count, 0) = 0
            or coalesce(trip_update_counts.trip_update_record_count, 0) = 0
            then 'critical'
        when coalesce(null_gps_counts.null_gps_count, 0) > 0
            or coalesce(duplicate_vehicle_counts.duplicate_vehicle_entity_count, 0) > 0
            or coalesce(duplicate_trip_update_counts.duplicate_trip_update_entity_count, 0) > 0
            or coalesce(unmatched_trip_counts.unmatched_realtime_trip_count, 0) > 0
            or freshness.freshness_status = 'late'
            then 'warning'
        else 'healthy'
    end as feed_quality_status
from snapshots
left join vehicle_counts
    on snapshots.snapshot_folder = vehicle_counts.snapshot_folder
left join trip_update_counts
    on snapshots.snapshot_folder = trip_update_counts.snapshot_folder
left join null_gps_counts
    on snapshots.snapshot_folder = null_gps_counts.snapshot_folder
left join duplicate_vehicle_counts
    on snapshots.snapshot_folder = duplicate_vehicle_counts.snapshot_folder
left join duplicate_trip_update_counts
    on snapshots.snapshot_folder = duplicate_trip_update_counts.snapshot_folder
left join unmatched_trip_counts
    on snapshots.snapshot_folder = unmatched_trip_counts.snapshot_folder
left join freshness
    on snapshots.snapshot_folder = freshness.snapshot_folder
