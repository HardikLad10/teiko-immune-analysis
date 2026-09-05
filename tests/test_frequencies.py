from pathlib import Path

import pytest

from teiko import db
from teiko.frequencies import summary_table
from teiko.loading import build_database

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "tiny.csv"


@pytest.fixture
def fixture_db(tmp_path):
    path = tmp_path / "tiny.db"
    build_database(path, FIXTURE)
    conn = db.connect(path)
    yield conn
    conn.close()


@pytest.fixture
def real_db(tmp_path):
    path = tmp_path / "real.db"
    build_database(path, ROOT / "cell-count.csv")
    conn = db.connect(path)
    yield conn
    conn.close()


def test_percentages_match_hand_computed_values(fixture_db):
    frame = summary_table(fixture_db)
    first = frame[frame["sample"] == "sampleT0"].set_index("population")

    # sampleT0 totals 100 cells, so each percentage equals its count.
    assert first.loc["b_cell", "total_count"] == 100
    assert first.loc["b_cell", "percentage"] == pytest.approx(10.0)
    assert first.loc["cd8_t_cell", "percentage"] == pytest.approx(20.0)
    assert first.loc["cd4_t_cell", "percentage"] == pytest.approx(30.0)
    assert first.loc["nk_cell", "percentage"] == pytest.approx(20.0)
    assert first.loc["monocyte", "percentage"] == pytest.approx(20.0)

    # sampleT1 is five populations of one cell each.
    second = frame[frame["sample"] == "sampleT1"]
    assert second["total_count"].unique().tolist() == [5]
    assert second["percentage"].tolist() == pytest.approx([20.0] * 5)


def test_population_order_is_fixed_not_alphabetical(fixture_db):
    frame = summary_table(fixture_db)
    order = frame[frame["sample"] == "sampleT0"]["population"].tolist()
    assert order == ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


def test_every_sample_percentages_sum_to_one_hundred(real_db):
    frame = summary_table(real_db)
    assert len(frame) == 52_500
    totals = frame.groupby("sample")["percentage"].sum()
    assert len(totals) == 10_500
    assert totals.min() == pytest.approx(100.0)
    assert totals.max() == pytest.approx(100.0)
