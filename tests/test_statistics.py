from pathlib import Path

import pytest

from teiko import db
from teiko.loading import build_database
from teiko.statistics import (
    benjamini_hochberg,
    cliffs_delta,
    compare_responders,
    magnitude,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("stats") / "real.db"
    build_database(path, ROOT / "cell-count.csv")
    conn = db.connect(path)
    yield conn
    conn.close()


def test_identical_groups_are_not_significant():
    from teiko.statistics import mann_whitney

    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    _, p = mann_whitney(values, list(values))
    assert p > 0.9


def test_clearly_separated_groups_are_significant():
    from teiko.statistics import mann_whitney

    low = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    high = [21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0]
    _, p = mann_whitney(low, high)
    assert p < 0.05


def test_cliffs_delta_and_magnitude_bands():
    low = [1.0, 2.0, 3.0, 4.0]
    high = [11.0, 12.0, 13.0, 14.0]
    assert cliffs_delta(low, high) == pytest.approx(-1.0)
    assert cliffs_delta(high, low) == pytest.approx(1.0)
    assert cliffs_delta(low, list(low)) == pytest.approx(0.0)
    assert magnitude(0.10) == "negligible"
    assert magnitude(0.20) == "small"
    assert magnitude(0.40) == "medium"
    assert magnitude(0.60) == "large"


def test_benjamini_hochberg_on_known_values():
    # Classic worked example: five p-values, m/k scaling, enforced monotone.
    raw = [0.01, 0.02, 0.03, 0.04, 0.05]
    adjusted = benjamini_hochberg(raw)
    assert adjusted == pytest.approx([0.05, 0.05, 0.05, 0.05, 0.05])

    assert benjamini_hochberg([0.001, 0.5]) == pytest.approx([0.002, 0.5])
    assert benjamini_hochberg([0.04]) == pytest.approx([0.04])


def test_no_population_is_significant_in_the_real_cohort(real_db):
    frame = compare_responders(real_db).set_index("population")

    assert sorted(frame["n_responder"].unique()) == [993]
    assert sorted(frame["n_non_responder"].unique()) == [975]
    assert not frame["significant"].any()
    assert frame["q_value"].min() > 0.05
    assert frame["cliffs_delta"].abs().max() < 0.147
    assert (frame["effect_magnitude"] == "negligible").all()


def test_cd4_is_the_trap_and_correction_defuses_it(real_db):
    frame = compare_responders(real_db).set_index("population")
    cd4 = frame.loc["cd4_t_cell"]

    # Uncorrected this reads as a finding; corrected it does not.
    assert cd4["p_value"] < 0.05
    assert cd4["q_value"] > 0.05


def test_both_figures_render_with_five_panels(real_db):
    from teiko.plots import responder_boxplots, timepoint_boxplots

    main = responder_boxplots(real_db)
    assert len(main.axes) == 5

    faceted = timepoint_boxplots(real_db)
    assert len(faceted.axes) == 15  # five populations by three timepoints
