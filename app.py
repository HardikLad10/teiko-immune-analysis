"""Interactive dashboard for the Loblaw Bio immune cell analysis."""
import pandas as pd
import streamlit as st

from teiko.db import ensure_database
from teiko.frequencies import summary_table
from teiko.plots import responder_boxplots, timepoint_boxplots
from teiko.statistics import compare_by_timepoint, compare_responders
from teiko.subsets import (
    baseline_breakdowns,
    baseline_cohort,
    melanoma_male_baseline_b_cell_mean,
)

st.set_page_config(page_title="Immune cell analysis", layout="wide")


@st.cache_resource
def get_connection():
    # Builds teiko.db from the committed CSV if it is absent, which is what
    # makes the hosted copy work without committing a database file.
    return ensure_database()


@st.cache_data
def load_summary():
    return summary_table(get_connection())


conn = get_connection()
st.title("Immune cell populations — Loblaw Bio miraclib trial")

overview, frequencies, response, subsets = st.tabs(
    ["Overview", "Frequencies", "Response analysis", "Subset explorer"]
)

with overview:
    st.subheader("What is in the study")
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("projects", "subjects", "samples", "cell_counts")
    }
    columns = st.columns(4)
    for column, (label, value) in zip(columns, counts.items()):
        column.metric(label.replace("_", " ").title(), f"{value:,}")
    st.markdown(
        "Five tables: `projects`, `populations`, `subjects`, `samples`, and "
        "`cell_counts`. Counts are stored one row per sample per population, "
        "and a `sample_frequencies` view is the single definition of relative "
        "frequency used by every tab here and by the pipeline."
    )
    st.dataframe(
        pd.read_sql_query(
            "SELECT condition, treatment, sample_type, COUNT(*) AS samples"
            " FROM samples sa JOIN subjects s ON s.subject_id = sa.subject_id"
            " GROUP BY condition, treatment, sample_type"
            " ORDER BY samples DESC",
            conn,
        ),
        use_container_width=True,
    )

with frequencies:
    st.subheader("Part 2 — relative frequency of each population")
    frame = load_summary()
    metadata = pd.read_sql_query(
        "SELECT sa.sample_id AS sample, s.project_id AS project, s.condition,"
        " s.treatment, sa.sample_type, sa.time_from_treatment_start AS timepoint"
        " FROM samples sa JOIN subjects s ON s.subject_id = sa.subject_id",
        conn,
    )
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

with response:
    st.subheader("Part 3 — responders against non-responders")
    table = compare_responders(conn)
    significant = table[table["significant"]]["population"].tolist()
    if significant:
        st.warning(f"Significant after correction: {', '.join(significant)}")
    else:
        p_cd4 = table.set_index("population").loc["cd4_t_cell", "p_value"]
        st.info(
            "No cell population differs significantly between responders and "
            "non-responders after Benjamini-Hochberg correction. Every effect "
            "size is negligible. CD4 T cells reach p = "
            f"{p_cd4:.4f} "
            "uncorrected, which is exactly the result that disappears once the "
            "five tests are corrected together."
        )
    st.pyplot(responder_boxplots(conn))
    st.dataframe(table, use_container_width=True)

    st.markdown("#### The same comparison at each timepoint")
    st.markdown(
        "At baseline the two groups are indistinguishable. A weak B cell "
        "difference appears after dosing and strengthens by day 14, but never "
        "reaches significance. That makes it an observation about what the "
        "drug does, not a way to predict who will respond."
    )
    st.dataframe(compare_by_timepoint(conn), use_container_width=True)
    st.pyplot(timepoint_boxplots(conn))

with subsets:
    st.subheader("Part 4 — cohort subsets")
    st.markdown(
        "**Cohort A** — melanoma, PBMC, miraclib, day 0. "
        "Samples are counted per project; subjects are counted for response "
        "and sex, because that is what the question asks for."
    )
    cohort = baseline_cohort(conn)
    st.metric("Samples in Cohort A", f"{len(cohort):,}")
    breakdowns = baseline_breakdowns(conn)
    for name in ("project", "response", "sex"):
        st.markdown(f"**By {name}**")
        st.dataframe(
            breakdowns[breakdowns["breakdown"] == name], use_container_width=True
        )

    st.divider()
    st.markdown(
        "**Cohort B** — melanoma males, responders, day 0, "
        "**all sample types and all treatments**. The brief widens the filters "
        "for this question, so this is a different group from Cohort A."
    )
    n_b, mean_b = melanoma_male_baseline_b_cell_mean(conn)
    left, right = st.columns(2)
    left.metric("Samples", f"{n_b:,}")
    right.metric("Average B cell count", f"{mean_b:.2f}")
