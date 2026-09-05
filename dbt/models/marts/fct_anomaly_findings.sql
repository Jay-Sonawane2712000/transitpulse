{{ config(materialized='table') }}

with stale_vehicle_timestamps as (

    select
        md5('rule_stale_vehicle_timestamp|' || snapshot_folder || '|' || entity_id) as anomaly_id,
        'vehicle_entity' as anomaly_grain,
        snapshot_folder,
        snapshot_timestamp_utc,
        route_id,
        trip_id,
        entity_id,
        vehicle_id,
        'stale_realtime_timestamp' as anomaly_type,
        'high' as anomaly_severity,
        0.85 as anomaly_score,
        'Vehicle position timestamp is more than 30 minutes older than the snapshot timestamp.' as anomaly_reason,
        'rule_stale_vehicle_timestamp' as detector_rule_id,
        'stg_vehicle_positions' as source_model
    from {{ ref('stg_vehicle_positions') }}
    where vehicle_timestamp_utc is not null
        and vehicle_timestamp_utc < snapshot_timestamp_utc - interval 30 minutes

),

duplicate_trip_update_entities as (

    select
        md5('rule_duplicate_trip_update_entity|' || snapshot_folder || '|' || entity_id) as anomaly_id,
        'trip_update_entity' as anomaly_grain,
        snapshot_folder,
        first_snapshot_timestamp_utc as snapshot_timestamp_utc,
        cast(null as varchar) as route_id,
        cast(null as varchar) as trip_id,
        entity_id,
        cast(null as varchar) as vehicle_id,
        'duplicate_trip_update_entity' as anomaly_type,
        'medium' as anomaly_severity,
        least(1.0, 0.60 + 0.05 * cast(duplicate_record_count - 2 as double)) as anomaly_score,
        'Trip update entity appears more than once within the same captured snapshot.' as anomaly_reason,
        'rule_duplicate_trip_update_entity' as detector_rule_id,
        'int_quality_duplicate_trip_update_entities' as source_model
    from {{ ref('int_quality_duplicate_trip_update_entities') }}

),

unmatched_schedule_references as (

    select
        md5(
            'rule_unmatched_schedule_reference|'
            || snapshot_folder || '|'
            || realtime_source || '|'
            || trip_id
        ) as anomaly_id,
        'trip_schedule_reference' as anomaly_grain,
        snapshot_folder,
        cast(null as timestamp) as snapshot_timestamp_utc,
        cast(null as varchar) as route_id,
        trip_id,
        cast(null as varchar) as entity_id,
        cast(null as varchar) as vehicle_id,
        'unmatched_schedule_reference' as anomaly_type,
        'high' as anomaly_severity,
        0.90 as anomaly_score,
        'Realtime trip_id does not match the aligned static GTFS trips table.' as anomaly_reason,
        'rule_unmatched_schedule_reference' as detector_rule_id,
        'int_quality_realtime_trip_referential_integrity' as source_model
    from {{ ref('int_quality_realtime_trip_referential_integrity') }}

),

missing_gps_coordinates as (

    select
        md5('rule_missing_gps_coordinate|' || snapshot_folder || '|' || entity_id) as anomaly_id,
        'vehicle_entity' as anomaly_grain,
        snapshot_folder,
        snapshot_timestamp_utc,
        route_id,
        trip_id,
        entity_id,
        vehicle_id,
        'missing_or_invalid_gps_coordinate' as anomaly_type,
        'medium' as anomaly_severity,
        0.70 as anomaly_score,
        'Vehicle position is missing latitude or longitude.' as anomaly_reason,
        'rule_missing_gps_coordinate' as detector_rule_id,
        'int_quality_null_gps' as source_model
    from {{ ref('int_quality_null_gps') }}

),

