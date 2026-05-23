"""Smoke test: verify all three tables exist after migrations.

Requires a running local postgres instance (run `srdb init` first).
"""

import pytest
import psycopg2


@pytest.fixture(scope="session")
def db_cursor():
    from staged_recipe_dashboard.config import load_config

    cfg = load_config()
    conn = psycopg2.connect(database=cfg.database.name, host=cfg.database.socket_dir)
    cur = conn.cursor()
    yield cur
    cur.close()
    conn.close()


def test_pull_requests_table(db_cursor):
    db_cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'pull_requests' ORDER BY column_name"
    )
    cols = {row[0] for row in db_cursor.fetchall()}
    assert {"id", "number", "state", "data", "html_url", "author"}.issubset(cols)


def test_pr_labels_table(db_cursor):
    db_cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'pr_labels'"
    )
    cols = {row[0] for row in db_cursor.fetchall()}
    assert {"pr_number", "label_name"} == cols


def test_pr_label_history_table(db_cursor):
    db_cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'pr_label_history'"
    )
    cols = {row[0] for row in db_cursor.fetchall()}
    assert {"pr_number", "label_name", "applied_at"} == cols


def test_all_tables_exist(db_cursor):
    db_cursor.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    tables = {row[0] for row in db_cursor.fetchall()}
    assert {"pull_requests", "pr_labels", "pr_label_history"}.issubset(tables)
