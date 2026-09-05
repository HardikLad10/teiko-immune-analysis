# Teiko immune analysis

## What this is

A take-home analysis of `cell-count.csv`: 10,500 samples from 3,500 subjects
across three projects, each sample counted for five immune cell populations.
The work answers the four parts of the brief. Part 1 loads the CSV into a
SQLite database. Part 2 computes relative frequencies. Part 3 tests whether
any population differs between melanoma responders and non-responders on
miraclib (PBMC only). Part 4 reports two subset queries, including the mean
raw B cell count the brief asks for. The deliverables are the database
pipeline, committed files in `outputs/`, this README, and a hosted Streamlit
dashboard.

## How to run it

Tested on Python 3.11 (GitHub Codespaces), 3.12 (this laptop), and 3.12
(Streamlit Community Cloud). `requirements.txt` lists package names without
pins so those three Pythons can install wheels. From the repository root:

```bash
make setup      # install the packages in requirements.txt
make pipeline   # build teiko.db and write everything in outputs/
make dashboard  # start the Streamlit app
```

`make setup` upgrades pip and installs pandas, numpy, scipy, matplotlib,
streamlit, and pytest. A few minutes on a cold machine; much faster if the
packages are already cached.

`make pipeline` runs `python load_data.py` then `python run_pipeline.py`.
The first script drops and rebuilds `teiko.db`. The second writes the
summary table, the responder and timepoint statistics, two boxplot figures,
the Part 4 answers, and `outputs/dashboard_metrics.csv`. On a laptop this
is about a minute. The last line should read:

```
Cohort B average B cell count: 10206.15 over 485 samples
```

`make dashboard` serves `app.py`. On a laptop, open http://localhost:8501.

**GitHub Codespaces.** On github.com open
`HardikLad10/teiko-immune-analysis`, branch `main`, then Code → Codespaces
→ Create codespace on main. In that terminal run the same three `make`
commands. After `make dashboard`, open the forwarded port **8501** in the
Ports tab (the URL is `*.app.github.dev`, not localhost on your computer).
The container installs packages on update; `make setup` is still the
command the grader runs.

Overview, Response, and Subsets read the committed files in `outputs/`.
Frequencies builds `teiko.db` if it is missing, then queries it. If an
output file is absent, the app says to run `make pipeline`.

`make test` runs the pytest suite. It is not required by the brief. The
tests check loading, percentage calculations, statistical utilities, and
the required subset answers.

## The schema

Each project contains subjects. Each subject contributes samples. Each
sample has one count for each measured population. The `populations` table
names the cell types. A **view** (a saved SQL query that behaves like a
table) calculates each count as a percentage of that sample’s measured
total.

The combination of sample ID and population identifies one measurement, so
the same pair cannot be stored twice. That does not require every sample
to contain all five populations; the current loader writes all five. If
the input later has holes, that needs a check, not a silent smaller panel.

**`projects`** holds one row per project (`prj1`, `prj2`, `prj3`). Today it
has a single column, `project_id`. Extra project facts (site, protocol)
would attach here once.

**`populations`** is a lookup: `b_cell`, `cd8_t_cell`, `cd4_t_cell`,
`nk_cell`, `monocyte`, each with a display name and an **ordinal** (display
order). That order is this project’s choice so tables stay comparable; the
brief names the five populations but does not require a presentation
order. Statistics queries sort by `ordinal`. Charts also keep a label map
in `teiko/plots.py`, so the lookup table is not the only source of chart
labels.

The storage model can accept another population as an insert. The loader
and the plot layout still list five names and would need edits. Adding a
population also changes the percentage denominator, because `total_count`
is the sum of the measured panel, not the true tube total. Percentages
sum to 100 by construction for the populations that are present.

**`subjects`** holds one row per person: project, condition, age, sex,
treatment, and response. Treatment and response sit here because they are
constant across all three of a subject's samples in this file. Storing them
once makes it impossible for the same person to appear as both a responder
and a non-responder. In a real trial, response is assessed over time and
would belong on `samples` or in its own table. Repeated enrollments or a
change of treatment would also need a richer model.

Subject IDs and sample IDs are assumed unique across the whole file, not
only inside one project. The loader rejects a subject whose project,
condition, age, sex, treatment, or response is not the same on every row.

The 474 healthy subjects (1,422 samples) have a blank response in the CSV.
Those become SQL `NULL`. `NULL` is in neither `response = 'yes'` nor
`response = 'no'`, which is what unknown should mean.

**`samples`** holds one row per draw: the subject, `PBMC` or `WB`, and
`time_from_treatment_start` (0, 7, or 14).

**`cell_counts`** is long, not wide: one row per sample per population,
52,500 rows. A wide table with five count columns would need a schema
change for every new population.

**`sample_frequencies`** is the view over `cell_counts`. It is the only
SQL definition of relative frequency. The pipeline computes statistics
from it. The dashboard Overview, Response, and Subsets display the files
that pipeline wrote; those files can go stale if someone changes the CSV
and skips `make pipeline`.

A **foreign key** is a rule that a referenced row must exist. Foreign keys
are declared in `schema.sql` (**DDL**: the SQL that defines tables). SQLite
leaves them off unless the connection says `PRAGMA foreign_keys = ON`.
That pragma is issued in `teiko.db.connect` on every open. A test inserts
a count for a sample that does not exist and checks that it fails.

At the scale the brief names — hundreds of projects and thousands of
samples — this file already has thousands of samples. Subject facts stay
one row per person as more timepoints arrive, so a metadata correction is
a one-row update. Cohort filters hit `subjects`. New questions are usually
new queries; some need new columns or new files. `cell_counts` grows with
both samples and populations. The table definitions are close to what
Postgres would use; moving the running system also means connections,
backups, and how writes are locked. SQLite allows one writer at a time.

