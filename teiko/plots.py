"""Boxplots for Part 3."""
import sqlite3

import matplotlib

matplotlib.use("Agg")  # No display in Codespaces or on Streamlit Cloud.
import matplotlib.pyplot as plt  # noqa: E402

from teiko.display import responder_figure_title, timepoint_figure_title  # noqa: E402
from teiko.statistics import (  # noqa: E402
    cohort_frequencies,
    compare_by_timepoint,
    compare_responders,
)

LABELS = {
    "b_cell": "B cell",
    "cd8_t_cell": "CD8+ T cell",
    "cd4_t_cell": "CD4+ T cell",
    "nk_cell": "NK cell",
    "monocyte": "Monocyte",
}


def _order(frame):
    return [p for p in LABELS if p in set(frame["population"])]


def responder_boxplots(conn: sqlite3.Connection) -> plt.Figure:
    frame = cohort_frequencies(conn)
    stats_table = compare_responders(conn).set_index("population")
    populations = _order(frame)

    fig, axes = plt.subplots(1, 5, figsize=(16, 4.5), sharey=True)
    for ax, population in zip(axes, populations):
        subset = frame[frame["population"] == population]
        groups = [
            subset[subset["response"] == "yes"]["percentage"],
            subset[subset["response"] == "no"]["percentage"],
        ]
        ax.boxplot(groups, tick_labels=["Responder", "Non-responder"], widths=0.6)
        q = stats_table.loc[population, "q_value"]
        ax.set_title(f"{LABELS[population]}\nq = {q:.3f}", fontsize=10)
        ax.tick_params(axis="x", labelrotation=20)

    axes[0].set_ylabel("Relative frequency (%)")
    fig.suptitle(responder_figure_title(stats_table.reset_index()), fontsize=12)
    fig.tight_layout()
    return fig


def timepoint_boxplots(conn: sqlite3.Connection) -> plt.Figure:
    frame = cohort_frequencies(conn)
    stats_table = compare_by_timepoint(conn).set_index(["timepoint", "population"])
    populations = _order(frame)
    timepoints = sorted(frame["timepoint"].unique())

    fig, axes = plt.subplots(
        len(timepoints), 5, figsize=(16, 11), sharey=True, squeeze=False
    )
    for row, timepoint in enumerate(timepoints):
        day = frame[frame["timepoint"] == timepoint]
        for col, population in enumerate(populations):
            ax = axes[row][col]
            subset = day[day["population"] == population]
            ax.boxplot(
                [
                    subset[subset["response"] == "yes"]["percentage"],
                    subset[subset["response"] == "no"]["percentage"],
                ],
                tick_labels=["R", "NR"],
                widths=0.6,
            )
            q = stats_table.loc[(timepoint, population), "q_value"]
            ax.set_title(f"{LABELS[population]} · day {timepoint}\nq = {q:.3f}",
                         fontsize=9)
        axes[row][0].set_ylabel("Relative frequency (%)")

    fig.suptitle(timepoint_figure_title(), fontsize=12)
    fig.tight_layout()
    return fig
