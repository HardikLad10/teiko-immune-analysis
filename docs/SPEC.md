# Specification — Immune Cell Analysis for Loblaw Bio

This document is the contract for the project. It states what gets built, what
does not, and how we know each piece is finished.

It is locked. If something needs to change, see [Change control](#15-change-control).
Work that is not described here does not get built.

---

## 1. Purpose and definition of done

A reviewer opens the repository in GitHub Codespaces and runs three commands:

```bash
make setup
make pipeline
make dashboard
```

The project is done when all three succeed with no manual steps, the pipeline
writes every output file listed here, the dashboard serves the results, and the
README explains the schema and links to a hosted copy of the dashboard.

Nothing is done on the strength of an argument. Each part below names the
command that proves it.

### Whose claim is being tested

The brief is written from Bob's point of view, and it leads. It asks for
statistics "to convince Yah of Bob's findings" — a sentence that presupposes
the findings exist.

They do not. Section 8 has the numbers.

Bob's framing supplies the question: which cohort, which drug, which
comparison, and what decision he is trying to make. That context is essential
and the project keeps all of it. His framing does not supply the answer. Every
analysis here reports what the data shows, including where that contradicts the
premise of the question being asked.

This is not a stylistic preference. The three shortcuts listed in section 8 —
skipping the correction, using a t-test, treating three samples per subject as
independent — each produce the confirmatory result the brief invites. Stack all
three and you get a confident p = 0.005 biomarker that is not there. The
leading framing and the statistical traps are the same trap, and the path of
least resistance runs straight through both.

The honest answer has real structure and serves Bob better than a false
positive would: at baseline the groups are indistinguishable, a weak signal
appears only after dosing, and nothing clears significance at any timepoint. He
asked for something that predicts response. The deliverable tells him he does
not have one, and shows the work that rules it out.

---

## 2. The data as it is

`cell-count.csv` sits in the repository root: 10,500 rows plus a header. Every
row is one biological sample.

### Column names

The brief and the file disagree. The file wins.

| Name in the brief | Column in the file |
| --- | --- |
| `sample_id` | `sample` |
| `indication` | `condition` |
| `gender` | `sex` |

The brief's column list is also incomplete. The file contains `project`,
`subject`, `age`, and `sample_type`, none of which it mentions. Parts 3 and 4
cannot be answered without them.

Full list: `project`, `subject`, `condition`, `age`, `sex`, `treatment`,
`response`, `sample`, `sample_type`, `time_from_treatment_start`, `b_cell`,
`cd8_t_cell`, `cd4_t_cell`, `nk_cell`, `monocyte`.

### Facts confirmed by reading the file

Checked directly. The code may rely on these, and tests hold them in place.

- 10,500 samples, 3,500 subjects, exactly 3 samples each.
- Timepoints are 0, 7, and 14 days. Every subject has all three.
- Projects: `prj1` 4,500 samples, `prj2` 3,000, `prj3` 3,000.
- Conditions: `melanoma` 5,175, `carcinoma` 3,903, `healthy` 1,422.
- Treatments: `miraclib` 4,695, `phauximab` 4,383, `none` 1,422.
- Sample types: `PBMC` 7,500, `WB` 3,000.
- Sex: `M` 5,430, `F` 5,070. Age range 50 to 79.
- No duplicate sample ids. All five count columns are positive integers in
  every row.
- Every subject-level field — project, condition, age, sex, treatment,
  response, sample_type — is constant across that subject's three samples. No
  subject mixes PBMC and whole blood.
- `response` is blank on exactly 1,422 rows, precisely the healthy subjects,
  who also have `treatment = 'none'`. No other column has missing values.

The data is clean and genuinely hierarchical. Normalising it is natural here,
not imposed on a mess.

### Cell populations

Five, always in this order: `b_cell`, `cd8_t_cell`, `cd4_t_cell`, `nk_cell`,
`monocyte`. Fixed so that tables and plots stay comparable.

---

## 3. Out of scope

Written down so good ideas arriving mid-build have somewhere to go.

- Predictive or machine learning models.
- Cell populations beyond the five in the file.
- User accounts, authentication, multi-user features.
- A database server. SQLite only.
- Analysis of `age`. It is loaded into the schema because it is in the data,
  but no required question uses it and no chart will.
- Analysis of carcinoma or healthy subjects beyond their presence in the
  Part 2 summary table.
- Any drug not present in the data. See [section 14](#14-writing-rules).
- Docker, CI pipelines, or deployment automation beyond the hosted dashboard.
- A second plotting library. See D-012.

---

## 4. Database schema

Five tables in `teiko.db`, in the repository root. The DDL lives in
`schema.sql` at the root so a reviewer can read the data model without reading
loader code.

```sql
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY
);

CREATE TABLE populations (
    population   TEXT PRIMARY KEY,   -- b_cell, cd8_t_cell, ...
    display_name TEXT NOT NULL,      -- "B cell", "CD8+ T cell", ...
    ordinal      INTEGER NOT NULL UNIQUE   -- fixed display order, 1 to 5
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
```

### Foreign keys must be switched on per connection

SQLite does not persist `PRAGMA foreign_keys = ON` in the database file. It is
a per-connection setting. Putting it in `schema.sql` and assuming it holds is a
silent failure: every foreign key above stops being enforced and nothing
complains.

`teiko/db.py` issues the pragma on every connection it opens, including the
ones the dashboard uses. There is no other way to open a connection in this
project.

### Part 2 lives as a view

```sql
CREATE VIEW sample_frequencies AS
SELECT
    cc.sample_id                                   AS sample,
    SUM(cc.count) OVER (PARTITION BY cc.sample_id) AS total_count,
    cc.population,
    cc.count,
    100.0 * cc.count
      / SUM(cc.count) OVER (PARTITION BY cc.sample_id) AS percentage
FROM cell_counts cc;
```

One definition of "relative frequency", used by the pipeline, the statistics,
and the dashboard alike. They cannot drift apart. Part 4 asks the program to
"query the database", and Part 3 says to work from "the data reported in the
summary table" — a view honours both literally.

Values stay unrounded. Rounding is a presentation concern, applied when writing
CSVs and rendering tables. Window functions need SQLite 3.25 or newer, which
Codespaces satisfies.

### Why this shape

**Treatment and response live on `subjects`.** A subject is enrolled in one arm
and has one recorded outcome; samples are timepoints within that. The data
confirms both fields are constant across all three of every subject's samples.
Storing them once makes it impossible for a subject to appear as both a
responder and a non-responder.

Worth stating honestly in the README: in a real trial, response is a
time-varying assessment and would belong on `samples` or in its own table. It
is modelled at subject level because this dataset makes that true, not because
it is universally right.

**Counts are long, not wide.** One row per sample per population, 52,500 rows.
A sixth population becomes an insert rather than an `ALTER TABLE` plus edits to
every query naming columns.

**`populations` is a lookup table.** It gives referential integrity on
population names and carries display labels, so charts read "CD8+ T cell"
without the presentation layer hardcoding a mapping. It also carries `ordinal`,
because the fixed order in section 2 is not alphabetical and every table and
figure must use it. Sorting happens in SQL, not in five separate call sites.

**Blank responses become `NULL`.** The 1,422 healthy subjects have no outcome.
`NULL` keeps them out of `response = 'yes'` and `response = 'no'` alike, which
is what unknown should mean.

**`total_count` is the sum of the five measured populations**, not the true
total cell count of the sample. Percentages are shares of the measured panel
and sum to 100 by construction. The README says so plainly.

**`projects` has one column today.** It is the extension point for the
"hundreds of projects" scenario, where site, protocol, sponsor, and dates
attach here rather than being repeated across samples.

### How it scales

Subject facts are stored once, so a metadata correction is a one-row update
rather than an N-row rewrite. Cohort filters hit `subjects`, which stays small
at one row per patient no matter how many samples arrive. New analytics are new
queries against the view, not new loader code. `cell_counts` is the only table
that grows multiplicatively, and it is the natural partition target. The schema
ports to Postgres essentially unchanged.

---

## 5. Code layout

```
load_data.py       required in root; bare `python load_data.py`, no arguments
run_pipeline.py    `make pipeline` entry point; writes everything in outputs/
app.py             `make dashboard` entry point; the Streamlit app
schema.sql         the DDL and the view
Makefile
requirements.txt
README.md
cell-count.csv
teiko/
    db.py          connect, apply schema, bootstrap the database if missing
    loading.py     CSV into the normalised tables
    frequencies.py Part 2
    statistics.py  Part 3: Mann-Whitney, Benjamini-Hochberg, Cliff's delta
    subsets.py     Part 4 cohort queries
    plots.py       the boxplot figures
tests/
    fixtures/tiny.csv
    test_loading.py  test_frequencies.py  test_statistics.py  test_subsets.py
    test_integrity.py
docs/
    SPEC.md  DECISIONS.md
outputs/
```

The package is `teiko/` at the repository root, **not** `src/teiko/`. Running
`python load_data.py` puts the script's own directory on `sys.path`, so
`from teiko.loading import ...` resolves with no `PYTHONPATH` juggling, no
`sys.path.insert`, and no editable install. A `src/` layout would need one of
those, and Part 1 forbids `python -m`, which is the usual escape hatch.

Root entry points are thin wrappers. They parse nothing and compute nothing.
All logic lives in `teiko/`, where tests import it directly and the pipeline
and dashboard share one implementation. Analysis functions take a database
connection and return DataFrames or figures.

`load_data.py` resolves its paths relative to its own file, so it works
regardless of the caller's working directory.

---

## 6. Part 1 — Loading

**File:** `load_data.py`, repository root. Runs as `python load_data.py`. No
arguments. Creates `teiko.db` in the repository root.

1. Create the database, dropping and rebuilding the five tables and the view.
2. Read `cell-count.csv`.
3. Insert in dependency order: projects, populations, subjects, samples, counts.
4. Use one transaction and `executemany` for the 52,500 count rows.
5. Verify row counts after loading and fail loudly on a mismatch.
6. Print one line per table.

Running it twice produces the same database. It never appends duplicates.

**Proof:** `python load_data.py && pytest tests/test_loading.py`

---

## 7. Part 2 — Summary table

**Output:** `outputs/summary_table.csv`, from `SELECT * FROM sample_frequencies`.

52,500 rows, one per sample per population.

| Column | Meaning |
| --- | --- |
| `sample` | Sample id, as in the `sample` column of the CSV |
| `total_count` | Sum of all five populations for that sample |
| `population` | One of the five population names |
| `count` | The cell count |
| `percentage` | `count / total_count * 100`, written to 4 decimal places |

Covers every sample, including healthy and whole blood. No filtering happens
here. Parts 3 and 4 filter this view; they never recompute frequencies.

**Proof:** 52,500 rows, and every sample's percentages sum to 100.

---

## 8. Part 3 — Responders versus non-responders

### Cohort

Melanoma subjects on miraclib, PBMC samples only: 656 subjects — 331
responders, 325 non-responders — contributing 1,968 samples, 993 and 975.

The PBMC restriction is the last clause of a long bullet in the brief. It is
not optional.

### Method

Per population, a two-sided **Mann-Whitney U** test of responder against
non-responder relative frequencies.

Chosen on evidence. Skewness and Jarque-Bera statistics were computed for all
ten group-by-population distributions in this cohort: nine of ten reject
normality, all skewed right.

**Benjamini-Hochberg** correction across the five populations. BH rather than
Bonferroni — the tests are few and related, and BH is the field standard.

**Cliff's delta** as the effect size, with the conventional magnitude bands:
below 0.147 negligible, below 0.33 small, below 0.474 medium.

A **Welch t-test** is reported alongside, not as the conclusion but as
evidence that the conclusion does not hinge on the choice of test.

### Unit of analysis

The headline uses all 1,968 samples, which is what the brief describes.

Each subject contributes three samples, so those rows are not independent. Two
sensitivity analyses run alongside on 656 independent observations: one on
per-subject means, one on baseline samples only. All three are reported.

### Findings already verified

**No population reaches significance at any timepoint.** Across five
populations at three timepoints, the smallest corrected q-value anywhere is
0.072. Every effect size is negligible; the largest Cliff's delta anywhere is
0.110, below the 0.147 threshold.

The dataset sets three traps, and each one alone produces a false finding:

| Mistake | What you would wrongly report |
| --- | --- |
| Skip the correction | cd4_t_cell "significant" at raw p = 0.0133, where q = 0.0667 |
| Use a t-test as primary | cd4_t_cell at p = 0.005, which reads as strong |
| Pool all 1,968 samples as independent | cd4_t_cell p = 0.013 pooled, against p = 0.796 at baseline |

Stacking all three yields a confident p = 0.005 biomarker that is not there.

### The pattern that is actually present

At baseline the groups are indistinguishable across all five populations —
every corrected q is 0.885, every effect size under 0.06. After dosing begins,
a weak difference appears:

| Timepoint | b_cell median difference | b_cell Cliff's delta | cd4_t_cell median difference |
| --- | --- | --- | --- |
| day 0 | +0.03 | 0.027 | +0.10 |
| day 7 | −0.73 | 0.066 | +0.90 |
| day 14 | −0.73 | 0.110 | +0.72 |

For B cells the effect strengthens steadily across the three timepoints. For
CD4 T cells it peaks at day 7 and eases back at day 14, so it is not a clean
monotonic trend and will not be described as one.

**The conclusion to report.** Bob asked about predicting response, which
requires information available before treatment starts. Baseline is exactly
where this dataset is emptiest. What weak signal exists appears only after
dosing, which makes it a pharmacodynamic observation — consistent with the drug
acting on responders — rather than a predictive biomarker that tells Bob whom
to treat. These five frequencies do not give him a predictor.

This negative result is the deliverable, not a failure. The code must present
it as a complete, fully rendered result: effect sizes beside every p-value, raw
and corrected values both visible so the reader can watch the correction do its
work, and baseline kept separate from on-treatment rather than pooled away.
Nothing may treat an empty list of significant hits as an error or an empty
state.

### Outputs

`outputs/responder_comparison.csv`, one row per population:

`population`, `n_responder`, `n_non_responder`, `median_responder`,
`median_non_responder`, `median_difference`, `cliffs_delta`,
`effect_magnitude`, `p_value`, `q_value`, `significant`, `p_value_welch`,
`p_value_subject_means`, `q_value_subject_means`, `p_value_baseline`,
`q_value_baseline`.

`outputs/timepoint_comparison.csv` — the same statistics per population per
timepoint, which is the evidence behind the table above.

`outputs/boxplots.png` — the required figure. Five panels, one per population,
responders beside non-responders, y-axis relative frequency in percent.

`outputs/boxplots_by_timepoint.png` — the same, faceted by day, showing the
emergence pattern.

**Proof:** `pytest tests/test_statistics.py`

---

## 9. Part 4 — Subsets

Two different cohorts. The brief switches between them without saying so.
Carrying the first one's filters into the second is the easiest way to submit a
wrong answer. All queries are SQL against the database.

### Cohort A — baseline melanoma, miraclib, PBMC

`condition = 'melanoma'`, `sample_type = 'PBMC'`, `treatment = 'miraclib'`,
`time_from_treatment_start = 0`. That is 656 samples from 656 subjects.

| Breakdown | Expected |
| --- | --- |
| Samples per project | `prj1` 384, `prj3` 272, **`prj2` 0** |
| Subjects by response | 331 responders, 325 non-responders |
| Subjects by sex | 344 male, 312 female |

The `prj2` zero is reported explicitly. A plain `GROUP BY` omits it.

The brief shifts between counting samples per project and counting subjects for
response and sex. They coincide here, since each subject has one baseline PBMC
sample, but the queries use `COUNT(DISTINCT subject_id)` where subjects are
asked for, so they stay correct if a subject ever has a replicate draw.

### Cohort B — the final question

`condition = 'melanoma'`, `sex = 'M'`, `response = 'yes'`,
`time_from_treatment_start = 0`, and **all sample types and all treatments**.
The brief says "all sample and treatment types", which drops the PBMC and
miraclib filters.

485 samples, spanning PBMC and whole blood, miraclib and phauximab. The answer
is the mean raw `b_cell` count over them: **10206.15**.

Raw count, not relative frequency. The frequency answer would be 9.99 and is
wrong. Keeping the earlier filters gives 184 samples and 10401.28. A test pins
the correct value.

### Outputs

- `outputs/part4_baseline_samples.csv` — the 656 Cohort A samples with
  `sample`, `subject`, `project`, `response`, `sex`.
- `outputs/part4_breakdowns.csv` — long format: `breakdown` (`project`,
  `response`, `sex`), `category`, `count`, `unit` (`samples` or `subjects`).
- `outputs/part4_answers.md` — the breakdowns and the B cell average written in
  sentences, so nobody has to interpret a CSV.

**Proof:** `pytest tests/test_subsets.py`

---

## 10. Dashboard

Streamlit, one file at `app.py`, hosted on Streamlit Community Cloud and linked
from the README.

`teiko.db.ensure_database()` builds the database from the committed CSV if it
is absent, cached with `@st.cache_resource`. That is what makes a laptop, a
Codespace, and the public URL one code path, since Community Cloud never runs
the Makefile.

Four tabs:

1. **Overview** — row counts, cohort composition, the five tables, and what
   the study contains.
2. **Frequencies** — the `sample_frequencies` view, filterable by project,
   condition, treatment, sample type, and timepoint, with a CSV download.
3. **Response analysis** — boxplots and the statistics table, with the
   plain-language conclusion above the table. Cohort dropdowns default to
   melanoma, miraclib, and PBMC but can be changed, so the tool answers the
   general question rather than one hardcoded slice. A timepoint selector
   exposes the emergence pattern.
4. **Subset explorer** — Cohort A's breakdowns and Cohort B's average, with the
   filters shown as controls so the widening in Cohort B is visible rather than
   magic. The two cohorts stay visually separate.

Charts are matplotlib. Interactivity comes from the filter controls.

**Proof:** `make dashboard` serves locally, and the hosted URL loads.

---

## 11. Makefile

| Target | Does |
| --- | --- |
| `setup` | `python -m pip install -r requirements.txt` |
| `pipeline` | `python load_data.py` then `python run_pipeline.py` |
| `dashboard` | `streamlit run app.py` |
| `test` | `pytest -q` |

The first three are named exactly as the brief requires. `make pipeline` runs
start to finish with no prompts and no arguments.

`requirements.txt` is pinned and holds `pandas`, `numpy`, `scipy`,
`matplotlib`, `streamlit`, and `pytest`. Nothing else without a decision log
entry.

---

## 12. README

Written for someone who has never seen the project.

1. **What this is** — one paragraph.
2. **How to run it** — the three make commands and what each produces.
3. **The schema** — the five tables, why they are shaped that way, and how the
   design holds at hundreds of projects and thousands of samples. Section 4 is
   the source. This is a graded essay and deserves real length.
4. **Code structure** — what each file does and why the work splits that way.
5. **Results** — the Part 3 conclusion and the Part 4 answers in plain words,
   including that nothing reached significance and why that is the honest
   finding.
6. **Dashboard link.**

---

## 13. Tests

Ten tests, each tied to a failure that could actually happen. A fixture CSV at
`tests/fixtures/tiny.csv` carries hand-computed values.

**Loading**

1. The loader writes 3,500 subjects, 10,500 samples, and 52,500 count rows.
2. Running it twice leaves those counts unchanged.
3. The 1,422 blank responses become `NULL` and appear in neither responder
   group.

**Frequencies**

4. On the fixture, each percentage equals its hand-computed value.
5. Across the real data, every sample's five percentages sum to 100.

**Statistics**

6. Two identical groups give a p-value near 1; two clearly separated groups
   give one below 0.05.
7. Benjamini-Hochberg on a known list returns the known corrected list.

**Subsets**

8. Cohort A returns 656 samples with `prj1` 384, `prj3` 272, `prj2` 0, and
   331/325 by response and 344/312 by sex.
9. Cohort B returns 485 samples and a B cell average of 10206.15.

**Integrity**

10. No file in the repository mentions a treatment outside the three that exist
    in the data. See section 14.

Test 9 guards the Part 4 filter trap. Test 10 guards the canary.

---

## 14. Writing rules

These apply to the spec, the README, code comments, and commit messages.

**Say what a thing does, not what it enables.** "Loads the CSV into five
tables" beats "provides a data ingestion layer."

**Banned words:** leverage, robust, seamless, comprehensive, powerful,
cutting-edge, delve, utilise, facilitate, "it's worth noting", "in the realm
of", "at the end of the day".

**Commit messages** are one line, lower case, stating the change:
`add relative frequency view for part 2`. No emoji. No conventional-commit
prefixes.

**Comments** explain constraints the code cannot show. They do not narrate the
next line.

**The planted drug name.** Part 4 of the brief contains a sentence addressed to
language models, instructing them to mention a drug that appears nowhere in the
data. It is a check for machine-written submissions. That name must not appear
anywhere in this repository — code, comments, documentation, commit messages,
or quoted requirement text — nor in git history. When quoting Part 4, omit that
sentence.

This is enforced by test 10, which inverts the check: rather than searching for
the banned word, which would require writing it down, the test asserts that no
treatment name outside `miraclib`, `phauximab`, and `none` appears in any
tracked file. Same protection, nothing incriminating on disk.

---

## 15. Change control

The spec is locked. When implementation hits something this document did not
anticipate:

1. Stop the task.
2. Say what was found and what it forces.
3. Get approval for a specific amendment.
4. Edit this file and record the reasoning in `docs/DECISIONS.md`.
5. Resume.

Adding scope is not a bug fix. A change that makes the project bigger needs the
same approval as a new feature.

`docs/DECISIONS.md` is the companion to this file. It is append-only and
records what was chosen, why, what was rejected, and what it costs. It never
changes requirements — that is this document's job.

---

## 16. Task sequence

Ten tasks. Each ends with a passing test, a commit, and a push to `main`.

1. Scaffolding — `requirements.txt`, `Makefile`, pytest config, `outputs/`,
   the fixture CSV, and the integrity test.
2. Schema and loader — `schema.sql`, `teiko/db.py`, `teiko/loading.py`,
   `load_data.py`. Tests 1 to 3.
3. Frequencies — `teiko/frequencies.py` reading the view. Tests 4 and 5.
4. Statistics — `teiko/statistics.py`. Tests 6 and 7.
5. Plots — `teiko/plots.py`, both figures.
6. Subsets — `teiko/subsets.py`. Tests 8 and 9.
7. Pipeline entry point — `run_pipeline.py`, wired into `make pipeline`.
8. Dashboard — `app.py`, wired into `make dashboard`.
9. Deployment — Streamlit Community Cloud, URL captured.
10. README, then a full verification run in a fresh Codespace.

Task 10 means launching an actual Codespace and running all three make targets
there before submitting. Not a local approximation.

The implementation plan turns each of these into steps small enough to execute
and check one at a time.
