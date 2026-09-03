select
    source_feed || ':' || route_id as route_key,
    source_feed,
    route_id,
    agency_id,
    route_short_name,
    route_long_name,
    route_type
from {{ ref('stg_routes') }}
