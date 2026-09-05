"""Interactive dashboard for the Loblaw Bio immune cell analysis.

Streamlit executes every `with tab:` block on each run. This app uses a
sidebar picker so only one section runs. Overview / Response / Subsets
read committed files in outputs/. Frequencies is the only path that
opens the database.
"""
import pandas as pd
import streamlit as st

from teiko.db import ROOT

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


if section == "Overview":
    st.subheader("What is in the study")
    columns = st.columns(4)
    for column, (label, value) in zip(
        columns,
        [("Projects", 3), ("Subjects", 3500), ("Samples", 10500), ("Cell counts", 52500)],
    ):
        column.metric(label, f"{value:,}")
    st.markdown(
        "Five tables: `projects`, `populations`, `subjects`, `samples`, and "
        "`cell_counts`. Counts are stored one row per sample per population, "
        "and a `sample_frequencies` view is the single definition of relative "
        "frequency used by every tab here and by the pipeline."
    )
    st.markdown(
        "**Conclusion.** No cell population differs significantly between "
        "responders and non-responders after correction. These five "
        "frequencies do not predict response to miraclib. Average B cell "
        "count for melanoma males who responded, all sample and treatment "
        "types, at time 0: **10206.15**."
    )

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
    table = load_csv("responder_comparison.csv")
    st.info(
        "No cell population differs significantly between responders and "
        "non-responders after Benjamini-Hochberg correction. Every effect "
        "size is negligible. CD4 T cells reach p = 0.0133 uncorrected, "
        "which disappears once the five tests are corrected together "
        "(q = 0.0667)."
    )
    if (OUTPUTS / "boxplots.png").exists():
        st.image(str(OUTPUTS / "boxplots.png"))
    st.dataframe(table, use_container_width=True)

    st.markdown("#### The same comparison at each timepoint")
    st.markdown(
        "At baseline the two groups are indistinguishable. A weak B cell "
        "difference appears after dosing and strengthens by day 14, but never "
        "reaches significance. That makes it an observation about what the "
        "drug does, not a way to predict who will respond."
    )
    st.dataframe(load_csv("timepoint_comparison.csv"), use_container_width=True)
    if (OUTPUTS / "boxplots_by_timepoint.png").exists():
        st.image(str(OUTPUTS / "boxplots_by_timepoint.png"))

else:
    st.subheader("Part 4 — cohort subsets")
    answers = OUTPUTS / "part4_answers.md"
    if answers.exists():
        st.markdown(answers.read_text(encoding="utf-8"))
    breakdowns = load_csv("part4_breakdowns.csv")
    for name in ("project", "response", "sex"):
        st.markdown(f"**By {name}**")
        st.dataframe(
            breakdowns[breakdowns["breakdown"] == name], use_container_width=True
        )
    left, right = st.columns(2)
    left.metric("Cohort A samples", "656")
    right.metric("Cohort B average B cells", "10206.15")
