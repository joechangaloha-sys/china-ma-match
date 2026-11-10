"""Local-only backup of snapshot-referenced immutable uploads."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
from . import config


def export_referenced(refs, root, output):
    root=Path(root).resolve()
    with tarfile.open(fileobj=output,mode='w|') as archive:
        for ref in refs:
            original=Path(ref['path']);path=original.resolve()
            if original.is_symlink() or not path.is_relative_to(root) or not path.is_file():
                raise RuntimeError('Invalid document path')
            if path.stat().st_size>20*1024*1024:raise RuntimeError('Document exceeds backup file limit')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=ref['sha256']:raise RuntimeError('Source document integrity failure')
            info=tarfile.TarInfo(str(path.relative_to(root)));info.size=len(data);info.mode=0o600
            archive.addfile(info,io.BytesIO(data))


if __name__=='__main__':
    export_referenced(json.load(sys.stdin),config.UPLOAD_DIR,sys.stdout.buffer)
