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

## Data Policy

Raw full data captures are not committed to the repository. Large captures should live under `data/raw/`, which is ignored by Git. Small synthetic or representative samples may be stored under `data/samples/`.

