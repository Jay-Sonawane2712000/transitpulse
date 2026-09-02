from datetime import UTC, datetime
import importlib.util
from pathlib import Path

from google.transit import gtfs_realtime_pb2
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "ingestion" / "poll_gtfs_rt.py"
SPEC = importlib.util.spec_from_file_location("poll_gtfs_rt", MODULE_PATH)
poll_gtfs_rt = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(poll_gtfs_rt)


def test_snapshot_directory_name_uses_utc_timestamp():
    snapshot_time = datetime(2026, 9, 2, 23, 45, 7, tzinfo=UTC)

    assert poll_gtfs_rt.build_snapshot_dir_name(snapshot_time) == "snapshot_20260902_234507"


def test_resolve_output_dir_uses_project_root_for_relative_paths():
    project_root = Path("example_project")

    output_dir = poll_gtfs_rt.resolve_output_dir("data/raw/realtime", project_root)

    assert output_dir == project_root / "data" / "raw" / "realtime"


def test_vehicle_position_entity_converts_to_record():
    entity = gtfs_realtime_pb2.FeedEntity(id="vehicle-entity-1")
    entity.vehicle.trip.trip_id = "trip-123"
    entity.vehicle.trip.route_id = "B63"
    entity.vehicle.vehicle.id = "bus-456"
    entity.vehicle.position.latitude = 40.6782
    entity.vehicle.position.longitude = -73.9442
    entity.vehicle.position.bearing = 90.0
    entity.vehicle.position.speed = 7.5
    entity.vehicle.current_stop_sequence = 12
    entity.vehicle.current_status = gtfs_realtime_pb2.VehiclePosition.STOPPED_AT
    entity.vehicle.timestamp = 1788392700

    record = poll_gtfs_rt.vehicle_position_to_record(
        entity,
        "2026-09-02T23:45:00Z",
    )

    assert record == {
        "feed_type": "vehicle_positions",
        "snapshot_timestamp_utc": "2026-09-02T23:45:00Z",
        "entity_id": "vehicle-entity-1",
        "vehicle_id": "bus-456",
        "trip_id": "trip-123",
        "route_id": "B63",
        "latitude": pytest.approx(40.6782),
        "longitude": pytest.approx(-73.9442),
        "bearing": 90.0,
        "speed": 7.5,
        "current_stop_sequence": 12,
        "current_status": "STOPPED_AT",
        "timestamp": 1788392700,
    }


def test_trip_update_entity_converts_to_record():
    entity = gtfs_realtime_pb2.FeedEntity(id="trip-entity-1")
    entity.trip_update.trip.trip_id = "trip-789"
    entity.trip_update.trip.route_id = "Q10"
    entity.trip_update.vehicle.id = "bus-111"
    entity.trip_update.timestamp = 1788392800
    stop_time_update = entity.trip_update.stop_time_update.add()
    stop_time_update.stop_id = "stop-1"
    stop_time_update.stop_sequence = 4
    stop_time_update.arrival.time = 1788393000
    stop_time_update.arrival.delay = 120
    stop_time_update.departure.time = 1788393060
    stop_time_update.departure.delay = 180

    record = poll_gtfs_rt.trip_update_to_record(entity, "2026-09-02T23:45:00Z")

    assert record == {
        "feed_type": "trip_updates",
        "snapshot_timestamp_utc": "2026-09-02T23:45:00Z",
        "entity_id": "trip-entity-1",
        "trip_id": "trip-789",
        "route_id": "Q10",
        "vehicle_id": "bus-111",
        "stop_time_updates": [
            {
                "stop_id": "stop-1",
                "stop_sequence": 4,
                "arrival_time": 1788393000,
                "arrival_delay": 120,
                "departure_time": 1788393060,
                "departure_delay": 180,
            }
        ],
        "timestamp": 1788392800,
    }


def test_build_manifest_counts_records_and_lists_outputs():
    manifest = poll_gtfs_rt.build_manifest(
        snapshot_timestamp_utc="2026-09-02T23:45:00Z",
        vehicle_url="https://example.com/vehicles.pb",
        trip_updates_url="https://example.com/trips.pb",
        vehicle_records=[{"entity_id": "vehicle-1"}],
        trip_update_records=[{"entity_id": "trip-1"}, {"entity_id": "trip-2"}],
        output_files=["vehicle_positions.json", "trip_updates.json", "manifest.json"],
    )

    assert manifest == {
        "snapshot_timestamp_utc": "2026-09-02T23:45:00Z",
        "vehicle_url": "https://example.com/vehicles.pb",
        "trip_updates_url": "https://example.com/trips.pb",
        "vehicle_record_count": 1,
        "trip_update_record_count": 2,
        "output_files": ["vehicle_positions.json", "trip_updates.json", "manifest.json"],
    }
