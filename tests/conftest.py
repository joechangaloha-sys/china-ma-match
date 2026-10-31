import os

os.environ["MAMATCH_LLM"] = "off"  # tests never call Claude

import pytest

from mamatch import db
from mamatch.seed import seed


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    db.init_db(url)
    return url


@pytest.fixture
def session(db_url):
    with db.session_scope(db_url) as s:
        yield s


@pytest.fixture
def seeded(session):
    seed(session)
    return session


@pytest.fixture
def clean_file(tmp_path, monkeypatch):
    """Trusted fixture for tests of other gates; scanner behavior has separate tests."""
    import hashlib
    from mamatch import config
    monkeypatch.setattr(config, 'UPLOAD_DIR', str(tmp_path))
    def make(doc):
        path = tmp_path / (str(id(doc)) + '.txt')
        path.write_bytes(b'Test fixture evidence')
        doc.stored_path = str(path)
        doc.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        doc.scanned_sha256 = doc.sha256
        doc.security_status = 'clean'
        return doc
    return make
