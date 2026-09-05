"""Run Parts 2 to 4 and write everything into outputs/.

Assumes load_data.py has already built the database. `make pipeline` runs both.
"""
from teiko.db import ROOT, ensure_database
from teiko.display import write_dashboard_metrics
from teiko.frequencies import summary_table
from teiko.plots import responder_boxplots, timepoint_boxplots
from teiko.statistics import compare_by_timepoint, compare_responders
from teiko.subsets import (
    baseline_breakdowns,
    baseline_cohort,
    melanoma_male_baseline_b_cell_mean,
)

OUTPUTS = ROOT / "outputs"


def write_answers(breakdowns, n_samples, cohort_b_n, cohort_b_mean, stats_table):
    projects = breakdowns[breakdowns["breakdown"] == "project"]
    response = breakdowns[breakdowns["breakdown"] == "response"].set_index("category")
    sex = breakdowns[breakdowns["breakdown"] == "sex"].set_index("category")
    n_subjects = int(response["count"].sum())
    project_line = ", ".join(
        f"{row.category} {row.count}" for row in projects.itertuples()
    )
    significant = stats_table[stats_table["significant"]]["population"].tolist()
    verdict = (
        "No cell population differs significantly between responders and "
        "non-responders after correction."
        if not significant
        else f"Significant after correction: {', '.join(significant)}."
    )

    text = f"""# Part 4 answers

## Cohort A — melanoma, PBMC, miraclib, day 0

{n_samples} samples from {n_subjects} subjects.

- Samples per project: {project_line}.
- Subjects by response: {response.loc['yes', 'count']} responders,
  {response.loc['no', 'count']} non-responders.
- Subjects by sex: {sex.loc['M', 'count']} male, {sex.loc['F', 'count']} female.

## Cohort B — melanoma males, all sample and treatment types, day 0

The final question uses a broader cohort than the earlier baseline query:
no PBMC restriction and no treatment restriction.

- Responder samples: {cohort_b_n}.
- Average B cell count: {cohort_b_mean:.2f}.

## Part 3 conclusion

{verdict}
"""
    (OUTPUTS / "part4_answers.md").write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUTS.mkdir(exist_ok=True)
    conn = ensure_database()
    try:
        summary = summary_table(conn)
        summary.to_csv(
            OUTPUTS / "summary_table.csv", index=False, float_format="%.4f"
        )
        print(f"summary_table.csv          {len(summary):>6,} rows")

        stats_table = compare_responders(conn)
        stats_table.to_csv(OUTPUTS / "responder_comparison.csv", index=False)
        print(f"responder_comparison.csv   {len(stats_table):>6,} rows")

        by_timepoint = compare_by_timepoint(conn)
        by_timepoint.to_csv(OUTPUTS / "timepoint_comparison.csv", index=False)
        print(f"timepoint_comparison.csv   {len(by_timepoint):>6,} rows")

        responder_boxplots(conn).savefig(OUTPUTS / "boxplots.png", dpi=150)
        timepoint_boxplots(conn).savefig(
            OUTPUTS / "boxplots_by_timepoint.png", dpi=150
        )
        print("boxplots.png, boxplots_by_timepoint.png")

        cohort = baseline_cohort(conn)
        cohort.to_csv(OUTPUTS / "part4_baseline_samples.csv", index=False)
        breakdowns = baseline_breakdowns(conn)
        breakdowns.to_csv(OUTPUTS / "part4_breakdowns.csv", index=False)
        n_b, mean_b = melanoma_male_baseline_b_cell_mean(conn)
        write_answers(breakdowns, len(cohort), n_b, mean_b, stats_table)
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "projects",
                "subjects",
                "samples",
                "cell_counts",
            )
        }
        write_dashboard_metrics(
            OUTPUTS / "dashboard_metrics.csv",
            counts,
            cohort_a_samples=len(cohort),
            cohort_b_samples=n_b,
            cohort_b_b_cell_mean=mean_b,
        )
        print(f"part4 files                {len(cohort):>6,} baseline samples")
        print(f"Cohort B average B cell count: {mean_b:.2f} over {n_b} samples")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
