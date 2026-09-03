select
    trip_updates.snapshot_folder,
    trip_updates.snapshot_timestamp_utc,
    trip_updates.entity_id,
    trip_updates.trip_id,
    trip_updates.route_id as realtime_route_id,
    trips.route_id as scheduled_route_id,
    trip_updates.vehicle_id,
    trip_updates.trip_update_timestamp_utc,
    case
        when trips.trip_id is not null then 'matched_to_static_schedule'
        else 'unmatched_realtime_trip'
    end as schedule_match_status,
    trips.trip_headsign,
    trips.direction_id,
    trips.shape_id
from {{ ref('stg_trip_updates') }} as trip_updates
left join {{ ref('stg_trips') }} as trips
    on trip_updates.trip_id = trips.trip_id
