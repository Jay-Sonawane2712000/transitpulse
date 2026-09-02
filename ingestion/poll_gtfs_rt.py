from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from google.transit import gtfs_realtime_pb2


VEHICLE_POSITIONS_URL = "https://gtfsrt.prod.obanyc.com/vehiclePositions"
TRIP_UPDATES_URL = "https://gtfsrt.prod.obanyc.com/tripUpdates"
DEFAULT_OUTPUT_DIR = Path("data") / "raw" / "realtime"
DEFAULT_TIMEOUT_SECONDS = 30


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def utc_now() -> datetime:
    return datetime.now(UTC)


def format_timestamp_utc(timestamp: datetime) -> str:
    return timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")


def build_snapshot_dir_name(snapshot_time: datetime) -> str:
    return f"snapshot_{snapshot_time.astimezone(UTC).strftime('%Y%m%d_%H%M%S')}"


def resolve_output_dir(output_dir: str | Path, project_root: Path | None = None) -> Path:
    path = Path(output_dir)
    if path.is_absolute():
        return path

    return (project_root or get_project_root()) / path


def create_snapshot_dir(output_dir: Path, snapshot_time: datetime) -> Path:
    snapshot_dir = output_dir / build_snapshot_dir_name(snapshot_time)
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    return snapshot_dir


def fetch_feed(url: str, timeout_seconds: int) -> gtfs_realtime_pb2.FeedMessage:
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


def optional_field(message: Any, field_name: str) -> Any | None:
    try:
        if message.HasField(field_name):
            return getattr(message, field_name)
    except ValueError:
        value = getattr(message, field_name)
        return value if value not in ("", 0, 0.0) else None

    return None


def vehicle_position_to_record(
    entity: gtfs_realtime_pb2.FeedEntity,
    snapshot_timestamp_utc: str,
) -> dict[str, Any]:
    vehicle = entity.vehicle
    trip = vehicle.trip
    position = vehicle.position
    vehicle_descriptor = vehicle.vehicle

    current_status = None
    if optional_field(vehicle, "current_status") is not None:
        current_status = gtfs_realtime_pb2.VehiclePosition.VehicleStopStatus.Name(
            vehicle.current_status
        )

    return {
        "feed_type": "vehicle_positions",
        "snapshot_timestamp_utc": snapshot_timestamp_utc,
        "entity_id": entity.id or None,
        "vehicle_id": vehicle_descriptor.id or None,
        "trip_id": trip.trip_id or None,
        "route_id": trip.route_id or None,
        "latitude": optional_field(position, "latitude"),
        "longitude": optional_field(position, "longitude"),
        "bearing": optional_field(position, "bearing"),
        "speed": optional_field(position, "speed"),
        "current_stop_sequence": optional_field(vehicle, "current_stop_sequence"),
        "current_status": current_status,
        "timestamp": optional_field(vehicle, "timestamp"),
    }


def stop_time_update_to_record(
    stop_time_update: gtfs_realtime_pb2.TripUpdate.StopTimeUpdate,
) -> dict[str, Any]:
    return {
        "stop_id": stop_time_update.stop_id or None,
        "stop_sequence": optional_field(stop_time_update, "stop_sequence"),
        "arrival_time": optional_field(stop_time_update.arrival, "time"),
        "arrival_delay": optional_field(stop_time_update.arrival, "delay"),
        "departure_time": optional_field(stop_time_update.departure, "time"),
        "departure_delay": optional_field(stop_time_update.departure, "delay"),
    }


def trip_update_to_record(
    entity: gtfs_realtime_pb2.FeedEntity,
    snapshot_timestamp_utc: str,
) -> dict[str, Any]:
    trip_update = entity.trip_update
    trip = trip_update.trip
    vehicle = trip_update.vehicle

    return {
        "feed_type": "trip_updates",
        "snapshot_timestamp_utc": snapshot_timestamp_utc,
        "entity_id": entity.id or None,
        "trip_id": trip.trip_id or None,
        "route_id": trip.route_id or None,
        "vehicle_id": vehicle.id or None,
        "stop_time_updates": [
            stop_time_update_to_record(stop_time_update)
            for stop_time_update in trip_update.stop_time_update
        ],
        "timestamp": optional_field(trip_update, "timestamp"),
    }


