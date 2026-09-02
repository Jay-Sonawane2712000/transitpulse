from __future__ import annotations

import argparse
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import poll_gtfs_rt


DEFAULT_INTERVAL_MINUTES = 5
DEFAULT_DURATION_MINUTES = 15


@dataclass(frozen=True)
class CaptureSummary:
    attempted: int
    succeeded: int
    failed: int


def validate_capture_config(interval_minutes: float, duration_minutes: float) -> None:
    if interval_minutes <= 0:
        raise ValueError("--interval-minutes must be greater than 0")
    if duration_minutes <= 0:
        raise ValueError("--duration-minutes must be greater than 0")


def calculate_snapshot_count(interval_minutes: float, duration_minutes: float) -> int:
    validate_capture_config(interval_minutes, duration_minutes)
    return max(1, math.ceil(duration_minutes / interval_minutes))


def summarize_results(results: list[bool]) -> CaptureSummary:
    attempted = len(results)
    succeeded = sum(1 for result in results if result)
    failed = attempted - succeeded
    return CaptureSummary(attempted=attempted, succeeded=succeeded, failed=failed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a short repeated GTFS-RT realtime snapshot capture."
    )
    parser.add_argument("--interval-minutes", type=float, default=DEFAULT_INTERVAL_MINUTES)
    parser.add_argument("--duration-minutes", type=float, default=DEFAULT_DURATION_MINUTES)
    parser.add_argument("--vehicle-url", default=poll_gtfs_rt.VEHICLE_POSITIONS_URL)
    parser.add_argument("--trip-updates-url", default=poll_gtfs_rt.TRIP_UPDATES_URL)
    parser.add_argument("--output-dir", default=str(poll_gtfs_rt.DEFAULT_OUTPUT_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=poll_gtfs_rt.DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args()


def run_capture_window(
    interval_minutes: float,
    duration_minutes: float,
    vehicle_url: str,
    trip_updates_url: str,
    output_dir: str | Path,
    timeout_seconds: int,
    capture_snapshot: Callable[..., dict] = poll_gtfs_rt.capture_snapshot,
    sleep: Callable[[float], None] = time.sleep,
) -> CaptureSummary:
    snapshot_count = calculate_snapshot_count(interval_minutes, duration_minutes)
    results: list[bool] = []

    for snapshot_number in range(1, snapshot_count + 1):
        print(f"Snapshot {snapshot_number} of {snapshot_count}")
        try:
            manifest = capture_snapshot(
                vehicle_url=vehicle_url,
                trip_updates_url=trip_updates_url,
                output_dir=output_dir,
                timeout_seconds=timeout_seconds,
            )
            results.append(True)
            print(
                "Succeeded: "
                f"{manifest['vehicle_record_count']} vehicle records, "
                f"{manifest['trip_update_record_count']} trip update records"
            )
        except Exception as error:
            results.append(False)
            print(f"Failed: {error}")

        if snapshot_number < snapshot_count:
            sleep(interval_minutes * 60)

    return summarize_results(results)


def main() -> None:
    args = parse_args()

    try:
        validate_capture_config(args.interval_minutes, args.duration_minutes)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    summary = run_capture_window(
        interval_minutes=args.interval_minutes,
        duration_minutes=args.duration_minutes,
        vehicle_url=args.vehicle_url,
        trip_updates_url=args.trip_updates_url,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
    )

    print("Realtime capture window complete.")
    print(f"Attempted: {summary.attempted}")
    print(f"Succeeded: {summary.succeeded}")
    print(f"Failed: {summary.failed}")


if __name__ == "__main__":
    main()