implausible_gps_or_speed as (

    select
        md5('rule_implausible_gps_or_speed|' || snapshot_folder || '|' || entity_id) as anomaly_id,
        'vehicle_entity' as anomaly_grain,
        snapshot_folder,
        snapshot_timestamp_utc,
        route_id,
        trip_id,
        entity_id,
        vehicle_id,
        'implausible_gps_or_speed' as anomaly_type,
        'critical' as anomaly_severity,
        0.95 as anomaly_score,
        case
            when speed > 90 then 'Vehicle speed exceeds the 90 mph plausibility threshold.'
            else 'Vehicle GPS coordinate falls outside a broad NYC operating envelope.'
        end as anomaly_reason,
        'rule_implausible_gps_or_speed' as detector_rule_id,
        'stg_vehicle_positions' as source_model
    from {{ ref('stg_vehicle_positions') }}
    where speed > 90
        or latitude not between 40.3 and 41.0
        or longitude not between -74.5 and -73.4

),

extreme_delay_outliers as (

    select
        md5('rule_extreme_delay|' || snapshot_folder || '|' || trip_id) as anomaly_id,
        'trip_snapshot' as anomaly_grain,
        snapshot_folder,
        snapshot_timestamp_utc,
        route_id,
        trip_id,
        cast(null as varchar) as entity_id,
        vehicle_id,
        'extreme_delay_outlier' as anomaly_type,
        'critical' as anomaly_severity,
        case
            when delay_minutes_abs >= 90 then 1.0
            else 0.90
        end as anomaly_score,
        'Trip has an extreme schedule-derived delay outside the plausible delay range.' as anomaly_reason,
        'rule_extreme_delay' as detector_rule_id,
        'fct_on_time_performance' as source_model
    from {{ ref('fct_on_time_performance') }}
    where delay_sanity_status in ('extreme_early', 'extreme_late')

),

feed_quality_warnings as (

    select
        md5('rule_feed_quality_warning|' || snapshot_folder) as anomaly_id,
        'snapshot' as anomaly_grain,
        snapshot_folder,
        snapshot_timestamp_utc,
        cast(null as varchar) as route_id,
        cast(null as varchar) as trip_id,
        cast(null as varchar) as entity_id,
        cast(null as varchar) as vehicle_id,
        'feed_quality_warning' as anomaly_type,
        case
            when feed_quality_status = 'critical' then 'critical'
            else 'medium'
        end as anomaly_severity,
        case
            when feed_quality_status = 'critical' then 1.0
            else 0.65
        end as anomaly_score,
        'Snapshot feed quality status is warning or critical based on completeness, duplicate, GPS, schedule match, or freshness checks.' as anomaly_reason,
        'rule_feed_quality_warning' as detector_rule_id,
        'fct_feed_quality' as source_model
    from {{ ref('fct_feed_quality') }}
    where feed_quality_status in ('warning', 'critical')

),

feed_freshness_issues as (

    select
        md5('rule_feed_freshness|' || snapshot_folder) as anomaly_id,
        'snapshot' as anomaly_grain,
        snapshot_folder,
        snapshot_timestamp_utc,
        cast(null as varchar) as route_id,
        cast(null as varchar) as trip_id,
        cast(null as varchar) as entity_id,
        cast(null as varchar) as vehicle_id,
        'feed_freshness_issue' as anomaly_type,
        'high' as anomaly_severity,
        0.80 as anomaly_score,
        'Snapshot arrived later than the expected realtime capture interval.' as anomaly_reason,
        'rule_feed_freshness' as detector_rule_id,
        'fct_feed_quality' as source_model
    from {{ ref('fct_feed_quality') }}
    where freshness_status = 'late'

)

select *
from stale_vehicle_timestamps

union all

select *
from duplicate_trip_update_entities

union all

select *
from unmatched_schedule_references

union all

select *
from missing_gps_coordinates

union all

select *
from implausible_gps_or_speed

union all

select *
from extreme_delay_outliers

union all

select *
from feed_quality_warnings

union all

select *
from feed_freshness_issues
