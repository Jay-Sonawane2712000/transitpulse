with feed_quality as (

    select
        snapshot_folder,
        snapshot_timestamp_utc,
        vehicle_record_count,
        trip_update_record_count,
        vehicle_record_count + trip_update_record_count as total_realtime_records,
        null_gps_count,
        duplicate_vehicle_entity_count,
        duplicate_trip_update_entity_count,
        unmatched_realtime_trip_count,
        snapshot_gap_minutes,
        freshness_status,
        feed_quality_status
    from {{ ref('int_feed_quality_summary') }}

)

select
    snapshot_folder,
    snapshot_timestamp_utc,
    vehicle_record_count,
    trip_update_record_count,
    total_realtime_records,
    null_gps_count,
    duplicate_vehicle_entity_count,
    duplicate_trip_update_entity_count,
    unmatched_realtime_trip_count,
    snapshot_gap_minutes,
    freshness_status,
    feed_quality_status,
    case
        when vehicle_record_count = 0 then 0.0
        else cast(null_gps_count as double) / cast(vehicle_record_count as double)
    end as null_gps_rate,
    case
        when trip_update_record_count = 0 then 0.0
        else cast(duplicate_trip_update_entity_count as double) / cast(trip_update_record_count as double)
    end as duplicate_trip_update_rate,
    case
        when total_realtime_records = 0 then 0.0
        else cast(unmatched_realtime_trip_count as double) / cast(total_realtime_records as double)
    end as unmatched_realtime_trip_rate,
    case
        when vehicle_record_count > 0 and trip_update_record_count > 0 then 1.0
        else 0.0
    end as feed_completeness_proxy
from feed_quality
