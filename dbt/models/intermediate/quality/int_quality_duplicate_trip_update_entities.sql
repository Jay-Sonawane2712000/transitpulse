select
    snapshot_folder,
    entity_id,
    count(*) as duplicate_record_count,
    min(snapshot_timestamp_utc) as first_snapshot_timestamp_utc,
    max(snapshot_timestamp_utc) as last_snapshot_timestamp_utc
from {{ ref('stg_trip_updates') }}
group by
    snapshot_folder,
    entity_id
having count(*) > 1
