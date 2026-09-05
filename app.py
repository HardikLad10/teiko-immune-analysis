"""Interactive dashboard for the Loblaw Bio immune cell analysis.

Streamlit executes every `with tab:` block on each run. This app uses a
sidebar picker so only one section runs. Overview / Response / Subsets
read committed files in outputs/. Frequencies is the only path that
opens the database.
"""
import pandas as pd
import streamlit as st

from teiko.db import ROOT
from teiko.display import (
    METRICS_NAME,
    read_dashboard_metrics,
    response_banner,
    timepoint_correction_note,
)

OUTPUTS = ROOT / "outputs"

st.set_page_config(page_title="Immune cell analysis", layout="wide")
st.title("Immune cell populations — Loblaw Bio miraclib trial")

section = st.sidebar.radio(
    "Section",
    ["Overview", "Frequencies", "Response analysis", "Subset explorer"],
)


@st.cache_resource
def ensure_db_file() -> str:
    """Build teiko.db once. Do not cache the connection — sqlite3
    connections cannot be shared across Streamlit's threads."""
    from teiko.db import DB_PATH, CSV_PATH
    from teiko.loading import build_database

    if not DB_PATH.exists():
        build_database(DB_PATH, CSV_PATH)
    return str(DB_PATH)


def get_connection():
    from teiko.db import connect
    from pathlib import Path

    return connect(Path(ensure_db_file()))


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUTS / name)


@st.cache_data
def load_summary():
    from teiko.frequencies import summary_table

    conn = get_connection()
    try:
        return summary_table(conn)
    finally:
        conn.close()


def require_metrics():
    path = OUTPUTS / METRICS_NAME
    if not path.exists():
        st.error(
            "Required output files are missing. Run `make pipeline` from the "
            "repository root, then reload."
        )
        return None
    return read_dashboard_metrics(OUTPUTS)


if section == "Overview":
    st.subheader("What is in the study")
    metrics = require_metrics()
    if metrics is not None:
        columns = st.columns(4)
        for column, (label, key) in zip(
            columns,
            [
                ("Projects", "projects"),
                ("Subjects", "subjects"),
                ("Samples", "samples"),
                ("Cell counts", "cell_counts"),
            ],
        ):
            column.metric(label, f"{metrics[key]:,}")
    st.markdown(
        "Five tables: `projects`, `populations`, `subjects`, `samples`, and "
        "`cell_counts`. Counts are stored one row per sample per population. "
        "A view (a saved SQL query that behaves like a table) named "
        "`sample_frequencies` is the single formula for relative frequency. "
        "The pipeline writes `outputs/`; this page reads those files. "
        "Frequencies queries the database."
    )
    answers = OUTPUTS / "part4_answers.md"
    if answers.exists():
        st.markdown(answers.read_text(encoding="utf-8"))
    else:
        st.error("outputs/part4_answers.md is missing. Run `make pipeline`.")

elif section == "Frequencies":
    st.subheader("Part 2 — relative frequency of each population")
    frame = load_summary()
    conn = get_connection()
    try:
        metadata = pd.read_sql_query(
            "SELECT sa.sample_id AS sample, s.project_id AS project, s.condition,"
            " s.treatment, sa.sample_type, sa.time_from_treatment_start AS timepoint"
            " FROM samples sa JOIN subjects s ON s.subject_id = sa.subject_id",
            conn,
        )
    finally:
        conn.close()
    merged = frame.merge(metadata, on="sample")

    controls = st.columns(5)
    filters = {}
    for column, field in zip(
        controls, ["project", "condition", "treatment", "sample_type", "timepoint"]
    ):
        options = sorted(merged[field].unique())
        filters[field] = column.multiselect(
            field.replace("_", " "), options, default=options
        )
    for field, chosen in filters.items():
        merged = merged[merged[field].isin(chosen)]

    st.caption(f"{len(merged):,} rows")
    st.dataframe(merged.head(1000), use_container_width=True)
    st.download_button(
        "Download the filtered table as CSV",
        merged.to_csv(index=False).encode("utf-8"),
        "summary_table_filtered.csv",
        "text/csv",
    )

elif section == "Response analysis":
    st.subheader("Part 3 — responders against non-responders")
    table_path = OUTPUTS / "responder_comparison.csv"
    if not table_path.exists():
        st.error("outputs/responder_comparison.csv is missing. Run `make pipeline`.")
    else:
        table = load_csv("responder_comparison.csv")
        st.info(response_banner(table))
        if (OUTPUTS / "boxplots.png").exists():
            st.image(str(OUTPUTS / "boxplots.png"))
        else:
            st.warning("outputs/boxplots.png is missing. Run `make pipeline`.")
        st.dataframe(table, use_container_width=True)

        st.markdown("#### The same comparison at each timepoint")
        st.caption(timepoint_correction_note())
        st.dataframe(load_csv("timepoint_comparison.csv"), use_container_width=True)
        if (OUTPUTS / "boxplots_by_timepoint.png").exists():
            st.image(str(OUTPUTS / "boxplots_by_timepoint.png"))
        else:
            st.warning(
                "outputs/boxplots_by_timepoint.png is missing. Run `make pipeline`."
            )

else:
    st.subheader("Part 4 — cohort subsets")
    answers = OUTPUTS / "part4_answers.md"
    if answers.exists():
        st.markdown(answers.read_text(encoding="utf-8"))
    else:
        st.error("outputs/part4_answers.md is missing. Run `make pipeline`.")
    breakdowns = OUTPUTS / "part4_breakdowns.csv"
    if breakdowns.exists():
        frame = load_csv("part4_breakdowns.csv")
        for name in ("project", "response", "sex"):
            st.markdown(f"**By {name}**")
            st.dataframe(
                frame[frame["breakdown"] == name], use_container_width=True
            )
    metrics = require_metrics()
    if metrics is not None:
        left, right = st.columns(2)
        left.metric("Cohort A samples", f"{metrics['cohort_a_samples']:,}")
        right.metric(
            "Cohort B average B cells",
            f"{metrics['cohort_b_b_cell_mean']:.2f}",
        )
