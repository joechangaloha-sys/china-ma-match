import sqlite3

from sqlalchemy import select

from mamatch import db
from mamatch.models import Buyer


def test_init_db_adds_new_columns_to_an_old_database(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE buyers (id INTEGER PRIMARY KEY, name VARCHAR(200), kind VARCHAR(20), source VARCHAR(20), "
                "external_id VARCHAR(40), province VARCHAR(20), sectors JSON, target_sectors JSON, target_regions JSON, "
                "deal_size_min FLOAT, deal_size_max FLOAT, rationale TEXT, is_example BOOLEAN, updated_at DATETIME)")
    con.execute("INSERT INTO buyers (name, kind, source, external_id, province, sectors, target_sectors, target_regions,"
                " rationale, is_example) VALUES ('老买方', 'listed', 'cninfo', '600000', '', '[]', '[]', '[]', '', 0)")
    con.commit()
    con.close()

    url = f"sqlite:///{path}"
    db.init_db(url)
    with db.session_scope(url) as s:
        b = s.scalar(select(Buyer))
        assert b.status == "suggested" and b.target_deal_types == [] and b.excluded_sectors == []


def test_legacy_files_quarantined_and_sessions_invalidated(tmp_path):
    path = tmp_path / 'legacy-security.db'
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE documents (id INTEGER PRIMARY KEY, target_id INTEGER, uploaded_by INTEGER, kind VARCHAR(30), filename VARCHAR(200), stored_path VARCHAR(300), content_type VARCHAR(100), size INTEGER, sha256 VARCHAR(64), text TEXT, in_data_room BOOLEAN, created_at DATETIME)')
    con.execute("INSERT INTO documents (id, target_id, filename, stored_path) VALUES (1, 1, 'old.txt', '/old.txt')")
    con.execute('CREATE TABLE user_sessions (token VARCHAR(64) PRIMARY KEY, user_id INTEGER, created_at DATETIME, expires_at DATETIME)')
    con.execute("INSERT INTO user_sessions VALUES ('old-token', 1, '2026-10-01', '2026-12-01')")
    con.commit(); con.close()
    url = f'sqlite:///{path}'
    db.init_db(url)
    from mamatch.models import Document, UserSession
    with db.session_scope(url) as s:
        doc = s.get(Document, 1)
        assert doc.security_status == 'quarantined' and doc.scanned_sha256 == ''
        assert s.get(UserSession, 'old-token').last_seen_at is None
