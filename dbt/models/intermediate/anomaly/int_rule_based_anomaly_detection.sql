{{ config(materialized='table') }}

with evaluation_rows as (

    select *
    from {{ ref('int_synthetic_anomaly_evaluation') }}

),

rule_predictions as (

    select
        *,
        case
            when vehicle_timestamp_utc is not null
                and vehicle_timestamp_utc < snapshot_timestamp_utc - interval 30 minutes
                then true
            when evaluation_record_type = 'vehicle_position'
                and (
                    speed > 90
                    or latitude not between 40.3 and 41.0
                    or longitude not between -74.5 and -73.4
                )
                then true
            when evaluation_record_type = 'trip_update'
                then true
            when schedule_match_status = 'unmatched_realtime_trip'
                then true
            when delay_sanity_status in ('extreme_early', 'extreme_late')
                or estimated_delay_minutes > 60
                or estimated_delay_minutes < -15
                then true
            else false
        end as predicted_is_anomaly,
        case
            when vehicle_timestamp_utc is not null
                and vehicle_timestamp_utc < snapshot_timestamp_utc - interval 30 minutes
                then 'stale_vehicle_position_timestamp'
            when evaluation_record_type = 'vehicle_position'
                and (
                    speed > 90
                    or latitude not between 40.3 and 41.0
                    or longitude not between -74.5 and -73.4
                )
                then 'gps_jump_or_implausible_speed'
            when evaluation_record_type = 'trip_update'
                then 'duplicate_trip_update_entity'
            when schedule_match_status = 'unmatched_realtime_trip'
                then 'missing_or_unmatched_schedule_reference'
            when delay_sanity_status in ('extreme_early', 'extreme_late')
                or estimated_delay_minutes > 60
                or estimated_delay_minutes < -15
                then 'late_or_extreme_delay_outlier'
            else 'normal'
        end as predicted_anomaly_type,
        case
            when vehicle_timestamp_utc is not null
                and vehicle_timestamp_utc < snapshot_timestamp_utc - interval 30 minutes
                then 'high'
            when evaluation_record_type = 'vehicle_position'
                and (
                    speed > 90
                    or latitude not between 40.3 and 41.0
                    or longitude not between -74.5 and -73.4
                )
                then 'critical'
            when evaluation_record_type = 'trip_update'
                then 'medium'
            when schedule_match_status = 'unmatched_realtime_trip'
                then 'high'
            when delay_sanity_status in ('extreme_early', 'extreme_late')
                or estimated_delay_minutes > 60
                or estimated_delay_minutes < -15
                then 'critical'
            else 'none'
        end as predicted_severity,
        case
            when vehicle_timestamp_utc is not null
                and vehicle_timestamp_utc < snapshot_timestamp_utc - interval 30 minutes
                then 'rule_stale_vehicle_timestamp'
            when evaluation_record_type = 'vehicle_position'
                and (
                    speed > 90
                    or latitude not between 40.3 and 41.0
                    or longitude not between -74.5 and -73.4
                )
                then 'rule_implausible_gps_or_speed'
            when evaluation_record_type = 'trip_update'
                then 'rule_duplicate_trip_update_candidate'
            when schedule_match_status = 'unmatched_realtime_trip'
                then 'rule_unmatched_schedule_reference'
            when delay_sanity_status in ('extreme_early', 'extreme_late')
                or estimated_delay_minutes > 60
                or estimated_delay_minutes < -15
                then 'rule_extreme_delay'
            else 'rule_no_anomaly_detected'
        end as detector_rule_id,
        case
            when vehicle_timestamp_utc is not null
                and vehicle_timestamp_utc < snapshot_timestamp_utc - interval 30 minutes
                then 'Vehicle timestamp is more than 30 minutes older than the snapshot timestamp.'
            when evaluation_record_type = 'vehicle_position'
                and speed > 90
                then 'Vehicle speed exceeds the 90 mph plausibility threshold.'
            when evaluation_record_type = 'vehicle_position'
                and (
                    latitude not between 40.3 and 41.0
                    or longitude not between -74.5 and -73.4
                )
                then 'Vehicle GPS coordinate falls outside a broad NYC operating envelope.'
            when evaluation_record_type = 'trip_update'
                then 'Trip update row is treated as a duplicate entity candidate in the synthetic evaluation set.'
            when schedule_match_status = 'unmatched_realtime_trip'
                then 'Realtime trip record does not match the aligned static schedule.'
            when delay_sanity_status in ('extreme_early', 'extreme_late')
                or estimated_delay_minutes > 60
                or estimated_delay_minutes < -15
                then 'Schedule-derived delay is outside the plausible delay range.'
            else 'No rule threshold was crossed.'
        end as detection_reason
    from evaluation_rows

)

select
    evaluation_record_id,
    source_model,
    evaluation_record_type,
    snapshot_folder,
    snapshot_timestamp_utc,
    entity_id,
    trip_id,
    route_id,
    vehicle_id,
    latitude,
    longitude,
    speed,
    vehicle_timestamp_utc,
    trip_update_timestamp_utc,
    schedule_match_status,
    estimated_delay_minutes,
    delay_sanity_status,
    delay_band,
    on_time_flag,
    is_synthetic_anomaly,
    synthetic_anomaly_type,
    anomaly_severity,
    anomaly_reason,
    predicted_is_anomaly,
    predicted_anomaly_type,
    predicted_severity,
    detector_rule_id,
    detection_reason
from rule_predictions
