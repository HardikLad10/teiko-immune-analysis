from pathlib import Path

import pytest

from teiko import db
from teiko.loading import build_database
from teiko.subsets import (
    baseline_breakdowns,
    baseline_cohort,
    melanoma_male_baseline_b_cell_mean,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("subsets") / "real.db"
    build_database(path, ROOT / "cell-count.csv")
    conn = db.connect(path)
    yield conn
    conn.close()


def test_cohort_a_size(real_db):
    cohort = baseline_cohort(real_db)
    assert len(cohort) == 656
    assert cohort["subject"].nunique() == 656


def test_cohort_a_breakdowns_including_the_empty_project(real_db):
    frame = baseline_breakdowns(real_db)

    projects = frame[frame["breakdown"] == "project"].set_index("category")
    assert projects.loc["prj1", "count"] == 384
    assert projects.loc["prj2", "count"] == 0   # must be present, not omitted
    assert projects.loc["prj3", "count"] == 272
    assert (projects["unit"] == "samples").all()

    response = frame[frame["breakdown"] == "response"].set_index("category")
    assert response.loc["yes", "count"] == 331
    assert response.loc["no", "count"] == 325
    assert (response["unit"] == "subjects").all()

    sex = frame[frame["breakdown"] == "sex"].set_index("category")
    assert sex.loc["M", "count"] == 344
    assert sex.loc["F", "count"] == 312
    assert (sex["unit"] == "subjects").all()


def test_cohort_b_drops_the_pbmc_and_miraclib_filters(real_db):
    """Guards the filter trap. Keeping those filters gives 184 and 10401.28."""
    n, mean = melanoma_male_baseline_b_cell_mean(real_db)
    assert n == 485
    assert round(mean, 2) == 10206.15
