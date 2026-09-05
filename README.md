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

Needs Python 3.10 or newer. From the repository root:

```bash
make setup      # install the packages in requirements.txt
make pipeline   # build teiko.db and write everything in outputs/
make dashboard  # start the Streamlit app on http://localhost:8501
```

`make setup` upgrades pip and installs pandas, numpy, scipy, matplotlib,
streamlit, and pytest. A few minutes on a cold machine; much faster if the
packages are already cached.

`make pipeline` runs `python load_data.py` then `python run_pipeline.py`.
The first script drops and rebuilds `teiko.db`. The second writes the
summary table, the responder and timepoint statistics, two boxplot figures,
and the Part 4 answers. On a laptop this is about a minute. The last line
should read:

```
Cohort B average B cell count: 10206.15 over 485 samples
```

`make dashboard` serves `app.py`. The first visit after a clean checkout
builds the database if `teiko.db` is missing, which is the path Streamlit
Cloud takes. Overview, Response, and Subsets read the committed files in
`outputs/`. Frequencies queries the database.

`make test` runs the pytest suite. It is not required by the brief, but it
is how the traps in Parts 3 and 4 stay pinned.

## The schema

Five tables and one view.

**`projects`** holds one row per project (`prj1`, `prj2`, `prj3`). Today it
has a single column, `project_id`. That is deliberate. If the company grew
to hundreds of projects, site, protocol, sponsor, and dates would attach
here once, not be copied onto every sample.

**`populations`** is a lookup: `b_cell`, `cd8_t_cell`, `cd4_t_cell`,
`nk_cell`, `monocyte`, each with a display name and an `ordinal`. The brief
fixes that order, and it is not alphabetical. Putting the order in the
table means every chart and every exported table sorts in SQL instead of
hardcoding the same list in five places. A sixth population would be an
insert, not an `ALTER TABLE`.

**`subjects`** holds one row per person: project, condition, age, sex,
treatment, and response. Treatment and response sit here because they are
constant across all three of a subject's samples in this file. Storing them
once makes it impossible for the same person to appear as both a responder
and a non-responder. In a real trial, response is assessed over time and
would belong on `samples` or in its own table. It is modelled at subject
level because this dataset makes that true, not because that is always
right.

The 1,422 healthy subjects have a blank response in the CSV. Those become
SQL `NULL`. `NULL` is in neither `response = 'yes'` nor `response = 'no'`,
which is what unknown should mean.

**`samples`** holds one row per draw: the subject, `PBMC` or `WB`, and
`time_from_treatment_start` (0, 7, or 14).

**`cell_counts`** is long, not wide: one row per sample per population,
52,500 rows. A wide table with five count columns would need a schema
change and query edits for every new population. Long form does not.

`total_count` is the sum of those five measured populations, not the true
total cell count of the tube. Percentages are shares of the measured panel.
They sum to 100 by construction.

**`sample_frequencies`** is a view over `cell_counts`. It is the only
definition of relative frequency. The pipeline, the statistics, and the
dashboard all read it. They cannot drift apart.

Foreign keys are declared in `schema.sql`, but SQLite leaves them off
unless the connection says `PRAGMA foreign_keys = ON`. That pragma is
issued in `teiko.db.connect` on every open, not once at create time. A
connection that skipped it would accept orphan rows. A test inserts a
count for a sample that does not exist and checks that it fails.

How this holds at hundreds of projects and thousands of samples: subject
facts stay one row per person no matter how many timepoints arrive, so a
metadata correction is a one-row update. Cohort filters hit `subjects`,
which stays small. New analytics are new queries against the view, not
new loader code. `cell_counts` is the only table that grows with both
samples and populations, and it is the natural place to partition later.
The same DDL ports to Postgres with almost no change.

The CSV's real column names win over the brief: `sample`, `condition`,
and `sex`, not `sample_id`, `indication`, or `gender`. The loader reads
the file, not the prompt.

## Code structure

Three thin scripts sit at the repository root because the brief names them
and Codespaces graders run them with no arguments:

| File | What it does |
| --- | --- |
| `load_data.py` | Calls `build_database` and prints row counts. |
| `run_pipeline.py` | Writes every file in `outputs/`. |
| `app.py` | The Streamlit dashboard. |

