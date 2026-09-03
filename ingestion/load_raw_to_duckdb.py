from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


DEFAULT_STATIC_DIR = Path("data") / "raw" / "static" / "extracted"
DEFAULT_REALTIME_DIR = Path("data") / "raw" / "realtime"
DEFAULT_DATABASE_PATH = Path("data") / "warehouse" / "transitpulse.duckdb"
STATIC_ROOT_DIR = Path("data") / "raw" / "static"
LEGACY_SOURCE_FEED = "single_feed"
RECOGNIZED_STATIC_FEEDS = [
    "busco",
    "brooklyn",
    "bronx",
    "manhattan",
    "queens",
    "staten_island",
]
REQUIRED_STATIC_FILES = ["routes.txt", "trips.txt", "stops.txt", "stop_times.txt"]

STATIC_GTFS_TABLES = {
    "routes.txt": "raw_routes",
    "trips.txt": "raw_trips",
    "stops.txt": "raw_stops",
    "stop_times.txt": "raw_stop_times",
    "calendar.txt": "raw_calendar",
    "calendar_dates.txt": "raw_calendar_dates",
}

REALTIME_TABLE_SCHEMAS = {
    "raw_vehicle_positions": {
        "feed_type": "VARCHAR",
        "snapshot_timestamp_utc": "VARCHAR",
        "entity_id": "VARCHAR",
        "vehicle_id": "VARCHAR",
        "trip_id": "VARCHAR",
        "route_id": "VARCHAR",
        "latitude": "DOUBLE",
        "longitude": "DOUBLE",
        "bearing": "DOUBLE",
        "speed": "DOUBLE",
        "current_stop_sequence": "BIGINT",
        "current_status": "VARCHAR",
        "timestamp": "BIGINT",
        "snapshot_folder": "VARCHAR",
    },
    "raw_trip_updates": {
        "feed_type": "VARCHAR",
        "snapshot_timestamp_utc": "VARCHAR",
        "entity_id": "VARCHAR",
        "trip_id": "VARCHAR",
        "route_id": "VARCHAR",
        "vehicle_id": "VARCHAR",
        "stop_time_updates": "VARCHAR",
        "timestamp": "BIGINT",
        "snapshot_folder": "VARCHAR",
    },
}


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_project_path(path: str | Path, project_root: Path | None = None) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    return (project_root or get_project_root()) / candidate


def ensure_database_parent(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)


def read_static_gtfs_file(file_path: Path) -> pd.DataFrame:
    return pd.read_csv(file_path, dtype=str, keep_default_na=False)


def load_dataframe_replace(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    dataframe: pd.DataFrame,
) -> int:
    connection.register("source_dataframe", dataframe)
    try:
        connection.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM source_dataframe")
    finally:
        connection.unregister("source_dataframe")

    return connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]


def create_empty_table_replace(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    schema: dict[str, str],
) -> int:
    columns = ", ".join(f"{column_name} {column_type}" for column_name, column_type in schema.items())
    connection.execute(f"CREATE OR REPLACE TABLE {table_name} ({columns})")
    return 0


def detect_static_feed_sources(static_dir: Path) -> tuple[str, list[tuple[str, Path]]]:
    static_root = static_dir.parent if static_dir.name == "extracted" else static_dir
    multi_feed_sources = [
        (feed_name, static_root / feed_name / "extracted")
        for feed_name in RECOGNIZED_STATIC_FEEDS
        if (static_root / feed_name / "extracted").exists()
    ]

    if multi_feed_sources:
        return "multi-feed", multi_feed_sources

    if static_dir.exists():
        return "single-feed", [(LEGACY_SOURCE_FEED, static_dir)]

    return "single-feed", []


def validate_required_static_files(feed_name: str, extracted_dir: Path) -> None:
    missing_files = [
        file_name
        for file_name in REQUIRED_STATIC_FILES
        if not (extracted_dir / file_name).exists()
    ]
    if missing_files:
        missing = ", ".join(missing_files)
        raise FileNotFoundError(
            f"Static feed '{feed_name}' is missing required GTFS files: {missing}"
        )


def read_static_gtfs_file_for_feed(
    file_path: Path,
    source_feed: str,
) -> pd.DataFrame:
    dataframe = read_static_gtfs_file(file_path)
    dataframe["source_feed"] = source_feed
    return dataframe


def collect_static_table_dataframes(
    feed_sources: list[tuple[str, Path]],
    filename: str,
    required: bool,
) -> list[pd.DataFrame]:
    dataframes: list[pd.DataFrame] = []

    for feed_name, extracted_dir in feed_sources:
        file_path = extracted_dir / filename
        if not file_path.exists():
            if required:
                raise FileNotFoundError(
                    f"Static feed '{feed_name}' is missing required GTFS file: {filename}"
                )
            continue

        dataframes.append(read_static_gtfs_file_for_feed(file_path, feed_name))

    return dataframes


