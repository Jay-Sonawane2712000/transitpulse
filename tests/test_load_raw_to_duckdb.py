import importlib.util
import json
from pathlib import Path
import shutil
import uuid

import duckdb


MODULE_PATH = Path(__file__).resolve().parents[1] / "ingestion" / "load_raw_to_duckdb.py"
SPEC = importlib.util.spec_from_file_location("load_raw_to_duckdb", MODULE_PATH)
load_raw_to_duckdb = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(load_raw_to_duckdb)


def make_test_workspace() -> Path:
    workspace = Path(__file__).resolve().parent / f"_tmp_load_raw_{uuid.uuid4().hex}"
    workspace.mkdir()
    return workspace


def remove_test_workspace(workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)


def test_static_table_mapping_matches_expected_raw_tables():
    assert load_raw_to_duckdb.STATIC_GTFS_TABLES == {
        "routes.txt": "raw_routes",
        "trips.txt": "raw_trips",
        "stops.txt": "raw_stops",
        "stop_times.txt": "raw_stop_times",
        "calendar.txt": "raw_calendar",
        "calendar_dates.txt": "raw_calendar_dates",
    }


def test_load_static_tables_reads_present_gtfs_files_only():
    workspace = make_test_workspace()
    try:
        static_dir = workspace / "static"
        static_dir.mkdir()
        (static_dir / "routes.txt").write_text(
            "route_id,route_short_name\nM20,M20\n",
            encoding="utf-8",
        )
        (static_dir / "stops.txt").write_text(
            "stop_id,stop_name\n400001,Example Stop\n",
            encoding="utf-8",
        )
        (static_dir / "trips.txt").write_text(
            "route_id,service_id,trip_id\nM20,weekday,trip-1\n",
            encoding="utf-8",
        )
        (static_dir / "stop_times.txt").write_text(
            "trip_id,stop_id,stop_sequence\ntrip-1,400001,1\n",
            encoding="utf-8",
        )

        with duckdb.connect(":memory:") as connection:
            counts = load_raw_to_duckdb.load_static_tables(connection, static_dir)
            route_count = connection.execute("SELECT COUNT(*) FROM raw_routes").fetchone()[0]
            stop_count = connection.execute("SELECT COUNT(*) FROM raw_stops").fetchone()[0]
            source_feed = connection.execute("SELECT source_feed FROM raw_routes").fetchone()[0]

        assert counts == {
            "raw_routes": 1,
            "raw_trips": 1,
            "raw_stops": 1,
            "raw_stop_times": 1,
        }
        assert route_count == 1
        assert stop_count == 1
        assert source_feed == "single_feed"
    finally:
        remove_test_workspace(workspace)


def write_required_static_files(extracted_dir: Path, route_id: str, trip_id: str) -> None:
    extracted_dir.mkdir(parents=True, exist_ok=True)
    (extracted_dir / "routes.txt").write_text(
        f"route_id,route_short_name\n{route_id},{route_id}\n",
        encoding="utf-8",
    )
    (extracted_dir / "trips.txt").write_text(
        f"route_id,service_id,trip_id\n{route_id},weekday,{trip_id}\n",
        encoding="utf-8",
    )
    (extracted_dir / "stops.txt").write_text(
        f"stop_id,stop_name\n{route_id}-stop,Example Stop\n",
        encoding="utf-8",
    )
    (extracted_dir / "stop_times.txt").write_text(
        f"trip_id,stop_id,stop_sequence\n{trip_id},{route_id}-stop,1\n",
        encoding="utf-8",
    )


def test_multi_feed_layout_is_detected_and_preferred_over_legacy_layout():
    workspace = make_test_workspace()
    try:
        static_root = workspace / "static"
        legacy_extracted = static_root / "extracted"
        write_required_static_files(legacy_extracted, "LEGACY", "legacy-trip")
        write_required_static_files(static_root / "busco" / "extracted", "B100", "busco-trip")

        layout, feed_sources = load_raw_to_duckdb.detect_static_feed_sources(legacy_extracted)

        assert layout == "multi-feed"
        assert feed_sources == [("busco", static_root / "busco" / "extracted")]
    finally:
        remove_test_workspace(workspace)


def test_multi_feed_static_rows_are_combined_with_source_feed():
    workspace = make_test_workspace()
    try:
        static_root = workspace / "static"
        write_required_static_files(static_root / "busco" / "extracted", "B100", "busco-trip")
        write_required_static_files(static_root / "brooklyn" / "extracted", "B1", "brooklyn-trip")

        with duckdb.connect(":memory:") as connection:
            counts = load_raw_to_duckdb.load_static_tables(
                connection,
                static_root / "extracted",
            )
            rows = connection.execute(
                "SELECT route_id, source_feed FROM raw_routes ORDER BY source_feed"
            ).fetchall()

        assert counts["raw_routes"] == 2
        assert counts["raw_trips"] == 2
        assert rows == [("B1", "brooklyn"), ("B100", "busco")]
    finally:
        remove_test_workspace(workspace)


