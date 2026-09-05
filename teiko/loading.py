"""Load cell-count.csv into the normalised schema."""
import csv
from pathlib import Path

from teiko.db import apply_schema, connect

POPULATIONS = [
    ("b_cell", "B cell", 1),
    ("cd8_t_cell", "CD8+ T cell", 2),
    ("cd4_t_cell", "CD4+ T cell", 3),
    ("nk_cell", "NK cell", 4),
    ("monocyte", "Monocyte", 5),
]
POPULATION_NAMES = [name for name, _, _ in POPULATIONS]

TABLES = ("projects", "populations", "subjects", "samples", "cell_counts")


def build_database(db_path: Path, csv_path: Path) -> dict[str, int]:
    """Create the database and load every row. Safe to run repeatedly."""
    conn = connect(db_path)
    try:
        apply_schema(conn)
        _load(conn, csv_path)
        conn.commit()
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in TABLES
        }
    finally:
        conn.close()
    return counts


def _load(conn, csv_path: Path) -> None:
    with open(csv_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    projects = sorted({row["project"] for row in rows})
    conn.executemany(
        "INSERT INTO projects (project_id) VALUES (?)", [(p,) for p in projects]
    )
    conn.executemany(
        "INSERT INTO populations (population, display_name, ordinal)"
        " VALUES (?, ?, ?)",
        POPULATIONS,
    )

    subjects = {}
    for row in rows:
        # Subject and sample IDs are treated as unique across the file.
        # This CSV keeps every subject field constant; a clash is an error.
        record = (
            row["subject"],
            row["project"],
            row["condition"],
            int(row["age"]),
            row["sex"],
            row["treatment"],
            row["response"] or None,
        )
        existing = subjects.get(row["subject"])
        if existing is None:
            subjects[row["subject"]] = record
        elif existing != record:
            raise ValueError(
                f"subject {row['subject']} has conflicting metadata; "
                "identifiers are assumed unique across projects"
            )
    conn.executemany(
        "INSERT INTO subjects"
        " (subject_id, project_id, condition, age, sex, treatment, response)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        list(subjects.values()),
    )

    conn.executemany(
        "INSERT INTO samples"
        " (sample_id, subject_id, sample_type, time_from_treatment_start)"
        " VALUES (?, ?, ?, ?)",
        [
            (
                row["sample"],
                row["subject"],
                row["sample_type"],
                int(row["time_from_treatment_start"]),
            )
            for row in rows
        ],
    )

    conn.executemany(
        "INSERT INTO cell_counts (sample_id, population, count) VALUES (?, ?, ?)",
        [
            (row["sample"], population, int(row[population]))
            for row in rows
            for population in POPULATION_NAMES
        ],
    )
