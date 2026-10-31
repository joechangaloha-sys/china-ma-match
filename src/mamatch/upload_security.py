"""Conservative format validation and fail-closed local scanning; no external transfers."""
import hashlib
import io
import re
import subprocess
import zipfile
from pathlib import Path
from . import config

LABELS = {'quarantined': '隔离待检 Quarantined', 'clean': '扫描通过 Scan passed',
          'infected': '检测到风险 Threat detected', 'error': '扫描未完成 Scan incomplete'}


def validate(ext, data):
    invalid = '文件内容与格式不符或包含不支持的内容 File format is invalid or contains unsupported content.'
    if ext == '.pdf':
        if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-2048:]:
            raise ValueError(invalid)
        if any(x.lower() in data.lower() for x in (b'/JavaScript', b'/JS', b'/Launch', b'/EmbeddedFile', b'/Encrypt')):
            raise ValueError(invalid)
    elif ext == '.png':
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError(invalid)
    elif ext in {'.jpg', '.jpeg'}:
        if not data.startswith(b'\xff\xd8\xff') or not data.endswith(b'\xff\xd9'):
            raise ValueError(invalid)
    elif ext in {'.txt', '.csv'}:
        if b'\x00' in data or any(b < 9 or 13 < b < 32 for b in data):
            raise ValueError(invalid)
        try:
            data.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                data.decode('gb18030')
            except UnicodeDecodeError:
                raise ValueError(invalid)
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(x.file_size for x in entries) > 80 * 1024 * 1024:
                    raise ValueError(invalid)
                names = {x.filename for x in entries}
                required = 'word/document.xml' if ext == '.docx' else 'xl/workbook.xml'
                if len(names) != len(entries) or required not in names or '[Content_Types].xml' not in names:
                    raise ValueError(invalid)
                for x in entries:
                    name = x.filename.lower()
                    if (x.flag_bits & 1 or name.startswith(('/', '\\')) or '..' in name.split('/')
                            or '\\' in name or any(k in name for k in ('vbaproject', 'embeddings/', 'activex/'))
                            or x.file_size > 20 * 1024 * 1024
                            or x.file_size > max(x.compress_size, 1) * 200):
                        raise ValueError(invalid)
                    if name.endswith(('.rels', '.xml')):
                        body = archive.read(x).lower()
                        if re.search(rb'''targetmode\s*=\s*["']external["']''', body) or any(k in body for k in (b'macroenabled', b'<!entity', b'<!doctype')):
                            raise ValueError(invalid)
        except (zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError):
            raise ValueError(invalid)


def verified_path(doc):
    root = Path(config.UPLOAD_DIR).resolve()
    path = Path(doc.stored_path)
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('文件不可用 File unavailable.')
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('文件不可用 File unavailable.')
    if hashlib.sha256(path.read_bytes()).hexdigest() != doc.sha256:
        raise ValueError('文件校验失败 File integrity check failed.')
    return path


def usable(doc):
    if doc.security_status != 'clean' or doc.scanned_sha256 != doc.sha256:
        return False
    try:
        verified_path(doc)
        return True
    except (ValueError, OSError):
        return False


def scan(doc):
    """ClamAV exit 0 only; unavailable/outdated/error results never release a file."""
    path = verified_path(doc)
    validate(path.suffix.lower(), path.read_bytes())
    if not config.CLAMSCAN_PATH:
        return 'error'
    try:
        result = subprocess.run([config.CLAMSCAN_PATH, '--no-summary', '--fail-if-cvd-older-than=2',
                                 '--alert-exceeds-max=yes', '--alert-encrypted=yes', '--max-filesize=20M',
                                 '--max-scansize=80M', '--max-recursion=10', '--', str(path)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
                                check=False)
        verified_path(doc)
        return {0: 'clean', 1: 'infected'}.get(result.returncode, 'error')
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return 'error'
