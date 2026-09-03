from datetime import UTC, datetime
import io
import importlib.util
import json
from pathlib import Path
import shutil
import uuid
import zipfile

MODULE_PATH = Path(__file__).resolve().parents[1] / "ingestion" / "download_static_gtfs.py"
SPEC = importlib.util.spec_from_file_location("download_static_gtfs", MODULE_PATH)
download_static_gtfs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(download_static_gtfs)


def make_test_workspace() -> Path:
    workspace = Path(__file__).resolve().parent / f"_tmp_download_static_gtfs_{uuid.uuid4().hex}"
    workspace.mkdir()
    return workspace


def remove_test_workspace(workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)


class FakeResponse:
    def __init__(self, content: bytes, should_fail: bool = False):
        self.content = content
        self.should_fail = should_fail

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def raise_for_status(self):
        if self.should_fail:
            raise RuntimeError("network failure")

    def iter_content(self, chunk_size):
        yield self.content


def build_zip_bytes(file_names: list[str] | None = None) -> bytes:
    file_names = file_names or [
        "routes.txt",
        "trips.txt",
        "stops.txt",
        "stop_times.txt",
    ]
    output = io.BytesIO()

    with zipfile.ZipFile(output, "w") as gtfs_zip:
        for file_name in file_names:
            gtfs_zip.writestr(file_name, "id,name\n1,example\n")

    return output.getvalue()


def fake_requests_get_factory(
    zip_bytes_by_url: dict[str, bytes],
    failing_urls: set[str] | None = None,
):
    failing_urls = failing_urls or set()

    def fake_requests_get(url, stream, timeout):
        return FakeResponse(
            zip_bytes_by_url.get(url, build_zip_bytes()),
            should_fail=url in failing_urls,
        )

    return fake_requests_get


def test_get_static_data_paths_uses_project_root():
    project_root = Path("example_project")

    paths = download_static_gtfs.get_static_data_paths(project_root)

    assert paths["static_dir"] == project_root / "data" / "raw" / "static"
    assert paths["zip_path"] == project_root / "data" / "raw" / "static" / "mta_bus_gtfs_static.zip"
    assert paths["extract_dir"] == project_root / "data" / "raw" / "static" / "extracted"
    assert paths["manifest_path"] == project_root / "data" / "raw" / "static" / "manifest.json"


def test_list_extracted_files_returns_sorted_relative_paths():
    workspace = make_test_workspace()
    try:
        extract_dir = workspace / "extracted"
        nested_dir = extract_dir / "nested"
        nested_dir.mkdir(parents=True)
        (extract_dir / "stops.txt").write_text("stop_id,stop_name\n", encoding="utf-8")
        (nested_dir / "routes.txt").write_text("route_id,route_short_name\n", encoding="utf-8")

        files = download_static_gtfs.list_extracted_files(extract_dir)

        assert files == ["nested/routes.txt", "stops.txt"]
    finally:
        remove_test_workspace(workspace)


def test_build_manifest_contains_expected_structure():
    workspace = make_test_workspace()
    downloaded_at = datetime(2026, 9, 2, 12, 30, tzinfo=UTC)
    try:
        zip_path = workspace / "mta_bus_gtfs_static.zip"
        extract_dir = workspace / "extracted"
        extracted_files = ["routes.txt", "trips.txt"]

        manifest = download_static_gtfs.build_manifest(
            source_url="https://example.com/gtfs.zip",
            zip_path=zip_path,
            extract_dir=extract_dir,
            extracted_files=extracted_files,
            downloaded_at_utc=downloaded_at,
        )

        assert manifest == {
            "source_url": "https://example.com/gtfs.zip",
            "downloaded_at_utc": "2026-09-02T12:30:00Z",
            "zip_path": str(zip_path),
            "extract_dir": str(extract_dir),
            "extracted_files": ["routes.txt", "trips.txt"],
            "file_count": 2,
            "required_files_present": False,
            "missing_required_files": ["stops.txt", "stop_times.txt"],
        }
    finally:
        remove_test_workspace(workspace)


def test_validate_required_files_catches_missing_required_files():
    required_files_present, missing_required_files = download_static_gtfs.validate_required_files(
        ["routes.txt", "trips.txt"]
    )

    assert required_files_present is False
    assert missing_required_files == ["stops.txt", "stop_times.txt"]


def test_all_six_feed_names_and_urls_are_configured():
    assert download_static_gtfs.MTA_BUS_STATIC_FEEDS == {
        "busco": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip",
        "brooklyn": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_b.zip",
        "bronx": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_bx.zip",
        "manhattan": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_m.zip",
        "queens": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_q.zip",
        "staten_island": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_si.zip",
    }


