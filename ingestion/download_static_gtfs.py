from __future__ import annotations

import json
import argparse
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import requests


DEFAULT_GTFS_STATIC_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip"
ZIP_FILENAME = "mta_bus_gtfs_static.zip"
REQUEST_TIMEOUT_SECONDS = 60
REQUIRED_GTFS_FILES = ["routes.txt", "trips.txt", "stops.txt", "stop_times.txt"]
MTA_BUS_STATIC_FEEDS = {
    "busco": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip",
    "brooklyn": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_b.zip",
    "bronx": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_bx.zip",
    "manhattan": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_m.zip",
    "queens": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_q.zip",
    "staten_island": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_si.zip",
}


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_static_data_paths(project_root: Path | None = None) -> dict[str, Path]:
    root = project_root or get_project_root()
    static_dir = root / "data" / "raw" / "static"

    return {
        "static_dir": static_dir,
        "zip_path": static_dir / ZIP_FILENAME,
        "extract_dir": static_dir / "extracted",
        "manifest_path": static_dir / "manifest.json",
    }


def get_feed_data_paths(feed_name: str, project_root: Path | None = None) -> dict[str, Path]:
    root = project_root or get_project_root()
    feed_dir = root / "data" / "raw" / "static" / feed_name

    return {
        "feed_dir": feed_dir,
        "zip_path": feed_dir / f"{feed_name}.zip",
        "extract_dir": feed_dir / "extracted",
        "manifest_path": feed_dir / "manifest.json",
    }


def download_file(source_url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(source_url, stream=True, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        response.raise_for_status()

        with destination.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output_file.write(chunk)


def extract_zip(zip_path: Path, extract_dir: Path) -> None:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    resolved_extract_dir = extract_dir.resolve()

    with zipfile.ZipFile(zip_path) as gtfs_zip:
        for member in gtfs_zip.infolist():
            destination = (extract_dir / member.filename).resolve()
            if not destination.is_relative_to(resolved_extract_dir):
                raise ValueError(f"Unsafe path in GTFS zip: {member.filename}")

        gtfs_zip.extractall(extract_dir)


def list_extracted_files(extract_dir: Path) -> list[str]:
    if not extract_dir.exists():
        return []

    return sorted(
        str(path.relative_to(extract_dir)).replace("\\", "/")
        for path in extract_dir.rglob("*")
        if path.is_file()
    )


def validate_required_files(extracted_files: list[str]) -> tuple[bool, list[str]]:
    extracted_file_names = {Path(file_name).name for file_name in extracted_files}
    missing_required_files = [
        file_name
        for file_name in REQUIRED_GTFS_FILES
        if file_name not in extracted_file_names
    ]

    return len(missing_required_files) == 0, missing_required_files


def build_manifest(
    source_url: str,
    zip_path: Path,
    extract_dir: Path,
    extracted_files: list[str],
    downloaded_at_utc: datetime | None = None,
) -> dict[str, object]:
    timestamp = downloaded_at_utc or datetime.now(UTC)
    required_files_present, missing_required_files = validate_required_files(extracted_files)

    return {
        "source_url": source_url,
        "downloaded_at_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "zip_path": str(zip_path),
        "extract_dir": str(extract_dir),
        "extracted_files": extracted_files,
        "file_count": len(extracted_files),
        "required_files_present": required_files_present,
        "missing_required_files": missing_required_files,
    }


def write_manifest(manifest_path: Path, manifest: dict[str, object]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def download_static_feed(
    source_url: str,
    zip_path: Path,
    extract_dir: Path,
    manifest_path: Path,
) -> dict[str, object]:
    download_file(source_url, zip_path)
    extract_zip(zip_path, extract_dir)

    extracted_files = list_extracted_files(extract_dir)
    manifest = build_manifest(
        source_url=source_url,
        zip_path=zip_path,
        extract_dir=extract_dir,
        extracted_files=extracted_files,
    )
    write_manifest(manifest_path, manifest)

    if not manifest["required_files_present"]:
        missing_files = ", ".join(manifest["missing_required_files"])
        raise ValueError(f"Missing required GTFS files: {missing_files}")

    return manifest


def download_legacy_single_feed(project_root: Path | None = None) -> dict[str, object]:
    paths = get_static_data_paths(project_root)
    return download_static_feed(
        source_url=DEFAULT_GTFS_STATIC_URL,
        zip_path=paths["zip_path"],
        extract_dir=paths["extract_dir"],
        manifest_path=paths["manifest_path"],
    )


def build_combined_manifest(
    feed_results: list[dict[str, object]],
    run_started_at_utc: datetime | None = None,
) -> dict[str, object]:
    timestamp = run_started_at_utc or datetime.now(UTC)
    attempted_count = len(feed_results)
    succeeded_count = sum(1 for result in feed_results if result["status"] == "succeeded")
    failed_count = attempted_count - succeeded_count

    return {
        "run_started_at_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "attempted_count": attempted_count,
        "succeeded_count": succeeded_count,
        "failed_count": failed_count,
        "feeds": feed_results,
    }


def download_all_static_feeds(project_root: Path | None = None) -> dict[str, object]:
    root = project_root or get_project_root()
    feed_results: list[dict[str, object]] = []

    for feed_name, source_url in MTA_BUS_STATIC_FEEDS.items():
        paths = get_feed_data_paths(feed_name, root)
        try:
            download_static_feed(
                source_url=source_url,
                zip_path=paths["zip_path"],
                extract_dir=paths["extract_dir"],
                manifest_path=paths["manifest_path"],
            )
            feed_results.append(
                {
                    "feed_name": feed_name,
                    "source_url": source_url,
                    "status": "succeeded",
                    "manifest_path": str(paths["manifest_path"]),
                }
            )
            print(f"{feed_name}: succeeded")
        except Exception as error:
            feed_results.append(
                {
                    "feed_name": feed_name,
                    "source_url": source_url,
                    "status": "failed",
                    "error_message": str(error),
                }
            )
            print(f"{feed_name}: failed - {error}")

    combined_manifest = build_combined_manifest(feed_results)
    combined_manifest_path = root / "data" / "raw" / "static" / "manifest.json"
    write_manifest(combined_manifest_path, combined_manifest)
    return combined_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download NYC MTA bus static GTFS schedule data."
    )
    parser.add_argument(
        "--all-feeds",
        action="store_true",
        help="Download MTA Bus Company plus all NYCT bus borough static feeds.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.all_feeds:
        manifest = download_all_static_feeds()

        print("Downloaded MTA bus static GTFS feeds.")
        print(f"Attempted: {manifest['attempted_count']}")
        print(f"Succeeded: {manifest['succeeded_count']}")
        print(f"Failed: {manifest['failed_count']}")
        print(f"Output: {get_project_root() / 'data' / 'raw' / 'static'}")
        return

    paths = get_static_data_paths()
    manifest = download_legacy_single_feed()

    print("Downloaded NYC MTA bus static GTFS schedule data.")
    print(f"Zip: {paths['zip_path']}")
    print(f"Extracted files: {manifest['file_count']}")
    print(f"Manifest: {paths['manifest_path']}")


if __name__ == "__main__":
    main()
