#!/usr/bin/env python3
"""Build one KiCad PCM package release and regenerate repository indexes.

Tag convention: <package-folder-slug>/v<major>.<minor>.<patch>
Example: sfr-tools/v1.2.0 releases src/SFR-Tools.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
VERSION_RE = re.compile(r"^(?P<slug>.+)/v(?P<version>\d{1,4}(?:\.\d{1,4}){1,2})$")
DOWNLOAD_FIELDS = {"download_url", "download_sha256", "download_size", "install_size"}


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_size(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


def find_package(slug: str) -> Path:
    candidates = [
        p for p in SRC.iterdir()
        if p.is_dir() and (slugify(p.name) == slug.casefold())
        and (p / "metadata.json").is_file()
    ]
    if len(candidates) != 1:
        available = ", ".join(
            f"{p.name} (tag slug: {slugify(p.name)})"
            for p in SRC.iterdir() if p.is_dir() and (p / "metadata.json").is_file()
        )
        raise SystemExit(
            f"Expected exactly one package folder matching tag slug '{slug}', "
            f"found {len(candidates)}. Available packages: {available}"
        )
    return candidates[0]


def build_resources_archive(output: Path) -> bool:
    """Build repository-level icons archive: <package identifier>/icon.png."""
    icons = []
    for package_dir in sorted(SRC.iterdir()):
        metadata_path = package_dir / "metadata.json"
        icon_path = package_dir / "resources" / "icon.png"
        if not package_dir.is_dir() or not metadata_path.is_file() or not icon_path.is_file():
            continue
        metadata = read_json(metadata_path)
        identifier = metadata.get("identifier")
        if not identifier:
            print(f"Warning: skipping icon without package identifier: {metadata_path}")
            continue
        icons.append((icon_path, f"{identifier}/icon.png"))

    if not icons:
        if output.exists():
            output.unlink()
        print("No package icons found; resources.zip will not be published.")
        return False

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for icon_path, archive_path in icons:
            archive.write(icon_path, archive_path)
    print(f"Built repository icon archive with {len(icons)} icon(s): {output}")
    return True


def zip_package(package_dir: Path, output: Path, metadata: dict) -> int:
    """Zip package contents at archive root; strip repository-only download fields."""
    staging = output.parent / "_package_staging"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(
        package_dir,
        staging,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".DS_Store"),
    )

    staged_metadata = copy.deepcopy(metadata)
    for version in staged_metadata.get("versions", []):
        for field in DOWNLOAD_FIELDS:
            version.pop(field, None)
    write_json(staging / "metadata.json", staged_metadata)

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, PurePosixPath(path.relative_to(staging)).as_posix())
    install_size = tree_size(staging)
    shutil.rmtree(staging)
    return install_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repository", required=True, help="owner/repo")
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--output-dir", default="dist")
    args = parser.parse_args()

    match = VERSION_RE.fullmatch(args.tag)
    if not match:
        raise SystemExit(
            f"Invalid tag '{args.tag}'. Use <package-folder-slug>/v1.2.0, "
            "e.g. sfr-tools/v1.2.0."
        )
    slug, version = match.group("slug"), match.group("version")
    package_dir = find_package(slug)
    metadata_path = package_dir / "metadata.json"
    source_metadata = read_json(metadata_path)
    identifier = source_metadata.get("identifier")
    if not identifier:
        raise SystemExit(f"{metadata_path} has no 'identifier' field.")

    output_dir = (ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"{identifier}_{version}_pcm.zip"
    archive_path = output_dir / archive_name
    release_url = (
        f"https://github.com/{args.repository}/releases/download/"
        f"{args.tag}/{archive_name}"
    )

    # Use the version's existing compatibility/status values as a template.
    old_versions = source_metadata.get("versions", [])
    template = copy.deepcopy(next(
        (v for v in old_versions if isinstance(v, dict)), {}
    ))
    for field in DOWNLOAD_FIELDS:
        template.pop(field, None)
    template["version"] = version
    template.setdefault("status", "stable")
    template.setdefault("kicad_version", "10.0")

    # GitHub marks testing/development builds as prereleases. A deprecated
    # release is not automatically a prerelease: that status describes support
    # state, not release maturity.
    status = str(template["status"]).strip().casefold()
    if status not in {"stable", "testing", "development", "deprecated"}:
        raise SystemExit(
            f"Unsupported metadata status '{template['status']}'. Expected "
            "stable, testing, development, or deprecated."
        )
    prerelease = status in {"testing", "development"}
    import os
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            output.write(f"prerelease={'true' if prerelease else 'false'}\n")
    print(f"Metadata status: {status}; GitHub prerelease: {prerelease}")

    # Keep only the newly released version inside the installable archive.
    source_metadata["versions"] = [template]
    write_json(metadata_path, source_metadata)

    install_size = zip_package(package_dir, archive_path, source_metadata)
    archive_size = archive_path.stat().st_size
    archive_hash = sha256_file(archive_path)

    # packages.json is the repository index and stores all published versions.
    packages_path = ROOT / "packages.json"
    if packages_path.exists():
        packages_doc = read_json(packages_path)
        packages = packages_doc.get("packages", [])
    else:
        packages_doc = {"$schema": "https://go.kicad.org/pcm/schemas/v2#/definitions/PackageArray",
                        "packages": []}
        packages = []

    existing = next(
        (p for p in packages if p.get("identifier") == identifier), None
    )
    if existing is None:
        existing = copy.deepcopy(source_metadata)
        existing["versions"] = []
        packages.append(existing)
    else:
        # Refresh descriptive metadata while retaining all previously released versions.
        retained_versions = existing.get("versions", [])
        for key, value in source_metadata.items():
            if key != "versions":
                existing[key] = copy.deepcopy(value)
        existing["versions"] = retained_versions

    versions = existing.setdefault("versions", [])
    if any(v.get("version") == version for v in versions):
        raise SystemExit(
            f"{identifier} version {version} is already in packages.json. "
            "Use a new version tag; releases are immutable."
        )

    release_version = copy.deepcopy(template)
    release_version.update({
        "download_url": release_url,
        "download_sha256": archive_hash,
        "download_size": archive_size,
        "install_size": install_size,
    })
    versions.append(release_version)
    # Keep history; display newest versions first using numeric version components.
    versions.sort(
        key=lambda v: tuple(int(part) for part in v.get("version", "0").split(".")),
        reverse=True,
    )
    packages.sort(key=lambda p: p.get("identifier", ""))

    packages_doc["packages"] = packages
    packages_doc.setdefault(
        "$schema", "https://go.kicad.org/pcm/schemas/v2#/definitions/PackageArray"
    )
    write_json(packages_path, packages_doc)

    # KiCad reads repository-list icons from a separate resources.zip. Each
    # icon is stored as <package identifier>/icon.png inside that archive.
    resources_path = ROOT / "resources.zip"
    has_resources = build_resources_archive(resources_path)

    # repository.json hashes the exact bytes of each published resource.
    packages_bytes = packages_path.read_bytes()
    timestamp = int(time.time())
    now_utc = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    repository_path = ROOT / "repository.json"
    repository_doc = {
        "$schema": "https://go.kicad.org/pcm/schemas/v2#/definitions/Repository",
        "name": "Sheffield Formula Racing KiCad Add-ons",
        "maintainer": {
            "name": "Sheffield Formula Racing",
            "contact": {"web": "https://github.com/sheffracing"}
        },
        "schema_version": 2,
        "packages": {
            "url": f"https://raw.githubusercontent.com/{args.repository}/{args.default_branch}/packages.json",
            "sha256": hashlib.sha256(packages_bytes).hexdigest(),
            "update_timestamp": timestamp,
            "update_time_utc": now_utc,
        },
    }
    if has_resources:
        repository_doc["resources"] = {
            "url": f"https://raw.githubusercontent.com/{args.repository}/{args.default_branch}/resources.zip",
            "sha256": sha256_file(resources_path),
            "update_timestamp": timestamp,
            "update_time_utc": now_utc,
        }
    write_json(repository_path, repository_doc)

    print(f"Package folder: {package_dir.relative_to(ROOT)}")
    print(f"Package identifier: {identifier}")
    print(f"Version: {version}")
    print(f"Archive: {archive_path}")
    print(f"Download URL: {release_url}")
    print("Updated: metadata.json, packages.json, repository.json, resources.zip")


if __name__ == "__main__":
    main()
