"""Part 2: relative frequency of each population in each sample."""
import sqlite3

import pandas as pd

SUMMARY_QUERY = """
SELECT f.sample, f.total_count, f.population, f.count, f.percentage
FROM sample_frequencies f
JOIN populations p ON p.population = f.population
ORDER BY f.sample, p.ordinal
"""


def summary_table(conn: sqlite3.Connection) -> pd.DataFrame:
    """One row per sample per population, in the fixed population order."""
    return pd.read_sql_query(SUMMARY_QUERY, conn)
