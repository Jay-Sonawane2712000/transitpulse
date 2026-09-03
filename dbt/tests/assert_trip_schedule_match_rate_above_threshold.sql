with match_summary as (
    select
        count(*) as total_rows,
        sum(
            case
                when schedule_match_status = 'matched_to_static_schedule' then 1
                else 0
            end
        ) as matched_rows
    from {{ ref('int_trip_schedule_vs_actual') }}
),

rate_check as (
    select
        total_rows,
        matched_rows,
        case
            when total_rows = 0 then 0.0
            else cast(matched_rows as double) / cast(total_rows as double)
        end as match_rate
    from match_summary
)

select
    total_rows,
    matched_rows,
    match_rate,
    0.95 as minimum_match_rate
from rate_check
where total_rows = 0
   or match_rate < 0.95