The CSV's real column names win over the brief: `sample`, `condition`,
and `sex`, not `sample_id`, `indication`, or `gender`. The loader reads
the file, not the prompt.

## Code structure

The brief requires `load_data.py` at the root, run as
`python load_data.py` with no arguments. `run_pipeline.py` and `app.py`
are the other two entry points this project uses. Codespaces graders run
the Makefile targets, which call these scripts.

| File | What it does |
| --- | --- |
| `load_data.py` | Calls `build_database` and prints row counts. |
| `run_pipeline.py` | Writes every file in `outputs/`. |
| `app.py` | The Streamlit dashboard. |

The work lives in `teiko/`, imported as `teiko`, not `src.teiko`. A
`src/` layout would need a package install or a `PYTHONPATH` before
`python load_data.py` worked.

| Module | What it does |
| --- | --- |
| `teiko/db.py` | Connect (pragma on), apply `schema.sql`, build the database if it is missing. |
| `teiko/loading.py` | CSV into the five tables. Drops and rebuilds on every load. |
| `teiko/frequencies.py` | Reads `sample_frequencies` for Part 2. |
| `teiko/statistics.py` | Mann-Whitney U, hand-written Benjamini-Hochberg, Cliff's delta, Welch t-test. |
| `teiko/subsets.py` | The two Part 4 SQL queries. |
| `teiko/plots.py` | The two boxplot figures. |
| `teiko/display.py` | Turns generated tables into dashboard sentences and metric cards. |

`schema.sql` is the DDL and the view. `tests/` checks loading, percentages,
the correction, both Part 4 answers, and an allowlist of treatment names
so a name that is not in the data cannot sit in a tracked file.
`docs/SPEC.md` is the contract. `docs/DECISIONS.md` is the paper trail.

The pipeline calls the analysis functions and writes `outputs/`. The
dashboard reads those files for Overview, Response, and Subsets. It does
not re-run Mann-Whitney on those pages.

## Results

A **cohort** here is the selected group of samples or subjects.

### Part 2 — relative frequencies

`outputs/summary_table.csv` has 52,500 rows: one per sample per
population. For each sample the five percentages sum to 100. Values stay
unrounded in the database; the CSV rounds percentages to four decimal
places for reading.

### Part 3 — responders versus non-responders

Cohort: melanoma, miraclib, PBMC only. 656 subjects (331 responders, 325
non-responders) and 1,968 samples (993 / 975).

Method: two-sided Mann-Whitney U on relative frequency, Benjamini-Hochberg
across the five populations, Cliff's delta as the **effect size** (how
different the groups are). The brief’s frequency table is one row per
sample per population (1,968 samples, 9,840 frequency rows). Those rows
are not independent: each subject appears
three times. The **conclusion** therefore uses the already-computed
per-subject means (656 independent observations). The pooled-sample tests
and boxplots stay in the output as exploratory description of the same
table. A day-0-only column is the slice that a pre-treatment question
needs. A Welch t-test on the pooled rows is also stored; it is not the
conclusion (the frequencies are skewed, and the rows are still repeated
subjects). After Benjamini-Hochberg, CD4 Welch q on the pooled rows is
about 0.025.

**Conclusion (one mean per subject):** no population differs significantly
after Benjamini-Hochberg. Smallest subject-mean q is about 0.062 (CD4).
At baseline, every corrected q is about 0.885.

The exploratory pooled CD4 Mann-Whitney p is about 0.0133; after
correction that is q about 0.0667. A Welch t-test on those same pooled
rows gives p about 0.005. Those are different hypotheses. The
`significant` column in `responder_comparison.csv` still flags the pooled
Mann-Whitney q (D-007). The prose conclusion uses the subject-mean
column.

A B cell median shift appears after day 0. It is never significant under
the within-day correction. That correction is five tests per timepoint,
not fifteen tests in one family. The smallest of those within-day q
values is about 0.072 on day 14. Every Cliff's delta is in the
“negligible” band used here (below 0.147); the largest anywhere is 0.110.
At day 0 the B cell median difference is +0.03; at day 7 and day 14 it is
about −0.73. CD4 peaks at day 7 and eases back.

Bob asked about a signal that could be used before treatment starts. Day 0
is the slice that question needs. On that slice, after correction, no
population meets p < 0.05. These tests do not prove the groups are the
same, do not prove the drug caused the later movement, and do not prove
there is no predictive information of any kind. They show no significant
difference on these five frequencies under the tests above.

Full tables: `outputs/responder_comparison.csv` and
`outputs/timepoint_comparison.csv`. Figures: `outputs/boxplots.png` and
`outputs/boxplots_by_timepoint.png`.

### Part 4 — subsets

The final question uses a broader cohort than the earlier baseline query.

**Cohort A** — melanoma, PBMC, miraclib, day 0. 656 samples from 656
subjects.

- Samples per project: prj1 384, prj2 0, prj3 272.
- Subjects by response: 331 responders, 325 non-responders.
- Subjects by sex: 344 male, 312 female.

`prj2` has zero rows in this slice and is still listed. A plain
`GROUP BY` would drop it.

**Cohort B** — melanoma males who responded, day 0, all sample types and
all treatments. 485 samples. Average raw B cell count: **10206.15**.

Raw count, not percentage. Keeping the earlier filters gives a different
mean on fewer samples.

## Dashboard

Hosted copy: <https://teiko-immune-analysis-hardikv3.streamlit.app/>

Local laptop: `make dashboard`, then open http://localhost:8501.

Codespaces: `make setup`, `make pipeline`, `make dashboard`, then open
forwarded port 8501.
