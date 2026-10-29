"""Build a clean, root-level ZIP for Tencent CloudRun source upload.

No local databases, virtual environments, Git metadata, screenshots, credentials or research notes are included.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
ZIP_PATH = RELEASE / "mamatch-tencent-demo.zip"
GUIDE_PATH = RELEASE / "mamatch-tencent-demo-guide.md"
SHA_PATH = RELEASE / "mamatch-tencent-demo.sha256"
ROOT_FILES = [
    ".dockerignore",
    ".env.example",
    "Dockerfile",
    "README.md",
    "START_LOCAL_DEMO.command",
    "compose.demo.yaml",
    "package.json",
    "pyproject.toml",
    "uv.lock",
]
TREE_ROOTS = ["src", "tests", "scripts", "deploy/tencent-cloud"]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files() -> list[Path]:
    files = [ROOT / name for name in ROOT_FILES]
    for tree in TREE_ROOTS:
        files.extend(
            path for path in (ROOT / tree).rglob("*")
            if path.is_file()
            and not any(part in {".git", ".venv", "__pycache__", ".pytest_cache"} for part in path.parts)
            and path.suffix.lower() not in {".pyc", ".pyo"}
        )
    files = sorted(set(files))
    for path in files:
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            raise RuntimeError(f"Symlinks are not allowed in the bundle: {relative}")
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache", "data", "artifacts", "release"} for part in relative.parts):
            raise RuntimeError(f"Local/generated file selected for bundle: {relative}")
        if path.name == ".env" or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite"}:
            raise RuntimeError(f"Potential secret/local data selected for bundle: {relative}")
        if not path.is_file():
            raise RuntimeError(f"Required bundle file is missing: {relative}")
    return files


def zip_entry(archive: ZipFile, name: str, data: bytes, executable: bool = False) -> None:
    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    archive.writestr(info, data)


def main() -> None:
    RELEASE.mkdir(exist_ok=True)
    files = source_files()
    contents: dict[str, bytes] = {str(path.relative_to(ROOT)): path.read_bytes() for path in files}
    guide = (ROOT / "deploy/tencent-cloud/README.md").read_bytes()
    contents["TENCENT_UPLOAD_GUIDE.md"] = guide
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {
        "bundle": "mamatch-tencent-demo",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "source_state": "working tree including uncommitted demo deployment changes",
        "archive_layout": "application files at ZIP root; no enclosing directory",
        "demo_data": "fictional only",
        "files": {name: {"bytes": len(data), "sha256": digest(data)} for name, data in sorted(contents.items())},
    }
    contents["BUNDLE_MANIFEST.json"] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()

    with ZipFile(ZIP_PATH, "w") as archive:
        for name, data in sorted(contents.items()):
            zip_entry(archive, name, data, executable=name.endswith(".sh"))
    with ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        names = set(archive.namelist())
        required = {"Dockerfile", "pyproject.toml", "src/mamatch/web/app.py", "TENCENT_UPLOAD_GUIDE.md"}
        if not required <= names:
            raise RuntimeError(f"Bundle is missing required entries: {sorted(required - names)}")
        if any(name.startswith(("mamatch-tencent-demo/", ".git/", ".venv/", "data/", "artifacts/")) for name in names):
            raise RuntimeError("Bundle contains a forbidden prefix")

    GUIDE_PATH.write_bytes(guide)
    zip_hash = digest(ZIP_PATH.read_bytes())
    SHA_PATH.write_text(f"{zip_hash}  {ZIP_PATH.name}\n")
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size:,} bytes, {len(contents)} files)")
    print(f"Guide {GUIDE_PATH}")
    print(f"SHA256 {zip_hash}")


if __name__ == "__main__":
    main()
