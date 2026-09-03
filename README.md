# TransitPulse

TransitPulse is a Bus Service Data Quality & Delay Intelligence Platform focused on turning transit feed data into reliable, queryable, and operationally useful signals.

## Problem Statement

Bus agencies and riders depend on timely, accurate service data, but realtime feeds can contain missing vehicles, stale updates, inconsistent trip references, and delay patterns that are difficult to inspect. TransitPulse will help capture, validate, transform, and analyze bus service data so data quality issues and delay trends can be surfaced clearly.

## Planned Architecture

- Ingestion: collect scheduled and realtime transit data using Python and HTTP APIs.
- Storage: persist local analytical datasets in DuckDB with columnar files where useful.
- Transformation: model cleaned datasets with dbt and DuckDB.
- Detection: identify data quality issues, delay anomalies, and operational patterns.
- Dashboard: present service quality and delay intelligence with Streamlit and Plotly.
- Testing: validate ingestion, transformations, and detection logic with pytest.

## Core Phases / Day Plan

1. Scaffold repository, dependencies, and project documentation.
2. Add sample data contracts and initial ingestion experiments.
3. Build local DuckDB storage and dbt project configuration.
4. Create cleaned service, vehicle, trip, and delay models.
5. Add data quality checks and anomaly detection modules.
6. Build the Streamlit dashboard for monitoring and exploration.
7. Add tests, documentation, and reproducible run instructions.

## Tech Stack

- Python
- requests
- pandas
- pyarrow
- gtfs-realtime-bindings
- dbt-core
- dbt-duckdb
- duckdb
- streamlit
- plotly
- pytest

## Local Setup

Create and activate a local virtual environment on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install project dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the environment import test:

```powershell
python -m pytest tests/test_environment.py
```

## Download Static GTFS Schedule Data

Download the legacy/testing single MTA Bus Company static GTFS schedule archive:

```powershell
python ingestion/download_static_gtfs.py
```

For TransitPulse analysis against the unified MTA Bus Time realtime feed, download all six MTA bus static feeds:

```powershell
python ingestion/download_static_gtfs.py --all-feeds
```

The single-feed command creates `data/raw/static/`, saves the GTFS zip file there, extracts the GTFS text files into `data/raw/static/extracted/`, and writes `data/raw/static/manifest.json`. The all-feeds command stores each feed under `data/raw/static/<feed_name>/` with its own zip, extracted files, and manifest, then writes a combined `data/raw/static/manifest.json`. The `data/raw/static/` folder is ignored by Git, so raw full data captures are not committed.

## Capture One GTFS-RT Realtime Snapshot

Capture vehicle positions and trip updates once:

```powershell
python ingestion/poll_gtfs_rt.py --vehicle-url "https://gtfsrt.prod.obanyc.com/vehiclePositions?key=YOUR_KEY" --trip-updates-url "https://gtfsrt.prod.obanyc.com/tripUpdates?key=YOUR_KEY"
```

Snapshots are stored under `data/raw/realtime/snapshot_YYYYMMDD_HHMMSS/` with `vehicle_positions.json`, `trip_updates.json`, and `manifest.json`. The `data/raw/realtime/` folder is ignored by Git, so captured realtime snapshots are not committed.

## Run A Short Realtime Capture Window

Run a tiny two-snapshot test window:

```powershell
python ingestion/run_realtime_capture.py --interval-minutes 1 --duration-minutes 2 --vehicle-url "https://gtfsrt.prod.obanyc.com/vehiclePositions?key=YOUR_KEY" --trip-updates-url "https://gtfsrt.prod.obanyc.com/tripUpdates?key=YOUR_KEY"
```

For a longer portfolio capture, run a 24-hour collection at five-minute intervals:

```powershell
python ingestion/run_realtime_capture.py --interval-minutes 5 --duration-minutes 1440 --vehicle-url "https://gtfsrt.prod.obanyc.com/vehiclePositions?key=YOUR_KEY" --trip-updates-url "https://gtfsrt.prod.obanyc.com/tripUpdates?key=YOUR_KEY"
```

Realtime captures are stored under `data/raw/realtime/`, which is ignored by Git.

## Load Raw Data Into DuckDB

Load local static GTFS files and realtime snapshot JSON files into raw DuckDB tables:

```powershell
python ingestion/load_raw_to_duckdb.py
```

The default database path is `data/warehouse/transitpulse.duckdb`. Local DuckDB database files are ignored by Git, so rebuilt warehouse files are not committed.

When using the all-feeds static download, static raw tables include a `source_feed` column identifying the originating feed folder, such as `busco`, `brooklyn`, `bronx`, `manhattan`, `queens`, or `staten_island`.

## dbt Transformation Layer

The `dbt/` folder contains the dbt project configuration for transforming raw GTFS and GTFS-RT DuckDB tables into staging, intermediate, and mart layers. It connects to the local DuckDB warehouse at `data/warehouse/transitpulse.duckdb`.

## Data Policy

Raw full data captures are not committed to the repository. Large captures should live under `data/raw/`, which is ignored by Git. Small synthetic or representative samples may be stored under `data/samples/`.
