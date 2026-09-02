from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import requests


DEFAULT_GTFS_STATIC_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_busco.zip"
ZIP_FILENAME = "mta_bus_gtfs_static.zip"
REQUEST_TIMEOUT_SECONDS = 60


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


def download_file(source_url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(source_url, stream=True, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        response.raise_for_status()

        with destination.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output_file.write(chunk)


def extract_zip(zip_path: Path, extract_dir: Path) -> None:
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


def build_manifest(
    source_url: str,
    zip_path: Path,
    extract_dir: Path,
    extracted_files: list[str],
    downloaded_at_utc: datetime | None = None,
) -> dict[str, object]:
    timestamp = downloaded_at_utc or datetime.now(UTC)

    return {
        "source_url": source_url,
        "downloaded_at_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "zip_path": str(zip_path),
        "extract_dir": str(extract_dir),
        "extracted_files": extracted_files,
        "file_count": len(extracted_files),
    }


def write_manifest(manifest_path: Path, manifest: dict[str, object]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    paths = get_static_data_paths()

    download_file(DEFAULT_GTFS_STATIC_URL, paths["zip_path"])
    extract_zip(paths["zip_path"], paths["extract_dir"])

    extracted_files = list_extracted_files(paths["extract_dir"])
    manifest = build_manifest(
        source_url=DEFAULT_GTFS_STATIC_URL,
        zip_path=paths["zip_path"],
        extract_dir=paths["extract_dir"],
        extracted_files=extracted_files,
    )
    write_manifest(paths["manifest_path"], manifest)

    print("Downloaded NYC MTA bus static GTFS schedule data.")
    print(f"Zip: {paths['zip_path']}")
    print(f"Extracted files: {len(extracted_files)}")
    print(f"Manifest: {paths['manifest_path']}")


if __name__ == "__main__":
    main()
