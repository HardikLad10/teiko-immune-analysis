"""Turn generated tables into dashboard sentences and metric cards."""
from pathlib import Path

import pandas as pd

METRICS_NAME = "dashboard_metrics.csv"


def write_dashboard_metrics(
    path: Path,
    counts: dict[str, int],
    cohort_a_samples: int,
    cohort_b_samples: int,
    cohort_b_b_cell_mean: float,
) -> None:
    rows = [{ "key": key, "value": value } for key, value in counts.items()]
    rows.extend(
        [
            {"key": "cohort_a_samples", "value": cohort_a_samples},
            {"key": "cohort_b_samples", "value": cohort_b_samples},
            {"key": "cohort_b_b_cell_mean", "value": cohort_b_b_cell_mean},
        ]
    )
    pd.DataFrame(rows).to_csv(path, index=False)


def read_dashboard_metrics(outputs_dir: Path) -> dict:
    frame = pd.read_csv(outputs_dir / METRICS_NAME)
    out = {}
    for row in frame.itertuples(index=False):
        key = row.key
        value = float(row.value)
        if key == "cohort_b_b_cell_mean":
            out[key] = value
        else:
            out[key] = int(value)
    return out


def response_banner(table: pd.DataFrame) -> str:
    if "q_value_subject_means" in table.columns:
        subject_hits = table.loc[
            table["q_value_subject_means"] < 0.05, "population"
        ].tolist()
        qmin = float(table["q_value_subject_means"].min())
    else:
        subject_hits = []
        qmin = None

    if subject_hits:
        lead = (
            "Conclusion (one mean per subject): significant after "
            f"Benjamini-Hochberg: {', '.join(subject_hits)}."
        )
    else:
        lead = (
            "Conclusion (one mean per subject): no population differs "
            "significantly after Benjamini-Hochberg across the five "
            "populations."
        )
        if qmin is not None:
            lead += f" Smallest subject-mean q = {qmin:.4f}."

    indexed = table.set_index("population")
    extra = ""
    if "cd4_t_cell" in indexed.index:
        cd4 = indexed.loc["cd4_t_cell"]
        extra = (
            f" Pooled-sample tests are exploratory (three rows per subject; "
            f"independence is not met). CD4 pooled Mann-Whitney p = "
            f"{float(cd4['p_value']):.4f}, q = {float(cd4['q_value']):.4f}. "
            f"Welch p on those rows is {float(cd4['p_value_welch']):.4f}."
        )
    return lead + extra


def timepoint_correction_note() -> str:
    return (
        "Benjamini-Hochberg is applied to the five populations within each "
        "timepoint. It is not applied to all fifteen tests together."
    )


def responder_figure_title(table: pd.DataFrame) -> str:
    hits = table.loc[table["significant"], "population"].tolist()
    if hits:
        return (
            "Exploratory pooled samples — melanoma, miraclib, PBMC — "
            "significant after correction: " + ", ".join(hits)
        )
    return (
        "Exploratory pooled samples — melanoma, miraclib, PBMC — "
        "no population differs significantly after correction"
    )


def timepoint_figure_title() -> str:
    return (
        "Relative frequency by timepoint "
        "(correction is within each day, five tests)"
    )