def convert_vehicle_positions(
    feed: gtfs_realtime_pb2.FeedMessage,
    snapshot_timestamp_utc: str,
) -> list[dict[str, Any]]:
    return [
        vehicle_position_to_record(entity, snapshot_timestamp_utc)
        for entity in feed.entity
        if entity.HasField("vehicle")
    ]


def convert_trip_updates(
    feed: gtfs_realtime_pb2.FeedMessage,
    snapshot_timestamp_utc: str,
) -> list[dict[str, Any]]:
    return [
        trip_update_to_record(entity, snapshot_timestamp_utc)
        for entity in feed.entity
        if entity.HasField("trip_update")
    ]


def write_json(path: Path, records: Any) -> None:
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def build_manifest(
    snapshot_timestamp_utc: str,
    vehicle_url: str,
    trip_updates_url: str,
    vehicle_records: list[dict[str, Any]],
    trip_update_records: list[dict[str, Any]],
    output_files: list[str],
) -> dict[str, Any]:
    return {
        "snapshot_timestamp_utc": snapshot_timestamp_utc,
        "vehicle_url": vehicle_url,
        "trip_updates_url": trip_updates_url,
        "vehicle_record_count": len(vehicle_records),
        "trip_update_record_count": len(trip_update_records),
        "output_files": output_files,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one GTFS-RT vehicle positions and trip updates snapshot."
    )
    parser.add_argument("--vehicle-url", default=VEHICLE_POSITIONS_URL)
    parser.add_argument("--trip-updates-url", default=TRIP_UPDATES_URL)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args()


def capture_snapshot(
    vehicle_url: str = VEHICLE_POSITIONS_URL,
    trip_updates_url: str = TRIP_UPDATES_URL,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    snapshot_time = utc_now()
    snapshot_timestamp_utc = format_timestamp_utc(snapshot_time)
    resolved_output_dir = resolve_output_dir(output_dir)
    snapshot_dir = create_snapshot_dir(resolved_output_dir, snapshot_time)

    vehicle_feed = fetch_feed(vehicle_url, timeout_seconds)
    trip_updates_feed = fetch_feed(trip_updates_url, timeout_seconds)

    vehicle_records = convert_vehicle_positions(vehicle_feed, snapshot_timestamp_utc)
    trip_update_records = convert_trip_updates(trip_updates_feed, snapshot_timestamp_utc)

    vehicle_output = snapshot_dir / "vehicle_positions.json"
    trip_updates_output = snapshot_dir / "trip_updates.json"
    manifest_output = snapshot_dir / "manifest.json"

    write_json(vehicle_output, vehicle_records)
    write_json(trip_updates_output, trip_update_records)

    output_files = [
        str(vehicle_output),
        str(trip_updates_output),
        str(manifest_output),
    ]
    manifest = build_manifest(
        snapshot_timestamp_utc=snapshot_timestamp_utc,
        vehicle_url=vehicle_url,
        trip_updates_url=trip_updates_url,
        vehicle_records=vehicle_records,
        trip_update_records=trip_update_records,
        output_files=output_files,
    )
    write_json(manifest_output, manifest)
    return manifest


def print_success_summary(manifest: dict[str, Any]) -> None:
    print("Captured one GTFS-RT realtime snapshot.")
    print(f"Vehicle records: {manifest['vehicle_record_count']}")
    print(f"Trip update records: {manifest['trip_update_record_count']}")
    print(f"Manifest: {manifest['output_files'][-1]}")


def main() -> None:
    args = parse_args()
    manifest = capture_snapshot(
        vehicle_url=args.vehicle_url,
        trip_updates_url=args.trip_updates_url,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
    )
    print_success_summary(manifest)


if __name__ == "__main__":
    main()
