# Immune Cell Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a SQLite pipeline and Streamlit dashboard that answer Parts 1 to 4 of the Loblaw Bio exercise, reproducibly, from `make setup && make pipeline && make dashboard`.

**Architecture:** A five-table normalised SQLite database with cell counts stored long, and a `sample_frequencies` view that is the single definition of relative frequency. Thin root entry points (`load_data.py`, `run_pipeline.py`, `app.py`) delegate to a `teiko/` package whose functions take a database connection and return DataFrames or figures, so the pipeline and the dashboard share one implementation.

**Tech Stack:** Python 3.11+, SQLite (stdlib `sqlite3`), pandas, numpy, scipy, matplotlib, Streamlit, pytest.

**Spec:** `docs/SPEC.md`. **Decision log:** `docs/DECISIONS.md`.

## Global Constraints

- `load_data.py` must be in the repository root, run as bare `python load_data.py`, take no arguments, not be invoked via `python -m`, and create a `.db` file in the repository root.
- The Makefile must implement targets named exactly `setup`, `pipeline`, and `dashboard`.
- `make pipeline` runs start to finish with no manual intervention.
- The package is `teiko/` at the repository root, never `src/teiko/`.
- Every SQLite connection is opened through `teiko.db.connect`, which issues `PRAGMA foreign_keys = ON`. Never call `sqlite3.connect` directly.
- Population order is always `b_cell, cd8_t_cell, cd4_t_cell, nk_cell, monocyte`, enforced by `populations.ordinal`.
- Dependencies are exactly: `pandas`, `numpy`, `scipy`, `matplotlib`, `streamlit`, `pytest`. Adding one requires a decision log entry.
- No file may mention a treatment name outside `miraclib`, `phauximab`, and `none`. Enforced by `tests/test_integrity.py`.
- Banned words in all prose: leverage, robust, seamless, comprehensive, powerful, cutting-edge, delve, utilise, facilitate, "it's worth noting", "in the realm of", "at the end of the day".
- Commit messages are one lower-case line stating the change. No emoji, no conventional-commit prefixes.
- Every task ends with a commit and `git push origin main`.
- `*.db` stays gitignored. `outputs/` is committed.

## Decision Protocol

Each task lists the decisions it forces, tagged by who resolves them.

- **[ASK]** — changes an output file, a dependency, a reported number, or a deliverable. Stop and ask before implementing.
- **[LOG]** — internal choice with no visible effect. Decide, implement, and append an entry to `docs/DECISIONS.md` in the same commit.
- Anything not listed is naming or formatting. Just do it, no entry.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `load_data.py` | Part 1 entry point. Builds `teiko.db` from `cell-count.csv`. |
| `run_pipeline.py` | Runs Parts 2 to 4, writes every file in `outputs/`. |
| `app.py` | Streamlit dashboard, four tabs. |
| `schema.sql` | Five `CREATE TABLE` statements, indexes, and the view. |
| `teiko/db.py` | Path constants, connection with the pragma, schema application, bootstrap. |
| `teiko/loading.py` | CSV to normalised tables. |
| `teiko/frequencies.py` | Part 2. Reads the view. |
| `teiko/statistics.py` | Mann-Whitney, Cliff's delta, Benjamini-Hochberg, the comparison table. |
| `teiko/subsets.py` | Part 4 cohort queries. |
| `teiko/plots.py` | Both boxplot figures. |
| `tests/` | Ten tests across five files. |

---

## Task 1: Scaffolding and the integrity guard

