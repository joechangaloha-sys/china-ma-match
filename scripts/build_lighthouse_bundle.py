"""Build a clean Lighthouse upload ZIP with website, PostgreSQL and beginner installer."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
ZIP_PATH = RELEASE / "mamatch-lighthouse-demo.zip"
GUIDE_PATH = RELEASE / "mamatch-lighthouse-guide.md"
SHA_PATH = RELEASE / "mamatch-lighthouse-demo.sha256"
ROOT_FILES = [".dockerignore", "Dockerfile", "README.md", "pyproject.toml", "uv.lock"]
LIGHTHOUSE_FILES = {
    "Caddyfile": "Caddyfile",
    "compose.lighthouse.yaml": "compose.lighthouse.yaml",
    "install.sh": "install.sh",
    "show_login.sh": "show_login.sh",
    "UPLOAD_TO_LIGHTHOUSE.command": "UPLOAD_TO_LIGHTHOUSE.command",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files() -> dict[str, bytes]:
    selected = {str((ROOT / name).relative_to(ROOT)): ROOT / name for name in ROOT_FILES}
    for path in (ROOT / "src").rglob("*"):
        if path.is_file() and not any(part == "__pycache__" for part in path.parts) and path.suffix != ".pyc":
            selected[str(path.relative_to(ROOT))] = path
    for source, target in LIGHTHOUSE_FILES.items():
        selected[target] = ROOT / "deploy/lighthouse" / source
    selected["LIGHTHOUSE_UPLOAD_GUIDE.md"] = ROOT / "deploy/lighthouse/README.md"

    contents: dict[str, bytes] = {}
    for name, path in sorted(selected.items()):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"Invalid bundle source: {path}")
        if path.name == ".env" or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite"}:
            raise RuntimeError(f"Potential secret/local data selected: {path}")
        contents[name] = path.read_bytes()
    return contents


def zip_entry(archive: ZipFile, name: str, data: bytes) -> None:
    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    executable = name.endswith((".sh", ".command"))
    info.external_attr = ((0o755 if executable else 0o644) & 0xFFFF) << 16
    archive.writestr(info, data)


def main() -> None:
    RELEASE.mkdir(exist_ok=True)
    contents = source_files()
    manifest = {
        "bundle": "mamatch-lighthouse-demo",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "target": "Tencent Cloud International Lighthouse, Singapore, Ubuntu 24.04 + Docker",
        "public_ip": "43.153.223.242",
        "demo_data": "fictional only",
        "secrets": "generated on the server; none included",
        "files": {name: {"bytes": len(data), "sha256": digest(data)} for name, data in contents.items()},
    }
    contents["BUNDLE_MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    with ZipFile(ZIP_PATH, "w") as archive:
        for name, data in sorted(contents.items()):
            zip_entry(archive, name, data)
    with ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        names = set(archive.namelist())
        required = {"Dockerfile", "pyproject.toml", "Caddyfile", "compose.lighthouse.yaml", "install.sh",
                    "UPLOAD_TO_LIGHTHOUSE.command", "src/mamatch/web/app.py", "LIGHTHOUSE_UPLOAD_GUIDE.md"}
        if not required <= names:
            raise RuntimeError(f"Missing required entries: {sorted(required - names)}")
        forbidden = (".env", "DEMO_LOGIN.txt", "data/local-demo.db")
        if any(name in forbidden or name.startswith((".git/", ".venv/", "data/", "release/")) for name in names):
            raise RuntimeError("Bundle contains a forbidden local or secret file")
    GUIDE_PATH.write_bytes(contents["LIGHTHOUSE_UPLOAD_GUIDE.md"])
    zip_hash = digest(ZIP_PATH.read_bytes())
    SHA_PATH.write_text(f"{zip_hash}  {ZIP_PATH.name}\n")
    print(f"Built {ZIP_PATH} ({ZIP_PATH.stat().st_size:,} bytes, {len(contents)} files)")
    print(f"Guide {GUIDE_PATH}")
    print(f"SHA256 {zip_hash}")


if __name__ == "__main__":
    main()
