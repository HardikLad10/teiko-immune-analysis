"""Dashboard text and metrics must come from generated files, not literals."""
from pathlib import Path

import pandas as pd
import pytest

from teiko.display import (
    read_dashboard_metrics,
    responder_figure_title,
    response_banner,
    write_dashboard_metrics,
)

ROOT = Path(__file__).resolve().parent.parent


def _stats(*, p_cd4, q_cd4, significant_cd4, p_welch=0.01, q_subject=0.2):
    return pd.DataFrame(
        {
            "population": ["b_cell", "cd4_t_cell"],
            "p_value": [0.4, p_cd4],
            "q_value": [0.4, q_cd4],
            "significant": [False, significant_cd4],
            "p_value_welch": [0.3, p_welch],
            "q_value_subject_means": [0.4, q_subject],
        }
    )


def test_response_banner_uses_table_p_and_q():
    text = response_banner(_stats(p_cd4=0.0133, q_cd4=0.0667, significant_cd4=False))
    assert "0.0133" in text
    assert "0.0667" in text
    assert "not significant" in text.lower() or "no population" in text.lower()


def test_response_banner_changes_when_the_table_changes():
    quiet = response_banner(_stats(p_cd4=0.4, q_cd4=0.8, significant_cd4=False))
    loud = response_banner(
        _stats(p_cd4=0.001, q_cd4=0.01, significant_cd4=True, q_subject=0.01)
    )
    assert quiet != loud
    assert "0.001" in loud
    assert "cd4_t_cell" in loud


def test_responder_figure_title_follows_the_significant_flag():
    none = responder_figure_title(_stats(p_cd4=0.2, q_cd4=0.3, significant_cd4=False))
    hit = responder_figure_title(_stats(p_cd4=0.001, q_cd4=0.01, significant_cd4=True))
    assert "no population differs" in none.lower()
    assert "cd4_t_cell" in hit
    assert none != hit


def test_dashboard_metrics_round_trip(tmp_path):
    path = tmp_path / "dashboard_metrics.csv"
    write_dashboard_metrics(
        path,
        {"projects": 3, "subjects": 3500, "samples": 10500, "cell_counts": 52500},
        cohort_a_samples=656,
        cohort_b_samples=485,
        cohort_b_b_cell_mean=10206.15,
    )
    metrics = read_dashboard_metrics(tmp_path)
    assert metrics["subjects"] == 3500
    assert metrics["cohort_a_samples"] == 656
    assert metrics["cohort_b_b_cell_mean"] == pytest.approx(10206.15)


def test_app_source_does_not_embed_result_literals():
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    for needle in (
        "10206.15",
        "0.0133",
        "0.0667",
        "3500",
        "10500",
        "52500",
        '"656"',
        "'656'",
    ):
        assert needle not in text, f"app.py still embeds {needle}"