**Files:**
- Create: `requirements.txt`, `Makefile`, `pytest.ini`, `outputs/.gitkeep`, `tests/__init__.py`, `tests/fixtures/tiny.csv`, `tests/test_integrity.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: `tests/fixtures/tiny.csv` with two samples whose percentages are hand-computable — `sampleT0` totals 100 cells (10/20/30/20/20) and `sampleT1` totals 5 (1/1/1/1/1). Tasks 2 and 3 use it.

**Decisions this task forces:**
- **[LOG]** Pin dependencies to exact versions or use minimum bounds. Exact pins are more reproducible in Codespaces; minimum bounds survive longer. Recommend exact pins with a comment saying why.

- [x] **Step 1: Write the failing integrity test**

Create `tests/test_integrity.py`:

```python
"""Guards the exercise's canary. See docs/SPEC.md section 14."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The only treatments that exist in cell-count.csv. Anything else appearing in
# a tracked file means text was copied from the brief without being read.
KNOWN_TREATMENTS = {"miraclib", "phauximab", "none"}

# Matches the naming pattern of the fictional drugs in this exercise.
DRUG_PATTERN = re.compile(r"\b[a-z]{4,}(?:clib|zide|mab|nib|tide|stat)\b")


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [ROOT / line for line in out.stdout.splitlines() if line]


def test_no_unknown_treatment_names_in_repository():
    offenders = {}
    for path in tracked_files():
        if path.name == "cell-count.csv" or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found = {m for m in DRUG_PATTERN.findall(text.lower())} - KNOWN_TREATMENTS
        if found:
            offenders[path.relative_to(ROOT).as_posix()] = sorted(found)
    assert offenders == {}, f"unknown treatment names found: {offenders}"
```

- [x] **Step 2: Run it and watch it fail**

Run: `python -m pytest tests/test_integrity.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'pytest'`, because nothing is installed yet.

- [x] **Step 3: Create `requirements.txt`**

```
# Pinned exactly so a Codespace and a laptop resolve identically.
pandas==2.2.3
numpy==2.1.3
scipy==1.14.1
matplotlib==3.9.2
streamlit==1.40.1
pytest==8.3.3
```

- [x] **Step 4: Create the `Makefile`**

Use real tab characters for indentation, not spaces.

```make
.PHONY: setup pipeline dashboard test

setup:
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt

pipeline:
	python load_data.py
	python run_pipeline.py

dashboard:
	streamlit run app.py

test:
	python -m pytest -q
```

- [x] **Step 5: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -ra
```

- [x] **Step 6: Create the fixture**

`tests/fixtures/tiny.csv`. Row one totals 100 cells so percentages are the counts themselves. Row two is a healthy subject with a blank response, which task 2 uses to check `NULL` handling.

```csv
project,subject,condition,age,sex,treatment,response,sample,sample_type,time_from_treatment_start,b_cell,cd8_t_cell,cd4_t_cell,nk_cell,monocyte
prjT,sbjT0,melanoma,60,M,miraclib,yes,sampleT0,PBMC,0,10,20,30,20,20
prjT,sbjT1,healthy,55,F,none,,sampleT1,WB,0,1,1,1,1,1
```

- [x] **Step 7: Create `tests/__init__.py` and `outputs/.gitkeep`**

Both empty files. `outputs/.gitkeep` makes the directory exist in git before any output is written.

- [x] **Step 8: Add `outputs/` exception to `.gitignore`**

`outputs/` is committed, so confirm no rule excludes it. Append this comment block to `.gitignore`:

```gitignore
# outputs/ IS committed - the brief asks for generated output files.
# Only the database is ignored, since `make pipeline` rebuilds it.
```

- [x] **Step 9: Install and run the test**

Run: `make setup && python -m pytest tests/test_integrity.py -v`

Expected: PASS, 1 test.

- [x] **Step 10: Commit and push**

```bash
git add requirements.txt Makefile pytest.ini .gitignore outputs/.gitkeep tests/
git commit -m "add project scaffolding and canary integrity test"
git push origin main
```

---

## Task 2: Schema and loader

**Files:**
- Create: `schema.sql`, `teiko/__init__.py`, `teiko/db.py`, `teiko/loading.py`, `load_data.py`, `tests/test_loading.py`

**Interfaces:**
- Consumes: `tests/fixtures/tiny.csv` from Task 1.
- Produces:
  - `teiko.db.ROOT: Path`, `teiko.db.DB_PATH: Path`, `teiko.db.CSV_PATH: Path`, `teiko.db.SCHEMA_PATH: Path`
  - `teiko.db.connect(db_path: Path = DB_PATH) -> sqlite3.Connection`
  - `teiko.db.apply_schema(conn: sqlite3.Connection) -> None`
  - `teiko.db.ensure_database(db_path: Path = DB_PATH, csv_path: Path = CSV_PATH) -> sqlite3.Connection`
  - `teiko.loading.POPULATIONS: list[tuple[str, str, int]]` — `(population, display_name, ordinal)`
  - `teiko.loading.POPULATION_NAMES: list[str]`
  - `teiko.loading.build_database(db_path: Path, csv_path: Path) -> dict[str, int]` — table name to row count

**Decisions this task forces:**
- **[LOG]** Rebuild the database from scratch on every run, or use `INSERT OR REPLACE`. Recommend dropping and rebuilding: it is simpler, guarantees idempotency, and takes under two seconds for 10,500 rows.

- [x] **Step 1: Write the failing loader tests**

Create `tests/test_loading.py`:

```python
import sqlite3
from pathlib import Path

import pytest

from teiko import db
from teiko.loading import build_database

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "tiny.csv"


@pytest.fixture
def real_db(tmp_path):
    path = tmp_path / "test.db"
    build_database(path, ROOT / "cell-count.csv")
    conn = db.connect(path)
    yield conn
    conn.close()


def row_counts(conn):
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("projects", "populations", "subjects", "samples", "cell_counts")
    }


def test_loader_writes_expected_row_counts(real_db):
    assert row_counts(real_db) == {
        "projects": 3,
        "populations": 5,
        "subjects": 3500,
        "samples": 10500,
        "cell_counts": 52500,
    }


def test_loading_twice_does_not_duplicate(tmp_path):
    path = tmp_path / "test.db"
    build_database(path, ROOT / "cell-count.csv")
    with db.connect(path) as first:
        before = row_counts(first)
    build_database(path, ROOT / "cell-count.csv")
    with db.connect(path) as second:
        assert row_counts(second) == before


def test_blank_responses_become_null_and_never_join_a_group(real_db):
    nulls = real_db.execute(
        "SELECT COUNT(*) FROM subjects WHERE response IS NULL"
    ).fetchone()[0]
    empty_strings = real_db.execute(
        "SELECT COUNT(*) FROM subjects WHERE response = ''"
    ).fetchone()[0]
    grouped = real_db.execute(
        "SELECT COUNT(*) FROM subjects WHERE response IN ('yes', 'no')"
    ).fetchone()[0]

    assert nulls == 474          # 1422 healthy rows / 3 samples per subject
    assert empty_strings == 0
    assert nulls + grouped == 3500


def test_foreign_keys_are_enforced_on_every_connection(tmp_path):
    path = tmp_path / "test.db"
    build_database(path, FIXTURE)
    conn = db.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cell_counts (sample_id, population, count)"
            " VALUES ('no_such_sample', 'b_cell', 1)"
        )
    conn.close()
```

- [x] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_loading.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'teiko'`.

- [x] **Step 3: Write `schema.sql`**

```sql
DROP VIEW  IF EXISTS sample_frequencies;
DROP TABLE IF EXISTS cell_counts;
DROP TABLE IF EXISTS samples;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS populations;
DROP TABLE IF EXISTS projects;

CREATE TABLE projects (
    project_id TEXT PRIMARY KEY
);

CREATE TABLE populations (
    population   TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    ordinal      INTEGER NOT NULL UNIQUE
);

CREATE TABLE subjects (
    subject_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    condition  TEXT NOT NULL,
    age        INTEGER CHECK (age > 0),
    sex        TEXT NOT NULL CHECK (sex IN ('M', 'F')),
    treatment  TEXT NOT NULL,
    response   TEXT CHECK (response IN ('yes', 'no'))
);

CREATE TABLE samples (
    sample_id                 TEXT PRIMARY KEY,
    subject_id                TEXT NOT NULL REFERENCES subjects(subject_id),
    sample_type               TEXT NOT NULL CHECK (sample_type IN ('PBMC', 'WB')),
    time_from_treatment_start INTEGER NOT NULL
);

CREATE TABLE cell_counts (
    sample_id  TEXT NOT NULL REFERENCES samples(sample_id),
    population TEXT NOT NULL REFERENCES populations(population),
    count      INTEGER NOT NULL CHECK (count >= 0),
    PRIMARY KEY (sample_id, population)
);

CREATE INDEX idx_subjects_cohort  ON subjects(condition, treatment, response);
CREATE INDEX idx_subjects_project ON subjects(project_id);
CREATE INDEX idx_samples_subject  ON samples(subject_id);
CREATE INDEX idx_samples_cohort   ON samples(sample_type, time_from_treatment_start);
CREATE INDEX idx_counts_pop       ON cell_counts(population);

-- The single definition of relative frequency. Everything downstream reads
-- this view, so the pipeline and the dashboard cannot disagree.
CREATE VIEW sample_frequencies AS
SELECT
    cc.sample_id                                   AS sample,
    SUM(cc.count) OVER (PARTITION BY cc.sample_id) AS total_count,
    cc.population,
    cc.count                                       AS count,
    100.0 * cc.count
      / SUM(cc.count) OVER (PARTITION BY cc.sample_id) AS percentage
FROM cell_counts cc;
```

- [x] **Step 4: Write `teiko/db.py`**

```python
"""Database paths, connections, and bootstrap."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "teiko.db"
CSV_PATH = ROOT / "cell-count.csv"
SCHEMA_PATH = ROOT / "schema.sql"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    # SQLite does not persist foreign_keys in the file; it is per connection.
    # Every connection in this project comes from here so the constraints hold.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def ensure_database(
    db_path: Path = DB_PATH, csv_path: Path = CSV_PATH
) -> sqlite3.Connection:
    """Open the database, building it first if it does not exist."""
    if not Path(db_path).exists():
        from teiko.loading import build_database

        build_database(Path(db_path), Path(csv_path))
    return connect(db_path)