def test_missing_optional_calendar_files_do_not_fail_multi_feed_load():
    workspace = make_test_workspace()
    try:
        static_root = workspace / "static"
        write_required_static_files(static_root / "busco" / "extracted", "B100", "busco-trip")

        with duckdb.connect(":memory:") as connection:
            counts = load_raw_to_duckdb.load_static_tables(
                connection,
                static_root / "extracted",
            )

        assert counts["raw_routes"] == 1
        assert "raw_calendar" not in counts
        assert "raw_calendar_dates" not in counts
    finally:
        remove_test_workspace(workspace)


def test_missing_required_static_file_is_reported_clearly():
    workspace = make_test_workspace()
    try:
        static_root = workspace / "static"
        extracted_dir = static_root / "busco" / "extracted"
        write_required_static_files(extracted_dir, "B100", "busco-trip")
        (extracted_dir / "trips.txt").unlink()

        with duckdb.connect(":memory:") as connection:
            try:
                load_raw_to_duckdb.load_static_tables(
                    connection,
                    static_root / "extracted",
                )
            except FileNotFoundError as error:
                error_message = str(error)
            else:
                raise AssertionError("Expected missing required file error")

        assert "busco" in error_message
        assert "trips.txt" in error_message
    finally:
        remove_test_workspace(workspace)


def test_collect_realtime_records_adds_snapshot_folder_and_json_stop_updates():
    workspace = make_test_workspace()
    try:
        realtime_dir = workspace / "realtime"
        snapshot_dir = realtime_dir / "snapshot_20260902_234000"
        snapshot_dir.mkdir(parents=True)
        (snapshot_dir / "trip_updates.json").write_text(
            json.dumps(
                [
                    {
                        "entity_id": "trip-1",
                        "trip_id": "trip-1",
                        "route_id": "M20",
                        "stop_time_updates": [{"stop_id": "400001"}],
                    }
                ]
            ),
            encoding="utf-8",
        )

        dataframe = load_raw_to_duckdb.collect_realtime_records(
            realtime_dir,
            "trip_updates.json",
        )

        assert len(dataframe) == 1
        assert dataframe.loc[0, "snapshot_folder"] == "snapshot_20260902_234000"
        assert dataframe.loc[0, "stop_time_updates"] == '[{"stop_id":"400001"}]'
    finally:
        remove_test_workspace(workspace)


def test_load_realtime_tables_creates_empty_tables_without_snapshots():
    workspace = make_test_workspace()
    try:
        realtime_dir = workspace / "realtime"

        with duckdb.connect(":memory:") as connection:
            counts = load_raw_to_duckdb.load_realtime_tables(connection, realtime_dir)
            vehicle_count = connection.execute(
                "SELECT COUNT(*) FROM raw_vehicle_positions"
            ).fetchone()[0]
            trip_count = connection.execute("SELECT COUNT(*) FROM raw_trip_updates").fetchone()[0]

        assert counts == {"raw_vehicle_positions": 0, "raw_trip_updates": 0}
        assert vehicle_count == 0
        assert trip_count == 0
    finally:
        remove_test_workspace(workspace)


def test_load_raw_data_creates_database_parent_and_tables():
    workspace = make_test_workspace()
    try:
        static_dir = workspace / "static"
        realtime_dir = workspace / "realtime"
        snapshot_dir = realtime_dir / "snapshot_20260902_234000"
        static_dir.mkdir()
        snapshot_dir.mkdir(parents=True)

        (static_dir / "routes.txt").write_text(
            "route_id,route_short_name\nM20,M20\n",
            encoding="utf-8",
        )
        (static_dir / "trips.txt").write_text(
            "route_id,service_id,trip_id\nM20,weekday,trip-1\n",
            encoding="utf-8",
        )
        (static_dir / "stops.txt").write_text(
            "stop_id,stop_name\n400001,Example Stop\n",
            encoding="utf-8",
        )
        (static_dir / "stop_times.txt").write_text(
            "trip_id,stop_id,stop_sequence\ntrip-1,400001,1\n",
            encoding="utf-8",
        )
        (snapshot_dir / "vehicle_positions.json").write_text(
            json.dumps([{"entity_id": "vehicle-1", "route_id": "M20"}]),
            encoding="utf-8",
        )
        (snapshot_dir / "trip_updates.json").write_text(
            json.dumps([{"entity_id": "trip-1", "route_id": "M20"}]),
            encoding="utf-8",
        )

        database_path = workspace / "warehouse" / "transitpulse.duckdb"
        counts = load_raw_to_duckdb.load_raw_data(static_dir, realtime_dir, database_path)

        with duckdb.connect(str(database_path)) as connection:
            raw_routes_count = connection.execute("SELECT COUNT(*) FROM raw_routes").fetchone()[0]
            raw_vehicle_count = connection.execute(
                "SELECT COUNT(*) FROM raw_vehicle_positions"
            ).fetchone()[0]
            raw_trip_count = connection.execute("SELECT COUNT(*) FROM raw_trip_updates").fetchone()[0]

        assert database_path.exists()
        assert counts["raw_routes"] == 1
        assert counts["raw_vehicle_positions"] == 1
        assert counts["raw_trip_updates"] == 1
        assert raw_routes_count == 1
        assert raw_vehicle_count == 1
        assert raw_trip_count == 1
    finally:
        remove_test_workspace(workspace)
