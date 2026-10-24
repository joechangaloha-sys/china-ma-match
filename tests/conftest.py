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
