with snapshots as (

    select distinct
        snapshot_folder,
        snapshot_timestamp_utc
    from {{ ref('stg_vehicle_positions') }}

    union

    select distinct
        snapshot_folder,
        snapshot_timestamp_utc
    from {{ ref('stg_trip_updates') }}

),

ordered_snapshots as (

    select
        snapshot_folder,
        snapshot_timestamp_utc,
        lag(snapshot_timestamp_utc) over (
            order by snapshot_timestamp_utc
        ) as previous_snapshot_timestamp_utc
    from snapshots

)

select
    snapshot_folder,
    snapshot_timestamp_utc,
    previous_snapshot_timestamp_utc,
    date_diff(
        'second',
        previous_snapshot_timestamp_utc,
        snapshot_timestamp_utc
    ) / 60.0 as gap_minutes,
    case
        when previous_snapshot_timestamp_utc is null then 'first_snapshot'
        when date_diff('second', previous_snapshot_timestamp_utc, snapshot_timestamp_utc) / 60.0 > 10 then 'gap_exceeds_threshold'
        else 'within_expected_interval'
    end as freshness_status
from ordered_snapshots
