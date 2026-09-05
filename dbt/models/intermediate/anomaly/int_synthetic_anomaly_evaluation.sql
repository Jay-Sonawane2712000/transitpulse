{{ config(materialized='table') }}

with normal_trip_performance as (

    select
        'normal_trip_performance_' || row_number() over (
            order by snapshot_folder, route_id, trip_id
        ) as evaluation_record_id,
        'fct_on_time_performance' as source_model,
        'trip_performance' as evaluation_record_type,
        snapshot_folder,
        snapshot_timestamp_utc,
        cast(null as varchar) as entity_id,
        trip_id,
        route_id,
        vehicle_id,
        cast(null as double) as latitude,
        cast(null as double) as longitude,
        cast(null as double) as speed,
        cast(null as timestamp) as vehicle_timestamp_utc,
        cast(null as timestamp) as trip_update_timestamp_utc,
        schedule_match_status,
        estimated_delay_minutes,
        delay_sanity_status,
        delay_band,
        on_time_flag,
        false as is_synthetic_anomaly,
        'normal' as synthetic_anomaly_type,
        'none' as anomaly_severity,
        'Baseline normal trip performance record sampled from plausible schedule-derived delay rows.' as anomaly_reason
    from {{ ref('fct_on_time_performance') }}
    where delay_sanity_status = 'plausible'
    qualify row_number() over (
        order by snapshot_folder, route_id, trip_id
    ) <= 250

),

stale_vehicle_position_timestamp as (

    select
        'synthetic_stale_vehicle_position_timestamp_' || row_number() over (
            order by snapshot_folder, route_id, vehicle_id, entity_id
        ) as evaluation_record_id,
        'stg_vehicle_positions' as source_model,
        'vehicle_position' as evaluation_record_type,
        snapshot_folder,
        snapshot_timestamp_utc,
        entity_id,
        trip_id,
        route_id,
        vehicle_id,
        latitude,
        longitude,
        speed,
        vehicle_timestamp_utc - interval 2 hours as vehicle_timestamp_utc,
        cast(null as timestamp) as trip_update_timestamp_utc,
        cast(null as varchar) as schedule_match_status,
        cast(null as double) as estimated_delay_minutes,
        'delay_unavailable' as delay_sanity_status,
        'unavailable' as delay_band,
        cast(null as boolean) as on_time_flag,
        true as is_synthetic_anomaly,
        'stale_vehicle_position_timestamp' as synthetic_anomaly_type,
        'high' as anomaly_severity,
        'Vehicle position timestamp was shifted two hours earlier than the snapshot timestamp.' as anomaly_reason
    from {{ ref('stg_vehicle_positions') }}
    where vehicle_timestamp_utc is not null
    qualify row_number() over (
        order by snapshot_folder, route_id, vehicle_id, entity_id
    ) <= 25

),

gps_jump_or_implausible_speed as (

    select
        'synthetic_gps_jump_or_implausible_speed_' || row_number() over (
            order by snapshot_folder, route_id, vehicle_id, entity_id
        ) as evaluation_record_id,
        'stg_vehicle_positions' as source_model,
        'vehicle_position' as evaluation_record_type,
        snapshot_folder,
        snapshot_timestamp_utc,
        entity_id,
        trip_id,
        route_id,
        vehicle_id,
        latitude + 1.0 as latitude,
        longitude - 1.0 as longitude,
        250.0 as speed,
        vehicle_timestamp_utc,
        cast(null as timestamp) as trip_update_timestamp_utc,
        cast(null as varchar) as schedule_match_status,
        cast(null as double) as estimated_delay_minutes,
        'delay_unavailable' as delay_sanity_status,
        'unavailable' as delay_band,
        cast(null as boolean) as on_time_flag,
        true as is_synthetic_anomaly,
        'gps_jump_or_implausible_speed' as synthetic_anomaly_type,
        'critical' as anomaly_severity,
        'Vehicle position was shifted by roughly one degree and speed was set to an implausible 250 mph-equivalent value.' as anomaly_reason
    from {{ ref('stg_vehicle_positions') }}
    where latitude is not null
        and longitude is not null
    qualify row_number() over (
        order by snapshot_folder, route_id, vehicle_id, entity_id
    ) <= 25

),

