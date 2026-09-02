from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import shutil
import uuid


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
        }
    finally:
        remove_test_workspace(workspace)