def test_existing_single_feed_behavior_still_writes_legacy_paths(monkeypatch):
    workspace = make_test_workspace()
    try:
        monkeypatch.setattr(
            download_static_gtfs.requests,
            "get",
            fake_requests_get_factory(
                {download_static_gtfs.DEFAULT_GTFS_STATIC_URL: build_zip_bytes()}
            ),
        )

        manifest = download_static_gtfs.download_legacy_single_feed(workspace)

        assert (workspace / "data" / "raw" / "static" / "mta_bus_gtfs_static.zip").exists()
        assert (workspace / "data" / "raw" / "static" / "extracted" / "routes.txt").exists()
        assert (workspace / "data" / "raw" / "static" / "manifest.json").exists()
        assert manifest["required_files_present"] is True
    finally:
        remove_test_workspace(workspace)


def test_all_feeds_creates_separate_feed_folders_and_manifests(monkeypatch):
    workspace = make_test_workspace()
    try:
        monkeypatch.setattr(
            download_static_gtfs.requests,
            "get",
            fake_requests_get_factory(
                {
                    source_url: build_zip_bytes()
                    for source_url in download_static_gtfs.MTA_BUS_STATIC_FEEDS.values()
                }
            ),
        )

        combined_manifest = download_static_gtfs.download_all_static_feeds(workspace)

        assert combined_manifest["attempted_count"] == 6
        assert combined_manifest["succeeded_count"] == 6
        assert combined_manifest["failed_count"] == 0

        for feed_name in download_static_gtfs.MTA_BUS_STATIC_FEEDS:
            feed_dir = workspace / "data" / "raw" / "static" / feed_name
            assert (feed_dir / f"{feed_name}.zip").exists()
            assert (feed_dir / "extracted" / "routes.txt").exists()
            assert (feed_dir / "manifest.json").exists()

        assert (workspace / "data" / "raw" / "static" / "manifest.json").exists()
    finally:
        remove_test_workspace(workspace)


def test_all_feeds_manifest_summarizes_failed_feed_without_stopping(monkeypatch):
    workspace = make_test_workspace()
    failing_url = download_static_gtfs.MTA_BUS_STATIC_FEEDS["bronx"]
    try:
        monkeypatch.setattr(
            download_static_gtfs.requests,
            "get",
            fake_requests_get_factory(
                {
                    source_url: build_zip_bytes()
                    for source_url in download_static_gtfs.MTA_BUS_STATIC_FEEDS.values()
                },
                failing_urls={failing_url},
            ),
        )

        combined_manifest = download_static_gtfs.download_all_static_feeds(workspace)

        assert combined_manifest["attempted_count"] == 6
        assert combined_manifest["succeeded_count"] == 5
        assert combined_manifest["failed_count"] == 1
        assert [
            result["feed_name"]
            for result in combined_manifest["feeds"]
            if result["status"] == "failed"
        ] == ["bronx"]
        assert (workspace / "data" / "raw" / "static" / "queens" / "manifest.json").exists()
    finally:
        remove_test_workspace(workspace)


def test_missing_required_files_marks_feed_failed_in_all_feeds(monkeypatch):
    workspace = make_test_workspace()
    missing_required_url = download_static_gtfs.MTA_BUS_STATIC_FEEDS["queens"]
    try:
        zip_bytes_by_url = {
            source_url: build_zip_bytes()
            for source_url in download_static_gtfs.MTA_BUS_STATIC_FEEDS.values()
        }
        zip_bytes_by_url[missing_required_url] = build_zip_bytes(["routes.txt", "trips.txt"])
        monkeypatch.setattr(
            download_static_gtfs.requests,
            "get",
            fake_requests_get_factory(zip_bytes_by_url),
        )

        combined_manifest = download_static_gtfs.download_all_static_feeds(workspace)

        failed_results = [
            result
            for result in combined_manifest["feeds"]
            if result["status"] == "failed"
        ]
        per_feed_manifest = json.loads(
            (
                workspace
                / "data"
                / "raw"
                / "static"
                / "queens"
                / "manifest.json"
            ).read_text(encoding="utf-8")
        )

        assert combined_manifest["succeeded_count"] == 5
        assert combined_manifest["failed_count"] == 1
        assert failed_results[0]["feed_name"] == "queens"
        assert "Missing required GTFS files" in failed_results[0]["error_message"]
        assert per_feed_manifest["required_files_present"] is False
        assert per_feed_manifest["missing_required_files"] == ["stops.txt", "stop_times.txt"]
    finally:
        remove_test_workspace(workspace)