duplicate_trip_update_entity as (

    select
        'synthetic_duplicate_trip_update_entity_' || row_number() over (
            order by snapshot_folder, route_id, trip_id, entity_id
        ) as evaluation_record_id,
        'stg_trip_updates' as source_model,
        'trip_update' as evaluation_record_type,
        snapshot_folder,
        snapshot_timestamp_utc,
        entity_id,
        trip_id,
        route_id,
        vehicle_id,
        cast(null as double) as latitude,
        cast(null as double) as longitude,
        cast(null as double) as speed,
        cast(null as timestamp) as vehicle_timestamp_utc,
        trip_update_timestamp_utc,
        'matched_to_static_schedule' as schedule_match_status,
        cast(null as double) as estimated_delay_minutes,
        'delay_unavailable' as delay_sanity_status,
        'unavailable' as delay_band,
        cast(null as boolean) as on_time_flag,
        true as is_synthetic_anomaly,
        'duplicate_trip_update_entity' as synthetic_anomaly_type,
        'medium' as anomaly_severity,
        'Trip update entity is intentionally labeled as a duplicate candidate within its snapshot for detector evaluation.' as anomaly_reason
    from {{ ref('stg_trip_updates') }}
    qualify row_number() over (
        order by snapshot_folder, route_id, trip_id, entity_id
    ) <= 25

),

missing_or_unmatched_schedule_reference as (

    select
        'synthetic_missing_or_unmatched_schedule_reference_' || row_number() over (
            order by snapshot_folder, realtime_route_id, trip_id, entity_id
        ) as evaluation_record_id,
        'int_trip_schedule_vs_actual' as source_model,
        'trip_schedule_alignment' as evaluation_record_type,
        snapshot_folder,
        snapshot_timestamp_utc,
        entity_id,
        trip_id || '_SYNTH_UNMATCHED' as trip_id,
        realtime_route_id as route_id,
        vehicle_id,
        cast(null as double) as latitude,
        cast(null as double) as longitude,
        cast(null as double) as speed,
        cast(null as timestamp) as vehicle_timestamp_utc,
        trip_update_timestamp_utc,
        'unmatched_realtime_trip' as schedule_match_status,
        cast(null as double) as estimated_delay_minutes,
        'delay_unavailable' as delay_sanity_status,
        'unavailable' as delay_band,
        cast(null as boolean) as on_time_flag,
        true as is_synthetic_anomaly,
        'missing_or_unmatched_schedule_reference' as synthetic_anomaly_type,
        'high' as anomaly_severity,
        'Realtime trip_id was modified so it no longer resolves to the static GTFS schedule reference.' as anomaly_reason
    from {{ ref('int_trip_schedule_vs_actual') }}
    qualify row_number() over (
        order by snapshot_folder, realtime_route_id, trip_id, entity_id
    ) <= 25

),

late_or_extreme_delay_outlier as (

    select
        'synthetic_late_or_extreme_delay_outlier_' || row_number() over (
            order by snapshot_folder, route_id, trip_id
        ) as evaluation_record_id,
        'fct_on_time_performance' as source_model,
        'trip_performance' as evaluation_record_type,
        snapshot_folder,
        snapshot_timestamp_utc,
        cast(null as varchar) as entity_id,
        trip_id,
        route_id,
        vehicle_id,
        cast(null as double) as latitude,
        cast(null as double) as longitude,
        cast(null as double) as speed,
        cast(null as timestamp) as vehicle_timestamp_utc,
        cast(null as timestamp) as trip_update_timestamp_utc,
        schedule_match_status,
        estimated_delay_minutes + 90.0 as estimated_delay_minutes,
        'extreme_late' as delay_sanity_status,
        'late_over_60_min' as delay_band,
        false as on_time_flag,
        true as is_synthetic_anomaly,
        'late_or_extreme_delay_outlier' as synthetic_anomaly_type,
        'critical' as anomaly_severity,
        'Estimated delay was increased by 90 minutes to create an extreme late schedule-derived delay outlier.' as anomaly_reason
    from {{ ref('fct_on_time_performance') }}
    where estimated_delay_minutes is not null
        and delay_sanity_status = 'plausible'
    qualify row_number() over (
        order by snapshot_folder, route_id, trip_id
    ) <= 25

)

select *
from normal_trip_performance

union all

select *
from stale_vehicle_position_timestamp

union all

select *
from gps_jump_or_implausible_speed

union all

select *
from duplicate_trip_update_entity

union all

select *
from missing_or_unmatched_schedule_reference

union all

select *
from late_or_extreme_delay_outlier
