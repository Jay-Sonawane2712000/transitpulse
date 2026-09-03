select
    snapshot_timestamp_utc,
    snapshot_folder,
    entity_id,
    vehicle_id,
    trip_id,
    route_id,
    latitude,
    longitude,
    case
        when latitude is null and longitude is null then 'missing_latitude_and_longitude'
        when latitude is null then 'missing_latitude'
        when longitude is null then 'missing_longitude'
    end as quality_issue
from {{ ref('stg_vehicle_positions') }}
where latitude is null
   or longitude is null
