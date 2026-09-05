"""Part 3: compare responders against non-responders.

The conclusion this produces is negative, and that is the finding. See
docs/SPEC.md section 8 and decision D-020.
"""
import sqlite3

import pandas as pd
from scipy import stats

# Melanoma subjects on miraclib, PBMC samples only. The PBMC restriction is
# easy to miss in the brief and is not optional.
RESPONSE_COHORT = """
    s.condition = 'melanoma'
AND s.treatment = 'miraclib'
AND sa.sample_type = 'PBMC'
AND s.response IS NOT NULL
"""

COHORT_QUERY = f"""
SELECT f.sample,
       s.subject_id                     AS subject,
       s.response,
       sa.time_from_treatment_start     AS timepoint,
       f.population,
       f.percentage
FROM sample_frequencies f
JOIN samples sa     ON sa.sample_id = f.sample
JOIN subjects s     ON s.subject_id = sa.subject_id
JOIN populations p  ON p.population = f.population
WHERE {RESPONSE_COHORT}
ORDER BY p.ordinal, f.sample
"""

POPULATION_ORDER_QUERY = "SELECT population FROM populations ORDER BY ordinal"


def mann_whitney(a, b) -> tuple[float, float]:
    result = stats.mannwhitneyu(a, b, alternative="two-sided")
    return float(result.statistic), float(result.pvalue)


def welch_t(a, b) -> float:
    return float(stats.ttest_ind(a, b, equal_var=False).pvalue)


def cliffs_delta(a, b) -> float:
    """Rank-based effect size. +1 means every value in a exceeds every b."""
    n1, n2 = len(a), len(b)
    u, _ = mann_whitney(a, b)
    return 2.0 * u / (n1 * n2) - 1.0


def magnitude(delta: float) -> str:
    d = abs(delta)
    if d < 0.147:
        return "negligible"
    if d < 0.330:
        return "small"
    if d < 0.474:
        return "medium"
    return "large"


def benjamini_hochberg(pvalues: list[float]) -> list[float]:
    """Step-up FDR correction. Returns q-values in the input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i], reverse=True)
    adjusted = [0.0] * m
    running = 1.0
    for position, index in enumerate(order):
        rank = m - position
        running = min(running, pvalues[index] * m / rank)
        adjusted[index] = running
    return adjusted


def cohort_frequencies(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(COHORT_QUERY, conn)


def _population_order(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute(POPULATION_ORDER_QUERY)]


def _split(frame: pd.DataFrame, population: str) -> tuple[list, list]:
    subset = frame[frame["population"] == population]
    return (
        subset[subset["response"] == "yes"]["percentage"].tolist(),
        subset[subset["response"] == "no"]["percentage"].tolist(),
    )


def compare_responders(conn: sqlite3.Connection) -> pd.DataFrame:
    """Headline comparison on all samples, with two sensitivity analyses."""
    frame = cohort_frequencies(conn)
    populations = _population_order(conn)

    subject_means = (
        frame.groupby(["subject", "response", "population"], as_index=False)
        ["percentage"].mean()
    )
    baseline = frame[frame["timepoint"] == 0]

    rows = []
    for population in populations:
        responders, non_responders = _split(frame, population)
        _, p = mann_whitney(responders, non_responders)
        delta = cliffs_delta(responders, non_responders)

        sm_a, sm_b = _split(subject_means, population)
        bl_a, bl_b = _split(baseline, population)

        rows.append(
            {
                "population": population,
                "n_responder": len(responders),
                "n_non_responder": len(non_responders),
                "median_responder": pd.Series(responders).median(),
                "median_non_responder": pd.Series(non_responders).median(),
                "median_difference": (
                    pd.Series(responders).median() - pd.Series(non_responders).median()
                ),
                "cliffs_delta": delta,
                "effect_magnitude": magnitude(delta),
                "p_value": p,
                "p_value_welch": welch_t(responders, non_responders),
                "p_value_subject_means": mann_whitney(sm_a, sm_b)[1],
                "p_value_baseline": mann_whitney(bl_a, bl_b)[1],
            }
        )

    table = pd.DataFrame(rows)
    table["q_value"] = benjamini_hochberg(table["p_value"].tolist())
    table["q_value_subject_means"] = benjamini_hochberg(
        table["p_value_subject_means"].tolist()
    )
    table["q_value_baseline"] = benjamini_hochberg(
        table["p_value_baseline"].tolist()
    )
    table["significant"] = table["q_value"] < 0.05
    return table[
        [
            "population",
            "n_responder",
            "n_non_responder",
            "median_responder",
            "median_non_responder",
            "median_difference",
            "cliffs_delta",
            "effect_magnitude",
            "p_value",
            "q_value",
            "significant",
            "p_value_welch",
            "p_value_subject_means",
            "q_value_subject_means",
            "p_value_baseline",
            "q_value_baseline",
        ]
    ]


def compare_by_timepoint(conn: sqlite3.Connection) -> pd.DataFrame:
    """The same comparison at each timepoint, corrected within each day."""
    frame = cohort_frequencies(conn)
    populations = _population_order(conn)

    blocks = []
    for timepoint in sorted(frame["timepoint"].unique()):
        day = frame[frame["timepoint"] == timepoint]
        rows = []
        for population in populations:
            responders, non_responders = _split(day, population)
            _, p = mann_whitney(responders, non_responders)
            delta = cliffs_delta(responders, non_responders)
            rows.append(
                {
                    "timepoint": int(timepoint),
                    "population": population,
                    "n_responder": len(responders),
                    "n_non_responder": len(non_responders),
                    "median_difference": (
                        pd.Series(responders).median()
                        - pd.Series(non_responders).median()
                    ),
                    "cliffs_delta": delta,
                    "effect_magnitude": magnitude(delta),
                    "p_value": p,
                }
            )
        block = pd.DataFrame(rows)
        block["q_value"] = benjamini_hochberg(block["p_value"].tolist())
        block["significant"] = block["q_value"] < 0.05
        blocks.append(block)

    return pd.concat(blocks, ignore_index=True)
