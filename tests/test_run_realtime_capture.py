import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "ingestion" / "run_realtime_capture.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("run_realtime_capture", MODULE_PATH)
run_realtime_capture = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["run_realtime_capture"] = run_realtime_capture
SPEC.loader.exec_module(run_realtime_capture)


def test_calculate_snapshot_count_rounds_up_to_cover_duration():
    assert run_realtime_capture.calculate_snapshot_count(5, 15) == 3
    assert run_realtime_capture.calculate_snapshot_count(5, 16) == 4
    assert run_realtime_capture.calculate_snapshot_count(10, 5) == 1


def test_validate_capture_config_rejects_non_positive_values():
    with pytest.raises(ValueError, match="interval-minutes"):
        run_realtime_capture.validate_capture_config(0, 15)

    with pytest.raises(ValueError, match="duration-minutes"):
        run_realtime_capture.validate_capture_config(5, 0)


def test_summarize_results_counts_attempted_succeeded_and_failed():
    summary = run_realtime_capture.summarize_results([True, False, True])

    assert summary.attempted == 3
    assert summary.succeeded == 2
    assert summary.failed == 1


def test_run_capture_window_continues_after_failed_snapshot():
    calls = []

    def fake_capture_snapshot(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("temporary feed failure")
        return {
            "vehicle_record_count": 10,
            "trip_update_record_count": 20,
        }

    sleep_calls = []

    summary = run_realtime_capture.run_capture_window(
        interval_minutes=1,
        duration_minutes=3,
        vehicle_url="https://example.com/vehicles",
        trip_updates_url="https://example.com/trips",
        output_dir="data/raw/realtime",
        timeout_seconds=30,
        capture_snapshot=fake_capture_snapshot,
        sleep=sleep_calls.append,
    )

    assert len(calls) == 3
    assert sleep_calls == [60, 60]
    assert summary.attempted == 3
    assert summary.succeeded == 2
    assert summary.failed == 1
