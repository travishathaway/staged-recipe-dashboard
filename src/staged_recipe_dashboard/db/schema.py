"""Reference DDL for the three core tables.

Migrations are managed by Alembic. This file is the authoritative schema
reference and can be used for documentation or test fixtures.
"""

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS pull_requests (
    id          TEXT        PRIMARY KEY,
    number      INTEGER     UNIQUE NOT NULL,
    state       TEXT        NOT NULL,
    author      TEXT,
    title       TEXT,
    html_url    TEXT,
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ,
    closed_at   TIMESTAMPTZ,
    merged_at   TIMESTAMPTZ,
    data        JSONB       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pr_state      ON pull_requests (state);
CREATE INDEX IF NOT EXISTS idx_pr_author     ON pull_requests (author);
CREATE INDEX IF NOT EXISTS idx_pr_created_at ON pull_requests (created_at);

CREATE TABLE IF NOT EXISTS pr_labels (
    pr_number   INTEGER     NOT NULL REFERENCES pull_requests(number) ON DELETE CASCADE,
    label_name  TEXT        NOT NULL,
    PRIMARY KEY (pr_number, label_name)
);

CREATE INDEX IF NOT EXISTS idx_label_name ON pr_labels (label_name);

CREATE TABLE IF NOT EXISTS pr_label_history (
    pr_number   INTEGER     NOT NULL REFERENCES pull_requests(number) ON DELETE CASCADE,
    label_name  TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (pr_number, label_name)
);

CREATE INDEX IF NOT EXISTS idx_history_label ON pr_label_history (label_name);
"""
