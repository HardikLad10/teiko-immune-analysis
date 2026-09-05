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
