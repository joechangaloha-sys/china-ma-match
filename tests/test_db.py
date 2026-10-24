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