The work lives in `teiko/`, imported as `teiko`, not `src.teiko`. A
`src/` layout would need a package install or a `PYTHONPATH` before
`python load_data.py` worked. The brief asks for that bare command.

| Module | What it does |
| --- | --- |
| `teiko/db.py` | Connect (pragma on), apply `schema.sql`, build the database if it is missing. |
| `teiko/loading.py` | CSV into the five tables. Drops and rebuilds on every load. |
| `teiko/frequencies.py` | Reads `sample_frequencies` for Part 2. |
| `teiko/statistics.py` | Mann-Whitney U, hand-written Benjamini-Hochberg, Cliff's delta, Welch t-test. |
| `teiko/subsets.py` | The two Part 4 SQL queries. |
| `teiko/plots.py` | The two boxplot figures. |

`schema.sql` is the DDL and the view. `tests/` pins the load counts, the
frequency arithmetic, the correction, both Part 4 answers, and an allowlist
of treatment names so a planted drug that is not in the data cannot sneak
into a tracked file. `docs/SPEC.md` is the locked contract.
`docs/DECISIONS.md` is the paper trail of choices.

The pipeline and the dashboard call the same functions. The dashboard does
not reimplement the statistics in Streamlit.

## Results

### Part 2 — relative frequencies

`outputs/summary_table.csv` has 52,500 rows: one per sample per
population. For each sample the five percentages sum to 100. Values stay
unrounded in the database; the CSV rounds percentages to four decimal
places for reading.

### Part 3 — responders versus non-responders

Cohort: melanoma, miraclib, PBMC only. 656 subjects (331 responders, 325
non-responders) and 1,968 samples (993 / 975).

Method: two-sided Mann-Whitney U on relative frequency, Benjamini-Hochberg
across the five populations, Cliff's delta for effect size. A Welch t-test
and two subject-level checks (per-subject means, baseline only) sit beside
the headline so the conclusion does not hinge on one test.

**No population differs significantly after correction.** That is the
finding, not a failed search for a biomarker.

The headline comparison (all 1,968 samples) has one tempting raw p-value:
CD4 T cells at p ≈ 0.0133. After correction that is q ≈ 0.0667, not
significant. A Welch t-test on the same rows gives p ≈ 0.005. At baseline,
where a predictor would have to live, every corrected q is ≈ 0.885 and
every effect is negligible. Pooling timepoints, skipping the correction,
and using a t-test as the primary test would invent a CD4 biomarker that
is not in the data.

A weak B cell shift appears after dosing. It is never significant. The
smallest corrected q anywhere, across five populations and three
timepoints, is ≈ 0.072 on day 14. Every Cliff's delta is negligible; the
largest anywhere is 0.110, below the 0.147 "small" band. At day 0 the B
cell median difference is +0.03; at day 7 and day 14 it is about −0.73.
CD4 peaks at day 7 and eases back, so it is not a clean trend.

Bob asked about predicting response. That needs information available
before treatment starts. Baseline is where this dataset is emptiest. The
weak on-treatment movement is a pharmacodynamic observation — consistent
with the drug acting on people who already responded — not a predictor of
whom to treat. These five frequencies do not predict response to miraclib.

Full tables: `outputs/responder_comparison.csv` and
`outputs/timepoint_comparison.csv`. Figures: `outputs/boxplots.png` and
`outputs/boxplots_by_timepoint.png`.

### Part 4 — subsets

Two different cohorts. The brief switches filters without saying so.
Carrying Cohort A's PBMC and miraclib restrictions into the last question
is the easy way to get the wrong number.

**Cohort A** — melanoma, PBMC, miraclib, day 0. 656 samples from 656
subjects.

- Samples per project: prj1 384, prj2 0, prj3 272.
- Subjects by response: 331 responders, 325 non-responders.
- Subjects by sex: 344 male, 312 female.

`prj2` has zero rows in this slice and is still listed. A plain
`GROUP BY` would drop it.

**Cohort B** — melanoma males who responded, day 0, all sample types and
all treatments. The brief drops the PBMC and miraclib filters here.
485 samples. Average raw B cell count: **10206.15**.

Raw count, not percentage. Keeping the earlier filters gives a different
mean on fewer samples.

## Dashboard

Hosted copy: <https://teiko-immune-analysis-hardikv3.streamlit.app/>

Local copy: `make dashboard`, then open http://localhost:8501.
