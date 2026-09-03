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

## Archive Investigation for September 2, 2026 Realtime Snapshots

Follow-up investigation on `2026-09-03` checked whether historical static GTFS feeds are available for the six MTA bus static feed families needed to align with the `2026-09-02` realtime snapshots.

### Transitland

Transitland public feed/version pages expose historical feed version metadata for the relevant onestop IDs, including versions with service windows covering `2026-09-02`.

Checked onestop IDs:

- `busco`: `f-dr5r-mtabc`
- `brooklyn`: `f-dr5r-mtanyctbusbrooklyn`
- `bronx`: `f-dr72-mtanyctbusbronx`
- `manhattan`: `f-dr5r-mtanyctbusmanhattan`
- `queens`: `f-dr5x-mtanyctbusqueens`
- `staten_island`: `f-dr5r-mtanyctbusstatenisland`

Transitland observations:

- Historical feed versions appear to exist.
- The public pages show service date metadata and file metadata.
- The API v2 download endpoint returned `401 Unauthorized` without an API key.
- The public page configuration references a `downloadHistoricFeedVersion` role, so historic downloads may require Transitland account/API access.
- No unauthenticated direct historic zip URL was verified from Transitland.

### MobilityDatabase

MobilityDatabase exposes public hosted historical GTFS zip URLs for all six MTA bus static feeds with service windows that include `2026-09-02`.

Candidate date-overlapping archives:

| feed | MobilityDatabase ID | dataset | downloaded_at | service range | direct zip |
| --- | --- | --- | --- | --- | --- |
| `busco` | `mdb-510` | `mdb-510-202606240101` | `2026-06-24T01:01:29.126797Z` | `2026-06-28T04:00:00Z` to `2026-09-06T03:59:00Z` | `https://files.mobilitydatabase.org/mdb-510/mdb-510-202606240101/mdb-510-202606240101.zip` |
| `brooklyn` | `mdb-512` | `mdb-512-202606240055` | `2026-06-24T00:55:54.782367Z` | `2026-06-27T04:00:00Z` to `2026-09-06T03:59:00Z` | `https://files.mobilitydatabase.org/mdb-512/mdb-512-202606240055/mdb-512-202606240055.zip` |
| `bronx` | `mdb-528` | `mdb-528-202606240058` | `2026-06-24T00:58:13.146737Z` | `2026-06-27T04:00:00Z` to `2026-09-06T03:59:00Z` | `https://files.mobilitydatabase.org/mdb-528/mdb-528-202606240058/mdb-528-202606240058.zip` |
| `manhattan` | `mdb-513` | `mdb-513-202606240130` | `2026-06-24T01:30:17.518575Z` | `2026-06-27T04:00:00Z` to `2026-09-06T03:59:00Z` | `https://files.mobilitydatabase.org/mdb-513/mdb-513-202606240130/mdb-513-202606240130.zip` |
| `queens` | `mdb-520` | `mdb-520-202606240102` | `2026-06-24T01:02:20.886010Z` | `2026-06-27T04:00:00Z` to `2026-09-06T03:59:00Z` | `https://files.mobilitydatabase.org/mdb-520/mdb-520-202606240102/mdb-520-202606240102.zip` |
| `staten_island` | `mdb-514` | `mdb-514-202607290026` | `2026-07-29T00:26:41.442361Z` | `2026-06-28T04:00:00Z` to `2026-09-06T03:59:00Z` | `https://files.mobilitydatabase.org/mdb-514/mdb-514-202607290026/mdb-514-202607290026.zip` |

Each listed MobilityDatabase zip URL was verified with an HTTP `HEAD` request returning `200 OK`, `content-type: application/zip`, and byte ranges enabled. The files were not downloaded during this investigation step.

Important caveat:

- These MobilityDatabase archives overlap the realtime snapshot date and are strong candidates for the needed C6 static dataset.
- The archive metadata does not expose individual `trip_id` values, so C6 trip IDs have not yet been confirmed without downloading and inspecting `trips.txt`.
- The next safe project step is to download these six archived feeds into a separate archived-static raw folder, inspect `trips.txt` for C6 trip IDs, then rerun the raw loader/dbt matching check if C6 is confirmed.

Recommended next action:

- Prefer the MobilityDatabase date-overlapping public archive candidates for a controlled historical-static download step.
- Keep the current no-normalization rule: do not convert C6 to D6 by string manipulation.
- If the MobilityDatabase archives do not contain C6 trip IDs after inspection, continue with route-level and feed-quality metrics and capture fresh realtime after `2026-09-06` when the D6 static feeds are effective.

## Final Alignment Resolution

The MobilityDatabase archived static GTFS feeds were downloaded to `data/raw/static_archives/c6_20260902/` and inspected. All six archived feeds cover the `2026-09-02` realtime snapshot date and contain C6 trip IDs with zero D6 trip IDs.

The raw loader was rerun with:

```powershell
python ingestion/load_raw_to_duckdb.py --static-dir data/raw/static_archives/c6_20260902
```

After rebuilding dbt, `int_trip_schedule_vs_actual` matched all current trip update records to static scheduled trips:

- `matched_to_static_schedule`: `29,779`
- `unmatched_realtime_trip`: `0`
- match rate: `100.00%`
- unmatched rate: `0.00%`

Final root cause:

1. Static feed coverage was incomplete when only MTA Bus Company static GTFS was loaded. This was fixed by supporting all six MTA bus static feed families.
2. Static/realtime schedule rating was mismatched. The current public static feeds use D6 service effective `2026-09-06`, while the `2026-09-02` realtime captures use C6 trip IDs. This was fixed by using MobilityDatabase archived C6 static feeds whose service windows include `2026-09-02`.

C6-to-D6 string normalization was rejected because C6 and D6 represent different published schedule versions/effective service periods. Rewriting identifiers would create false matches instead of preserving the actual data lineage.

## Reproducibility Guard

The current public MTA static feeds in `data/raw/static/` use D6 trip IDs and start on `2026-09-06`, so they do not match the `2026-09-02` realtime snapshots that use C6 trip IDs.

The MobilityDatabase archived C6 static feeds were downloaded into `data/raw/static_archives/c6_20260902/`. The archive identifiers and direct URLs are listed in the MobilityDatabase archive table above.

To reproduce the successful alignment, load the archived static feeds with:

```powershell
python ingestion/load_raw_to_duckdb.py --static-dir data/raw/static_archives/c6_20260902
```

Validation after loading the archived feeds:

- `matched_to_static_schedule`: `29,779`
- `unmatched_realtime_trip`: `0`
- match rate: `100.00%`
- unmatched rate: `0.00%`

A dbt singular test, `assert_trip_schedule_match_rate_above_threshold`, now protects against silent static/realtime schedule mismatch. It fails when `int_trip_schedule_vs_actual` has zero rows or when the trip schedule match rate falls below `95%`.
