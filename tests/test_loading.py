import sqlite3
from pathlib import Path

import pytest

from teiko import db
from teiko.loading import build_database

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "tiny.csv"


@pytest.fixture
def real_db(tmp_path):
    path = tmp_path / "test.db"
    build_database(path, ROOT / "cell-count.csv")
    conn = db.connect(path)
    yield conn
    conn.close()


def row_counts(conn):
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("projects", "populations", "subjects", "samples", "cell_counts")
    }


def test_loader_writes_expected_row_counts(real_db):
    assert row_counts(real_db) == {
        "projects": 3,
        "populations": 5,
        "subjects": 3500,
        "samples": 10500,
        "cell_counts": 52500,
    }


def test_loading_twice_does_not_duplicate(tmp_path):
    path = tmp_path / "test.db"
    build_database(path, ROOT / "cell-count.csv")
    with db.connect(path) as first:
        before = row_counts(first)
    build_database(path, ROOT / "cell-count.csv")
    with db.connect(path) as second:
        assert row_counts(second) == before


def test_blank_responses_become_null_and_never_join_a_group(real_db):
    nulls = real_db.execute(
        "SELECT COUNT(*) FROM subjects WHERE response IS NULL"
    ).fetchone()[0]
    empty_strings = real_db.execute(
        "SELECT COUNT(*) FROM subjects WHERE response = ''"
    ).fetchone()[0]
    grouped = real_db.execute(
        "SELECT COUNT(*) FROM subjects WHERE response IN ('yes', 'no')"
    ).fetchone()[0]

    assert nulls == 474          # 1422 healthy rows / 3 samples per subject
    assert empty_strings == 0
    assert nulls + grouped == 3500


def test_foreign_keys_are_enforced_on_every_connection(tmp_path):
    path = tmp_path / "test.db"
    build_database(path, FIXTURE)
    conn = db.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cell_counts (sample_id, population, count)"
            " VALUES ('no_such_sample', 'b_cell', 1)"
        )
    conn.close()
