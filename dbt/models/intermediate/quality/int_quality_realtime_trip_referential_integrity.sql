with realtime_trip_ids as (

    select distinct
        'vehicle_positions' as realtime_source,
        snapshot_folder,
        trip_id
    from {{ ref('stg_vehicle_positions') }}
    where trip_id is not null

    union

    select distinct
        'trip_updates' as realtime_source,
        snapshot_folder,
        trip_id
    from {{ ref('stg_trip_updates') }}
    where trip_id is not null

)

select
    realtime_trip_ids.realtime_source,
    realtime_trip_ids.snapshot_folder,
    realtime_trip_ids.trip_id,
    'missing_from_static_trips' as quality_issue
from realtime_trip_ids
left join {{ ref('stg_trips') }} as trips
    on realtime_trip_ids.trip_id = trips.trip_id
where trips.trip_id is null