def load_static_tables(
    connection: duckdb.DuckDBPyConnection,
    static_dir: Path,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    _, feed_sources = detect_static_feed_sources(static_dir)

    for feed_name, extracted_dir in feed_sources:
        validate_required_static_files(feed_name, extracted_dir)

    for filename, table_name in STATIC_GTFS_TABLES.items():
        dataframes = collect_static_table_dataframes(
            feed_sources=feed_sources,
            filename=filename,
            required=filename in REQUIRED_STATIC_FILES,
        )
        if not dataframes:
            continue

        dataframe = pd.concat(dataframes, ignore_index=True)
        counts[table_name] = load_dataframe_replace(connection, table_name, dataframe)

    return counts


def list_snapshot_dirs(realtime_dir: Path) -> list[Path]:
    if not realtime_dir.exists():
        return []

    return sorted(
        path
        for path in realtime_dir.iterdir()
        if path.is_dir() and path.name.startswith("snapshot_")
    )


def read_json_records(json_path: Path) -> list[dict[str, Any]]:
    if not json_path.exists():
        return []

    with json_path.open(encoding="utf-8") as input_file:
        records = json.load(input_file)

    if not isinstance(records, list):
        raise ValueError(f"Expected a list of records in {json_path}")

    return records


def records_to_dataframe(records: list[dict[str, Any]], snapshot_folder: str) -> pd.DataFrame:
    prepared_records: list[dict[str, Any]] = []

    for record in records:
        prepared_record = dict(record)
        prepared_record["snapshot_folder"] = snapshot_folder
        if "stop_time_updates" in prepared_record:
            prepared_record["stop_time_updates"] = json.dumps(
                prepared_record["stop_time_updates"],
                separators=(",", ":"),
            )
        prepared_records.append(prepared_record)

    return pd.DataFrame(prepared_records)


def collect_realtime_records(realtime_dir: Path, filename: str) -> pd.DataFrame:
    dataframes: list[pd.DataFrame] = []

    for snapshot_dir in list_snapshot_dirs(realtime_dir):
        records = read_json_records(snapshot_dir / filename)
        if records:
            dataframes.append(records_to_dataframe(records, snapshot_dir.name))

    if not dataframes:
        return pd.DataFrame()

    return pd.concat(dataframes, ignore_index=True)


def load_realtime_tables(
    connection: duckdb.DuckDBPyConnection,
    realtime_dir: Path,
) -> dict[str, int]:
    realtime_sources = {
        "raw_vehicle_positions": "vehicle_positions.json",
        "raw_trip_updates": "trip_updates.json",
    }
    counts: dict[str, int] = {}

    for table_name, filename in realtime_sources.items():
        dataframe = collect_realtime_records(realtime_dir, filename)
        if dataframe.empty and len(dataframe.columns) == 0:
            counts[table_name] = create_empty_table_replace(
                connection,
                table_name,
                REALTIME_TABLE_SCHEMAS[table_name],
            )
        else:
            counts[table_name] = load_dataframe_replace(connection, table_name, dataframe)

    return counts


def load_raw_data(
    static_dir: Path,
    realtime_dir: Path,
    database_path: Path,
) -> dict[str, int]:
    ensure_database_parent(database_path)

    with duckdb.connect(str(database_path)) as connection:
        table_counts = {}
        table_counts.update(load_static_tables(connection, static_dir))
        table_counts.update(load_realtime_tables(connection, realtime_dir))

    return table_counts


def get_loaded_feed_names(static_dir: Path) -> list[str]:
    _, feed_sources = detect_static_feed_sources(static_dir)
    return [feed_name for feed_name, _ in feed_sources]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load local raw GTFS static and realtime snapshot files into DuckDB raw tables."
    )
    parser.add_argument("--static-dir", default=str(DEFAULT_STATIC_DIR))
    parser.add_argument("--realtime-dir", default=str(DEFAULT_REALTIME_DIR))
    parser.add_argument("--database-path", default=str(DEFAULT_DATABASE_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    static_dir = resolve_project_path(args.static_dir)
    realtime_dir = resolve_project_path(args.realtime_dir)
    database_path = resolve_project_path(args.database_path)

    table_counts = load_raw_data(
        static_dir=static_dir,
        realtime_dir=realtime_dir,
        database_path=database_path,
    )
    static_layout, _ = detect_static_feed_sources(static_dir)
    feeds_loaded = get_loaded_feed_names(static_dir)

    print("Loaded raw GTFS data into DuckDB.")
    print(f"Static layout detected: {static_layout}")
    print(f"Static feeds loaded: {', '.join(feeds_loaded) if feeds_loaded else 'none'}")
    for table_name in sorted(table_counts):
        print(f"{table_name}: {table_counts[table_name]} rows")
    print(f"Database: {database_path}")


if __name__ == "__main__":
    main()
