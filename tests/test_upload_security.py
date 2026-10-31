import io
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from mamatch import auth, config, documents, upload_security
from mamatch.models import Document, Target, User, UserSession


@pytest.mark.parametrize('ext,data', [('.pdf', b'fake pdf'), ('.jpg', b'MZ fake'), ('.png', b'fake'),
    ('.csv', b'hello\x00world'), ('.txt', b'\x01'), ('.docx', b'not zip'),
    ('.pdf', b'%PDF-1.4\n/JavaScript test\n%%EOF')])
def test_spoofed_formats_rejected(ext, data):
    with pytest.raises(ValueError):
        upload_security.validate(ext, data)


def office(extra_name='', extra=b''):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', '<document/>')
        if extra_name:
            z.writestr(extra_name, extra)
    return data.getvalue()


@pytest.mark.parametrize('name,body', [('word/vbaProject.bin', b'x'), ('../escape', b'x'),
    ('word/_rels/document.xml.rels', b'<Relationship TargetMode="External"/>'),
    ('word/embeddings/item.bin', b'x'),
    ('word/_rels/other.rels', b"<Relationship TargetMode = 'External'/>")])
def test_unsafe_office_packages_rejected(name, body):
    with pytest.raises(ValueError):
        upload_security.validate('.docx', office(name, body))


def test_supported_formats_validate():
    upload_security.validate('.docx', office())
    upload_security.validate('.txt', '营业收入'.encode())
    upload_security.validate('.pdf', b'%PDF-1.7\nfictional\n%%EOF')


def test_quarantine_and_fail_closed_scanning(seeded, tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(config, 'CLAMSCAN_PATH', '')
    manager = seeded.scalar(select(User).where(User.role == 'deal_manager'))
    target = seeded.scalar(select(Target).limit(1))
    doc = documents.save(seeded, target, manager, 'financials', '../statement.txt', b'revenue 2025 100')
    assert doc.filename == 'statement.txt' and not doc.text and not upload_security.usable(doc)
    assert 'quarantine' in doc.stored_path
    assert documents.scan(seeded, doc, manager) == 'error'
    assert not upload_security.usable(doc)
    with pytest.raises(ValueError):
        documents.extract(seeded, doc, manager)
    monkeypatch.setattr(config, 'CLAMSCAN_PATH', '/trusted/clamscan')
    seen = []
    original_run = subprocess.run
    def run(args, **kwargs):
        if args[0] != config.CLAMSCAN_PATH:
            return original_run(args, **kwargs)
        seen.extend(args)
        assert kwargs['timeout'] == 60 and 'shell' not in kwargs
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(upload_security.subprocess, 'run', run)
    assert documents.scan(seeded, doc, manager) == 'clean'
    assert '--fail-if-cvd-older-than=2' in seen and '--alert-exceeds-max=yes' in seen
    assert upload_security.usable(doc) and doc.text
    from pathlib import Path
    Path(doc.stored_path).write_bytes(b'replaced')
    assert not upload_security.usable(doc)
    assert documents.scan(seeded, doc, manager) == 'error'
    assert not doc.text and not doc.scanned_sha256


@pytest.mark.parametrize('result', [1, 2, 'timeout'])
def test_scan_threat_error_timeout_never_releases(seeded, clean_file, monkeypatch, result):
    doc = clean_file(Document(target_id=1, kind='other', filename='x.txt'))
    monkeypatch.setattr(config, 'CLAMSCAN_PATH', '/trusted/clamscan')
    def run(*args, **kwargs):
        if result == 'timeout':
            raise subprocess.TimeoutExpired('clamscan', 60)
        return subprocess.CompletedProcess(args, result)
    monkeypatch.setattr(upload_security.subprocess, 'run', run)
    assert upload_security.scan(doc) in {'infected', 'error'}


def test_sessions_idle_absolute_expiry_and_revocation(seeded):
    user = seeded.scalar(select(User).where(User.role == 'deal_manager'))
    other = seeded.scalar(select(User).where(User.role == 'buyer'))
    first, second = auth.start_session(seeded, user), auth.start_session(seeded, user)
    other_token = auth.start_session(seeded, other)
    seeded.flush()
    assert auth.user_for_token(seeded, first) == user
    seeded.get(UserSession, first).last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    assert auth.user_for_token(seeded, first) is None
    seeded.get(UserSession, second).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert auth.user_for_token(seeded, second) is None
    fresh = auth.start_session(seeded, user); seeded.flush()
    auth.end_all_sessions(seeded, user)
    assert auth.user_for_token(seeded, fresh) is None
    assert auth.user_for_token(seeded, other_token) == other


def test_failed_signin_limit_counts_ten_attempts_once(seeded):
    from mamatch.models import AuditEvent
    from mamatch.seed import DEMO_PASSWORD
    user = seeded.scalar(select(User).where(User.role == 'deal_manager'))
    for _ in range(9):
        assert auth.authenticate(seeded, user.email, 'incorrect') is None
    assert auth.authenticate(seeded, user.email, DEMO_PASSWORD) == user
    assert auth.authenticate(seeded, user.email, 'incorrect') is None
    assert auth.authenticate(seeded, user.email, DEMO_PASSWORD) is None
    failures = seeded.scalars(select(AuditEvent).where(AuditEvent.action == 'sign_in_failed')).all()
    assert len(failures) == 10
    for event in failures:
        event.created_at = datetime.now(timezone.utc) - timedelta(minutes=16)
    assert auth.authenticate(seeded, user.email, DEMO_PASSWORD) == user