```

- [x] **Step 5: Write `teiko/loading.py`**

```python
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
        # Verified constant across every subject's three samples, so first wins.
        subjects.setdefault(
            row["subject"],
            (
                row["subject"],
                row["project"],
                row["condition"],
                int(row["age"]),
                row["sex"],
                row["treatment"],
                row["response"] or None,
            ),
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
```

- [x] **Step 6: Write `load_data.py`**

```python
"""Part 1: build teiko.db from cell-count.csv.

Run as `python load_data.py` from anywhere. Takes no arguments.
"""
from teiko.db import CSV_PATH, DB_PATH
from teiko.loading import build_database


def main() -> None:
    counts = build_database(DB_PATH, CSV_PATH)
    print(f"Built {DB_PATH.name} from {CSV_PATH.name}")
    for table, count in counts.items():
        print(f"  {table:<12} {count:>6,} rows")


if __name__ == "__main__":
    main()
```

Create an empty `teiko/__init__.py`.

- [x] **Step 7: Run the tests**

Run: `python -m pytest tests/test_loading.py -v`

Expected: PASS, 4 tests. If `test_blank_responses_become_null_and_never_join_a_group` fails on the count, print the actual number and confirm it equals 1422 divided by 3.

- [x] **Step 8: Run the script the way the grader will**

Run: `python load_data.py`

Expected output:

```
Built teiko.db from cell-count.csv
  projects            3 rows
  populations         5 rows
  subjects        3,500 rows
  samples        10,500 rows
  cell_counts    52,500 rows
```

Then run it a second time and confirm the numbers are identical.

- [x] **Step 9: Commit and push**

```bash
git add schema.sql teiko/ load_data.py tests/test_loading.py
git commit -m "add schema and csv loader for part 1"
git push origin main
```

---

## Task 3: Relative frequencies

**Files:**
- Create: `teiko/frequencies.py`, `tests/test_frequencies.py`

**Interfaces:**
- Consumes: `teiko.db.connect`, `teiko.loading.build_database`.
- Produces: `teiko.frequencies.summary_table(conn) -> pandas.DataFrame` with columns `sample`, `total_count`, `population`, `count`, `percentage`, ordered by sample then `populations.ordinal`.

**Decisions this task forces:**
- **[ASK]** Whether `outputs/summary_table.csv` rounds `percentage` to 4 decimal places on write. The spec says 4. Confirm before writing 52,500 rows, since the file is committed and the choice shows in the diff.

- [x] **Step 1: Write the failing tests**

Create `tests/test_frequencies.py`:

```python
from pathlib import Path

import pytest

from teiko import db
from teiko.frequencies import summary_table
from teiko.loading import build_database

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "tiny.csv"


@pytest.fixture
def fixture_db(tmp_path):
    path = tmp_path / "tiny.db"
    build_database(path, FIXTURE)
    conn = db.connect(path)
    yield conn
    conn.close()


@pytest.fixture
def real_db(tmp_path):
    path = tmp_path / "real.db"
    build_database(path, ROOT / "cell-count.csv")
    conn = db.connect(path)
    yield conn
    conn.close()


def test_percentages_match_hand_computed_values(fixture_db):
    frame = summary_table(fixture_db)
    first = frame[frame["sample"] == "sampleT0"].set_index("population")

    # sampleT0 totals 100 cells, so each percentage equals its count.
    assert first.loc["b_cell", "total_count"] == 100
    assert first.loc["b_cell", "percentage"] == pytest.approx(10.0)
    assert first.loc["cd8_t_cell", "percentage"] == pytest.approx(20.0)
    assert first.loc["cd4_t_cell", "percentage"] == pytest.approx(30.0)
    assert first.loc["nk_cell", "percentage"] == pytest.approx(20.0)
    assert first.loc["monocyte", "percentage"] == pytest.approx(20.0)

    # sampleT1 is five populations of one cell each.
    second = frame[frame["sample"] == "sampleT1"]
    assert second["total_count"].unique().tolist() == [5]
    assert second["percentage"].tolist() == pytest.approx([20.0] * 5)


def test_population_order_is_fixed_not_alphabetical(fixture_db):
    frame = summary_table(fixture_db)
    order = frame[frame["sample"] == "sampleT0"]["population"].tolist()
    assert order == ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


def test_every_sample_percentages_sum_to_one_hundred(real_db):
    frame = summary_table(real_db)
    assert len(frame) == 52_500
    totals = frame.groupby("sample")["percentage"].sum()
    assert len(totals) == 10_500
    assert totals.min() == pytest.approx(100.0)
    assert totals.max() == pytest.approx(100.0)
```

- [x] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_frequencies.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'teiko.frequencies'`.

- [x] **Step 3: Write `teiko/frequencies.py`**

```python
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
```

- [x] **Step 4: Run the tests**

Run: `python -m pytest tests/test_frequencies.py -v`

Expected: PASS, 3 tests.

- [x] **Step 5: Commit and push**

```bash
git add teiko/frequencies.py tests/test_frequencies.py
git commit -m "add relative frequency query for part 2"
git push origin main
```

---

## Task 4: Statistics

**Files:**
- Create: `teiko/statistics.py`, `tests/test_statistics.py`

**Interfaces:**
- Consumes: `teiko.frequencies.summary_table`.
- Produces:
  - `teiko.statistics.benjamini_hochberg(pvalues: list[float]) -> list[float]`
  - `teiko.statistics.cliffs_delta(a, b) -> float`
  - `teiko.statistics.magnitude(delta: float) -> str` — `"negligible" | "small" | "medium" | "large"`
  - `teiko.statistics.RESPONSE_COHORT: str` — the SQL WHERE clause for melanoma / miraclib / PBMC
  - `teiko.statistics.cohort_frequencies(conn) -> pandas.DataFrame` — columns `sample`, `subject`, `response`, `timepoint`, `population`, `percentage`
  - `teiko.statistics.compare_responders(conn) -> pandas.DataFrame` — one row per population, columns as listed in spec section 8
  - `teiko.statistics.compare_by_timepoint(conn) -> pandas.DataFrame` — the same statistics per population per timepoint

**Decisions this task forces:**
- **[LOG]** Implement Benjamini-Hochberg by hand or call `scipy.stats.false_discovery_control`. Recommend by hand: it is seven lines, it makes test 7 meaningful, and it avoids depending on a scipy version floor.
- **[ASK]** Whether `compare_responders` reports the Welch t-test p-value as a column. The spec says yes, as evidence the conclusion does not depend on the test. Confirm, since it adds a column to a committed output file.

- [x] **Step 1: Write the failing tests**

Create `tests/test_statistics.py`:

```python
from pathlib import Path

import pytest

from teiko import db
from teiko.loading import build_database
from teiko.statistics import (
    benjamini_hochberg,
    cliffs_delta,
    compare_responders,
    magnitude,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("stats") / "real.db"
    build_database(path, ROOT / "cell-count.csv")
    conn = db.connect(path)
    yield conn
    conn.close()


def test_identical_groups_are_not_significant():
    from teiko.statistics import mann_whitney

    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    _, p = mann_whitney(values, list(values))
    assert p > 0.9


def test_clearly_separated_groups_are_significant():
    from teiko.statistics import mann_whitney

    low = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    high = [21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0]
    _, p = mann_whitney(low, high)
    assert p < 0.05


def test_cliffs_delta_and_magnitude_bands():
    low = [1.0, 2.0, 3.0, 4.0]
    high = [11.0, 12.0, 13.0, 14.0]
    assert cliffs_delta(low, high) == pytest.approx(-1.0)
    assert cliffs_delta(high, low) == pytest.approx(1.0)
    assert cliffs_delta(low, list(low)) == pytest.approx(0.0)
    assert magnitude(0.10) == "negligible"
    assert magnitude(0.20) == "small"
    assert magnitude(0.40) == "medium"
    assert magnitude(0.60) == "large"


def test_benjamini_hochberg_on_known_values():
    # Classic worked example: five p-values, m/k scaling, enforced monotone.
    raw = [0.01, 0.02, 0.03, 0.04, 0.05]
    adjusted = benjamini_hochberg(raw)
    assert adjusted == pytest.approx([0.05, 0.05, 0.05, 0.05, 0.05])

    assert benjamini_hochberg([0.001, 0.5]) == pytest.approx([0.002, 0.5])
    assert benjamini_hochberg([0.04]) == pytest.approx([0.04])


def test_no_population_is_significant_in_the_real_cohort(real_db):
    frame = compare_responders(real_db).set_index("population")

    assert sorted(frame["n_responder"].unique()) == [993]
    assert sorted(frame["n_non_responder"].unique()) == [975]
    assert not frame["significant"].any()
    assert frame["q_value"].min() > 0.05
    assert frame["cliffs_delta"].abs().max() < 0.147
    assert (frame["effect_magnitude"] == "negligible").all()


def test_cd4_is_the_trap_and_correction_defuses_it(real_db):
    frame = compare_responders(real_db).set_index("population")
    cd4 = frame.loc["cd4_t_cell"]

    # Uncorrected this reads as a finding; corrected it does not.
    assert cd4["p_value"] < 0.05
    assert cd4["q_value"] > 0.05
```

- [x] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_statistics.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'teiko.statistics'`.

- [x] **Step 3: Write `teiko/statistics.py`**

```python
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
```

- [x] **Step 4: Run the tests**

Run: `python -m pytest tests/test_statistics.py -v`

Expected: PASS, 6 tests.

If `test_no_population_is_significant_in_the_real_cohort` fails, do not adjust the assertion. Print the table and compare against spec section 8, which lists the verified values: cd4_t_cell p = 0.0133 and q = 0.0667, and the largest Cliff's delta anywhere is 0.110.

- [x] **Step 5: Commit and push**

```bash
git add teiko/statistics.py tests/test_statistics.py
git commit -m "add mann-whitney comparison with fdr correction for part 3"
git push origin main
```

---

## Task 5: Plots

**Files:**
- Create: `teiko/plots.py`
- Modify: `tests/test_statistics.py` — append one smoke test

**Interfaces:**
- Consumes: `teiko.statistics.cohort_frequencies`, `teiko.loading.POPULATIONS`.
- Produces:
  - `teiko.plots.responder_boxplots(conn) -> matplotlib.figure.Figure`
  - `teiko.plots.timepoint_boxplots(conn) -> matplotlib.figure.Figure`

**Decisions this task forces:**
- **[LOG]** Whether the figures annotate each panel with its q-value. Recommend yes for the main figure: a boxplot showing two near-identical distributions is more convincing with the number printed on it.

- [x] **Step 1: Write the failing smoke test**

Append to `tests/test_statistics.py`:

```python
def test_both_figures_render_with_five_panels(real_db):
    from teiko.plots import responder_boxplots, timepoint_boxplots

    main = responder_boxplots(real_db)
    assert len(main.axes) == 5

    faceted = timepoint_boxplots(real_db)
    assert len(faceted.axes) == 15  # five populations by three timepoints
```

- [x] **Step 2: Run it and watch it fail**

Run: `python -m pytest tests/test_statistics.py::test_both_figures_render_with_five_panels -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'teiko.plots'`.

- [x] **Step 3: Write `teiko/plots.py`**

```python
"""Boxplots for Part 3."""
import sqlite3

import matplotlib

matplotlib.use("Agg")  # No display in Codespaces or on Streamlit Cloud.
import matplotlib.pyplot as plt  # noqa: E402

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
    fig.suptitle(
        "Melanoma, miraclib, PBMC — no population differs significantly "
        "after correction",
        fontsize=12,
    )
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

    fig.suptitle(
        "By timepoint — groups are indistinguishable at baseline; "
        "a weak B cell difference appears after dosing",
        fontsize=12,
    )
    fig.tight_layout()
    return fig
```

- [x] **Step 4: Run the test**

Run: `python -m pytest tests/test_statistics.py -v`

Expected: PASS, 7 tests.

- [x] **Step 5: Commit and push**

```bash
git add teiko/plots.py tests/test_statistics.py
git commit -m "add responder boxplots and timepoint facets"
git push origin main
```

---

## Task 6: Part 4 subsets

**Files:**
- Create: `teiko/subsets.py`, `tests/test_subsets.py`

**Interfaces:**
- Consumes: `teiko.db.connect`.
- Produces:
  - `teiko.subsets.baseline_cohort(conn) -> pandas.DataFrame` — Cohort A, columns `sample`, `subject`, `project`, `response`, `sex`
  - `teiko.subsets.baseline_breakdowns(conn) -> pandas.DataFrame` — columns `breakdown`, `category`, `count`, `unit`
  - `teiko.subsets.melanoma_male_baseline_b_cell_mean(conn) -> tuple[int, float]` — Cohort B sample count and mean

**Decisions this task forces:**
- **[LOG]** How to make `prj2` appear with a count of zero. Recommend a `LEFT JOIN` from `projects`, so the zero comes from the database rather than being patched in afterwards.

- [x] **Step 1: Write the failing tests**

Create `tests/test_subsets.py`:

```python
from pathlib import Path

import pytest

from teiko import db
from teiko.loading import build_database
from teiko.subsets import (
    baseline_breakdowns,
    baseline_cohort,
    melanoma_male_baseline_b_cell_mean,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("subsets") / "real.db"
    build_database(path, ROOT / "cell-count.csv")
    conn = db.connect(path)
    yield conn
    conn.close()


def test_cohort_a_size(real_db):
    cohort = baseline_cohort(real_db)
    assert len(cohort) == 656
    assert cohort["subject"].nunique() == 656


def test_cohort_a_breakdowns_including_the_empty_project(real_db):
    frame = baseline_breakdowns(real_db)

    projects = frame[frame["breakdown"] == "project"].set_index("category")
    assert projects.loc["prj1", "count"] == 384
    assert projects.loc["prj2", "count"] == 0   # must be present, not omitted
    assert projects.loc["prj3", "count"] == 272
    assert (projects["unit"] == "samples").all()

    response = frame[frame["breakdown"] == "response"].set_index("category")
    assert response.loc["yes", "count"] == 331
    assert response.loc["no", "count"] == 325
    assert (response["unit"] == "subjects").all()

    sex = frame[frame["breakdown"] == "sex"].set_index("category")
    assert sex.loc["M", "count"] == 344
    assert sex.loc["F", "count"] == 312
    assert (sex["unit"] == "subjects").all()


def test_cohort_b_drops_the_pbmc_and_miraclib_filters(real_db):
    """Guards the filter trap. Keeping those filters gives 184 and 10401.28."""
    n, mean = melanoma_male_baseline_b_cell_mean(real_db)
    assert n == 485
    assert round(mean, 2) == 10206.15
```

- [x] **Step 2: Run them and watch them fail**

Run: `python -m pytest tests/test_subsets.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'teiko.subsets'`.

- [x] **Step 3: Write `teiko/subsets.py`**

```python
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
```

- [x] **Step 4: Run the tests**

Run: `python -m pytest tests/test_subsets.py -v`

Expected: PASS, 3 tests.

- [x] **Step 5: Commit and push**

```bash
git add teiko/subsets.py tests/test_subsets.py
git commit -m "add part 4 cohort queries with explicit zero for empty project"
git push origin main
```

---

## Task 7: Pipeline entry point

**Files:**
- Create: `run_pipeline.py`

**Interfaces:**
- Consumes: everything from Tasks 2 to 6.
- Produces: seven files in `outputs/` — `summary_table.csv`, `responder_comparison.csv`, `timepoint_comparison.csv`, `boxplots.png`, `boxplots_by_timepoint.png`, `part4_baseline_samples.csv`, `part4_breakdowns.csv`, `part4_answers.md`.

**Decisions this task forces:**
- **[ASK]** `outputs/summary_table.csv` is 52,500 rows and roughly 2 MB, and it is committed. Confirm that is wanted, or whether to commit a sample and generate the full file at run time.

- [x] **Step 1: Write `run_pipeline.py`**

```python
"""Run Parts 2 to 4 and write everything into outputs/.

Assumes load_data.py has already built the database. `make pipeline` runs both.
"""
from teiko.db import ROOT, ensure_database
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

{n_samples} samples from {n_samples} subjects, since each subject contributes
one baseline sample.

- Samples per project: {project_line}.
- Subjects by response: {response.loc['yes', 'count']} responders,
  {response.loc['no', 'count']} non-responders.
- Subjects by sex: {sex.loc['M', 'count']} male, {sex.loc['F', 'count']} female.

## Cohort B — melanoma males, all sample and treatment types, day 0

The brief widens the filters here: no PBMC restriction and no treatment
restriction.

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
        print(f"part4 files                {len(cohort):>6,} baseline samples")
        print(f"Cohort B average B cell count: {mean_b:.2f} over {n_b} samples")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [x] **Step 2: Run the full pipeline the way the grader will**

Run: `rm -f teiko.db && make pipeline`

Expected: the loader summary from Task 2, then eight output lines ending with
`Cohort B average B cell count: 10206.15 over 485 samples`.

- [x] **Step 3: Confirm every output file exists**

Run: `ls -la outputs/`

Expected: eight files plus `.gitkeep`.

- [x] **Step 4: Run the whole test suite**

Run: `make test`

Expected: PASS, 14 tests.

- [x] **Step 5: Commit and push**

```bash
git add run_pipeline.py outputs/
git commit -m "add pipeline entry point and generated outputs"
git push origin main
```

---

## Task 8: Dashboard

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `teiko.db.ensure_database` and every analysis function.
- Produces: a Streamlit app with four tabs.

**Decisions this task forces:**
- **[ASK]** Whether the Response Analysis tab lets the user change the cohort away from melanoma / miraclib / PBMC. Generalised dropdowns make it a real tool; fixed values keep it exactly on the brief. Recommend generalised with those as defaults.

- [x] **Step 1: Write `app.py`**

```python
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
        width="stretch",
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
    st.dataframe(merged.head(1000), width="stretch")
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
        st.info(
            "No cell population differs significantly between responders and "
            "non-responders after Benjamini-Hochberg correction. Every effect "
            "size is negligible. CD4 T cells reach p = "
            f"{table.set_index('population').loc['cd4_t_cell', 'p_value']:.4f} "
            "uncorrected, which is exactly the result that disappears once the "
            "five tests are corrected together."
        )
    st.pyplot(responder_boxplots(conn))
    st.dataframe(table, width="stretch")

    st.markdown("#### The same comparison at each timepoint")
    st.markdown(
        "At baseline the two groups are indistinguishable. A weak B cell "
        "difference appears after dosing and strengthens by day 14, but never "
        "reaches significance. That makes it an observation about what the "
        "drug does, not a way to predict who will respond."
    )
    st.dataframe(compare_by_timepoint(conn), width="stretch")
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
            breakdowns[breakdowns["breakdown"] == name], width="stretch"
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
```

- [x] **Step 2: Start it and check every tab**

Run: `make dashboard`

Open the local URL. Confirm each of the four tabs renders, the filters on the
Frequencies tab change the row count, and the Response tab shows the
no-significant-difference message rather than a blank panel.

- [x] **Step 3: Confirm the bootstrap path works**

Run: `rm -f teiko.db && make dashboard`

Expected: the app builds the database on first load and renders normally. This
is the path Streamlit Cloud takes. Then run `make pipeline` to restore the
database.

- [x] **Step 4: Commit and push**

```bash
git add app.py
git commit -m "add streamlit dashboard with four tabs"
git push origin main
```

---

## Task 9: Deploy

**Files:** none in the repository.

**Interfaces:**
- Consumes: `app.py` and `requirements.txt` from the pushed repository.
- Produces: a public URL, used by Task 10's README.

**Decisions this task forces:** none.

- [x] **Step 1: Deploy**

Go to `share.streamlit.io`, sign in with GitHub, and create a new app from
`HardikLad10/teiko-immune-analysis`, branch `main`, main file path `app.py`.

- [x] **Step 2: Watch the build log**

Confirm the dependencies install and the app reaches "Your app is live".

- [x] **Step 3: Open the public URL and check all four tabs**

The first load builds the database from the CSV and will take a few seconds.
Confirm the Response tab shows the statistics table, not an error.

- [x] **Step 4: Record the URL**

https://teiko-immune-analysis-hardikv3.streamlit.app/ — Python 3.12 on
Community Cloud. Overview shows 10206.15. In the README in Task 10.

---

## Task 10: README and Codespaces verification

**Files:**
- Create: `README.md`
- Modify: `docs/DECISIONS.md` — append any entries from tasks that deferred them

**Interfaces:**
- Consumes: the dashboard URL from Task 9 and every output from Task 7.
- Produces: the final submission.

**Decisions this task forces:**
- **[ASK]** How much of the negative result belongs in the README versus the dashboard. Recommend the README states the conclusion and the reasoning in full, since a grader may read it without opening the app.

- [x] **Step 1: Write `README.md`**

Six sections, in this order, following the spec's section 12. Write the prose
fresh rather than pasting from the spec, and obey the banned word list.

1. **What this is** — one paragraph naming the dataset, the four questions, and
   the deliverables.
2. **How to run it** — `make setup`, `make pipeline`, `make dashboard`, with
   what each produces and roughly how long it takes.
3. **The schema** — the five tables, why counts are long, why treatment and
   response sit on `subjects`, why `PRAGMA foreign_keys` is issued per
   connection, and how the design behaves at hundreds of projects and thousands
   of samples. This is a graded section; give it real length.
4. **Code structure** — the thin entry points, the `teiko/` package, why it is
   not under `src/`, and how the pipeline and dashboard share one
   implementation.
5. **Results** — the Part 2 output, the Part 3 conclusion including that
   nothing is significant and why that is the honest answer, the per-timepoint
   pattern, and the Part 4 answers with both cohorts described separately.
6. **Dashboard** — the URL from Task 9.

- [x] **Step 2: Verify the README's numbers against the outputs**

Run: `cat outputs/part4_answers.md`

Every number in the README's results section must match this file exactly. Do
not retype them from memory.

- [x] **Step 3: Run the full suite and the full pipeline from clean**

```bash
rm -rf teiko.db outputs/*.csv outputs/*.png outputs/*.md
make setup && make pipeline && make test
```

Expected: pipeline prints `Cohort B average B cell count: 10206.15 over 485
samples`, and 14 tests pass.

- [ ] **Step 4: Verify in an actual Codespace**

Open the repository on GitHub, create a Codespace on `main`, and run all three
targets there. A local run does not count as this check. Confirm
`make dashboard` serves and the forwarded port opens.

Local clean run on 2026-09-05: `make setup && make pipeline && make test`
printed `Cohort B average B cell count: 10206.15 over 485 samples` and
18 tests passed. `gh` on this machine has an invalid token, so the
Codespace itself still needs a human.

- [x] **Step 5: Final canary sweep**

```bash
python -m pytest tests/test_integrity.py -v
```

Expected: the test passes. It is the allowlist check from spec section 14 —
it fails if any tracked file names a treatment that is not in the data.

- [x] **Step 6: Commit and push**

```bash
git add README.md outputs/ docs/DECISIONS.md
git commit -m "add readme with schema rationale and results"
git push origin main
```

---

## Self-Review

**Spec coverage.** Section 4 schema — Task 2. Section 5 code layout — Tasks 2
to 8. Section 6 Part 1 — Task 2. Section 7 Part 2 — Task 3. Section 8 Part 3 —
Tasks 4 and 5. Section 9 Part 4 — Task 6. Section 10 dashboard — Tasks 8 and 9.
Section 11 Makefile — Task 1. Section 12 README — Task 10. Section 13's ten
tests — test 10 in Task 1, tests 1 to 3 in Task 2, tests 4 and 5 in Task 3,
tests 6 and 7 in Task 4, tests 8 and 9 in Task 6. Section 14 writing rules —
Global Constraints. Section 1's "whose claim is being tested" — carried by
Task 4's `test_cd4_is_the_trap_and_correction_defuses_it` and Task 8's response
tab copy.

Two additions beyond the spec's ten tests, both cheap and both guarding
something real: a foreign key enforcement test in Task 2, since D-017 says the
pragma is the whole guarantee, and a figure smoke test in Task 5. Fourteen
tests total.

**Placeholder scan.** No TBD, TODO, or "handle edge cases". Every code step
carries the code. Every run step carries the command and the expected output.

**Type consistency.** `build_database(db_path, csv_path) -> dict[str, int]` is
defined in Task 2 and used in Tasks 3, 4, and 6. `connect` returns a
`sqlite3.Connection` with `row_factory` set, which Task 6's
`melanoma_male_baseline_b_cell_mean` relies on for `row["n"]`.
`compare_responders` produces the sixteen columns Task 7 writes and Task 8
displays. `cliffs_delta` is defined once in Task 4 and consumed by Task 5's
titles through `compare_responders`.
