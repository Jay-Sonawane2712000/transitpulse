# Static vs Realtime Alignment Notes

## Context

`int_trip_schedule_vs_actual` currently reports zero matched `trip_id` values between realtime trip updates and the static GTFS `trips.txt` table.

This note records the Day 3 investigation and recommended next action. No endpoint or normalization fix was applied because the mismatch is not explained by one safe constant change.

## Current Local Feed Configuration

- Static GTFS URL: `https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip`
- Realtime vehicle positions URL: `https://gtfsrt.prod.obanyc.com/vehiclePositions`
- Realtime trip updates URL: `https://gtfsrt.prod.obanyc.com/tripUpdates`

The downloaded static feed metadata identifies the agency as `MTABC` / MTA Bus Company. Its `feed_info.txt` currently shows:

- `feed_start_date`: `20260906`
- `feed_end_date`: `20270102`
- `feed_version`: `20260813`

The local realtime snapshots being analyzed were captured on `2026-09-02`.

## Observed Trip ID Examples

Realtime trip update `trip_id` examples:

- `46199039-FRPC6-FR_C6-Weekday-03`
- `46199040-FRPC6-FR_C6-Weekday-03`
- `46199098-FRPC6-FR_C6-Weekday-03`
- `46466786-SCPC6-SC_C6-Weekday-03`
- `46466791-SCPC6-SC_C6-Weekday-03`

Realtime vehicle position `trip_id` examples:

- `46199039-FRPC6-FR_C6-Weekday-03`
- `46199098-FRPC6-FR_C6-Weekday-03`
- `46199147-FRPC6-FR_C6-Weekday-03`
- `46199190-FRPC6-FR_C6-Weekday-03`
- `46199191-FRPC6-FR_C6-Weekday-03`

Static scheduled `trip_id` examples:

- `47280549-JKPD6-JK_D6-Weekday-04`
- `47280549-JKPD6-JK_D6-Weekday-04-SDon`
- `47280550-JKPD6-JK_D6-Weekday-04`
- `47414948-SCPD6-SC_D6-Weekday-04`
- `47414948-SCPD6-SC_D6-Weekday-04-SDon`

## Observed Route ID Examples

Realtime route examples:

- `B1`
- `B100`
- `B103`
- `B11`
- `B12`
- `B13`
- `B14`
- `B15`
- `B16`
- `B17`

Static route examples:

- `B100`
- `B103`
- `BM1`
- `BM2`
- `BM3`
- `BM4`
- `BM5`
- `BX23`
- `BXM1`
- `BXM10`

Route overlap observations:

- Realtime distinct routes: `337`
- Static distinct routes in the current local static feed: `92`
- Exact route overlap: `90`
- Examples of realtime routes missing from the current static feed include `B6`, `B41`, `Q44+`, `B35`, `M4`, `M3`, `B46`, `M101`, `B46+`, and `BX36`.

## Likely Root Cause

The mismatch appears to have two causes:

1. The current static feed is only the MTA Bus Company static feed, while the MTA Bus Time realtime endpoints include a broader bus feed family across NYCT Bus and MTA Bus Company routes.
2. The downloaded static feed is future-effective for service starting `2026-09-06`, while the captured realtime snapshots are from `2026-09-02`. Realtime trip IDs use `C6` schedule identifiers, while the static feed contains `D6` identifiers.

This does not look like a simple trip ID normalization issue. Even on overlapping routes such as `B100`, realtime trip IDs use `SC_C6-Weekday-03`, while static trip IDs use `SC_D6-Weekday-04`.

## Recommended Next Action

Do not change only one URL constant yet.

Day 3 follow-up checked the following public sources:

- Data.gov MTA GTFS Static Data listing for MTA Bus Company: `http://web.mta.info/developers/data/busco/google_transit.zip`
- Transitland MTA Bus Company feed page, which lists current static GTFS as `https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip` and historic GTFS as `http://web.mta.info/developers/data/busco/google_transit.zip`
- MobilityDatabase feed `mdb-510`, which lists the MTA Bus Company producer URL and a service range of Jun 28, 2026 to Sep 5, 2026
- Transitland Atlas MTA feed definitions, which show MTA Bus Company plus separate NYCT bus borough static feeds
- `gtfs-realtime-archiver` agency examples, which note that MTA publishes per-borough bus GTFS schedule feeds but a unified Bus Time realtime feed

The exact HTTP producer URL was tested locally:

- `http://web.mta.info/developers/data/busco/google_transit.zip`

It still returned a future-effective static feed with:

- `feed_start_date`: `20260906`
- `feed_end_date`: `20270102`
- `feed_version`: `20260813`
- `C6` trips found: `0`
- `D6` trips found: `45424`

Because this did not produce a static feed matching the Sep 2, 2026 `C6` realtime snapshots, no static URL change was kept.

The next safe fix should be a scoped static-feed alignment improvement:

- Support loading all MTA bus static feed families needed for MTA Bus Time:
  - MTA Bus Company
  - NYCT Bus Bronx
  - NYCT Bus Brooklyn
  - NYCT Bus Manhattan
  - NYCT Bus Queens
  - NYCT Bus Staten Island
- Ensure the static GTFS version overlaps the realtime capture date before comparing `trip_id` values.
- Rebuild raw static tables from the aligned static feed set, then rerun dbt and recheck `schedule_match_status`.

Recommended workaround for the current project phase:

- Use route-level and feed-quality metrics now.
- Treat trip-level schedule-vs-actual and on-time performance as blocked on acquiring static GTFS that overlaps the realtime capture date/version.
- Delay trip-level on-time performance metrics until a matching static feed is captured or obtained from an archive.

Until then, the zero trip match count should be treated as a feed alignment finding, not as a failed dbt join.
