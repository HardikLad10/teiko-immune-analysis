"""Part 4: cohort subsets.

Two different cohorts. Cohort B deliberately drops the PBMC and miraclib
filters, because the brief says "all sample and treatment types". Keeping them
changes the answer from 10206.15 to 10401.28.
"""
import sqlite3

import pandas as pd

COHORT_A = """
    s.condition = 'melanoma'
AND s.treatment = 'miraclib'
AND sa.sample_type = 'PBMC'
AND sa.time_from_treatment_start = 0
"""

COHORT_A_QUERY = f"""
SELECT sa.sample_id AS sample, s.subject_id AS subject, s.project_id AS project,
       s.response, s.sex
FROM samples sa
JOIN subjects s ON s.subject_id = sa.subject_id
WHERE {COHORT_A}
ORDER BY sa.sample_id
"""

# LEFT JOIN from projects so a project with no matching samples reports zero
# instead of vanishing from the result.
BY_PROJECT_QUERY = f"""
SELECT p.project_id AS category, COUNT(sa.sample_id) AS count
FROM projects p
LEFT JOIN subjects s ON s.project_id = p.project_id
LEFT JOIN samples sa ON sa.subject_id = s.subject_id AND {COHORT_A}
GROUP BY p.project_id
ORDER BY p.project_id
"""

# COUNT(DISTINCT subject_id) because the brief asks for subjects here, even
# though each subject has exactly one baseline sample.
BY_SUBJECT_QUERY = f"""
SELECT s.{{column}} AS category, COUNT(DISTINCT s.subject_id) AS count
FROM samples sa
JOIN subjects s ON s.subject_id = sa.subject_id
WHERE {COHORT_A}
GROUP BY s.{{column}}
ORDER BY s.{{column}} DESC
"""

COHORT_B_QUERY = """
SELECT COUNT(*) AS n, AVG(cc.count) AS mean_b_cell
FROM samples sa
JOIN subjects s     ON s.subject_id = sa.subject_id
JOIN cell_counts cc ON cc.sample_id = sa.sample_id
WHERE s.condition = 'melanoma'
  AND s.sex = 'M'
  AND s.response = 'yes'
  AND sa.time_from_treatment_start = 0
  AND cc.population = 'b_cell'
"""


def baseline_cohort(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(COHORT_A_QUERY, conn)


def baseline_breakdowns(conn: sqlite3.Connection) -> pd.DataFrame:
    projects = pd.read_sql_query(BY_PROJECT_QUERY, conn)
    projects.insert(0, "breakdown", "project")
    projects["unit"] = "samples"

    frames = [projects]
    for column, name in (("response", "response"), ("sex", "sex")):
        frame = pd.read_sql_query(BY_SUBJECT_QUERY.format(column=column), conn)
        frame.insert(0, "breakdown", name)
        frame["unit"] = "subjects"
        frames.append(frame)

    return pd.concat(frames, ignore_index=True)[
        ["breakdown", "category", "count", "unit"]
    ]


def melanoma_male_baseline_b_cell_mean(conn: sqlite3.Connection) -> tuple[int, float]:
    row = conn.execute(COHORT_B_QUERY).fetchone()
    return int(row["n"]), float(row["mean_b_cell"])
