with expected_labels as (

    select 'normal' as synthetic_anomaly_type
    union all
    select 'stale_vehicle_position_timestamp'
    union all
    select 'gps_jump_or_implausible_speed'
    union all
    select 'duplicate_trip_update_entity'
    union all
    select 'missing_or_unmatched_schedule_reference'
    union all
    select 'late_or_extreme_delay_outlier'

),

observed_labels as (

    select
        synthetic_anomaly_type,
        count(*) as row_count
    from {{ ref('int_synthetic_anomaly_evaluation') }}
    group by 1

)

select
    expected_labels.synthetic_anomaly_type,
    coalesce(observed_labels.row_count, 0) as row_count
from expected_labels
left join observed_labels
    on expected_labels.synthetic_anomaly_type = observed_labels.synthetic_anomaly_type
where coalesce(observed_labels.row_count, 0) = 0
