#!/usr/bin/env python3
"""
Fetch all pull request data from conda-forge/staged-recipes using Perceval
and store it in a SQLite database.

Installation:
    pip install perceval

Usage:
    python fetch_staged_recipes_prs.py --token YOUR_GITHUB_TOKEN
    python fetch_staged_recipes_prs.py --token TOKEN1 TOKEN2   # multiple tokens to extend rate limits
    python fetch_staged_recipes_prs.py --token YOUR_TOKEN --from-date 2024-01-01
    python fetch_staged_recipes_prs.py --token YOUR_TOKEN --output prs.db

Schema:
    Table: pull_requests
        id          INTEGER  PRIMARY KEY  -- perceval uuid (hash)
        number      INTEGER  UNIQUE       -- GitHub PR number
        state       TEXT                  -- 'open' | 'closed'
        author      TEXT                  -- GitHub login of PR author
        title       TEXT
        created_at  TEXT                  -- ISO-8601
        updated_at  TEXT                  -- ISO-8601
        closed_at   TEXT                  -- ISO-8601, NULL if open
        merged_at   TEXT                  -- ISO-8601, NULL if not merged
        data        TEXT                  -- full perceval item as JSON

Querying examples:
    -- All open PRs
    SELECT number, title, author FROM pull_requests WHERE state = 'open';

    -- PRs merged in 2024
    SELECT number, title FROM pull_requests
    WHERE merged_at >= '2024-01-01' AND merged_at < '2025-01-01';

    -- Number of comments on each PR
    SELECT number, json_array_length(data, '$.comments_data') AS n_comments
    FROM pull_requests ORDER BY n_comments DESC LIMIT 20;

    -- PRs by a specific author
    SELECT number, title, state FROM pull_requests WHERE author = 'octocat';
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone

from perceval.backends.core.github import GitHub

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

OWNER = "conda-forge"
REPO  = "staged-recipes"

# Commit to DB every N rows to balance speed vs. durability
BATCH_SIZE = 200


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch pull requests from conda-forge/staged-recipes into SQLite"
    )
    parser.add_argument(
        "-t", "--token",
        nargs="+",
        required=True,
        metavar="TOKEN",
        help="GitHub personal access token(s). Pass multiple to rotate and avoid rate limits.",
    )
    parser.add_argument(
        "--from-date",
        metavar="YYYY-MM-DD",
        default=None,
        help="Only fetch PRs updated on or after this date (default: all time).",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        default="conda-forge--staged-recipes.db",
        help="SQLite database file to write to (default: conda-forge--staged-recipes.db).",
    )
    parser.add_argument(
        "--sleep-for-rate",
        action="store_true",
        default=True,
        help="Sleep instead of crashing when the GitHub rate limit is hit (default: True).",
    )
    return parser.parse_args()


def init_db(conn):
    """Create the pull_requests table and indexes if they don't already exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pull_requests (
            id         TEXT    PRIMARY KEY,  -- perceval uuid
            number     INTEGER UNIQUE,
            state      TEXT,
            author     TEXT,
            title      TEXT,
            created_at TEXT,
            updated_at TEXT,
            closed_at  TEXT,
            merged_at  TEXT,
            data       TEXT NOT NULL         -- full perceval item JSON
        );

        CREATE INDEX IF NOT EXISTS idx_pr_number     ON pull_requests (number);
        CREATE INDEX IF NOT EXISTS idx_pr_state      ON pull_requests (state);
        CREATE INDEX IF NOT EXISTS idx_pr_author     ON pull_requests (author);
        CREATE INDEX IF NOT EXISTS idx_pr_created_at ON pull_requests (created_at);
        CREATE INDEX IF NOT EXISTS idx_pr_updated_at ON pull_requests (updated_at);
        CREATE INDEX IF NOT EXISTS idx_pr_merged_at  ON pull_requests (merged_at);
    """)
    conn.commit()


def fetch_pull_requests(tokens, from_date=None, sleep_for_rate=True):
    """Yield perceval items that are pull requests (not plain issues)."""
    repo = GitHub(
        owner=OWNER,
        repository=REPO,
        api_token=tokens,
        sleep_for_rate=sleep_for_rate,
    )

    kwargs = {}
    if from_date:
        kwargs["from_date"] = from_date

    total = 0
    seen = 0
    for item in repo.fetch(**kwargs):
        seen += 1
        # GitHub's issues endpoint returns both issues and PRs;
        # PRs always have a 'pull_request' key in their payload.
        if "pull_request" not in item["data"]:
            continue
        total += 1
        if total % 100 == 0:
            logger.info("Fetched %d pull requests so far (scanned %d items)…", total, seen)
        yield item

    logger.info("Done. Total pull requests fetched: %d (out of %d items scanned)", total, seen)


def item_to_row(item):
    """Extract indexed columns from a perceval item, keeping full JSON in `data`."""
    d = item["data"]
    return (
        item["uuid"],                          # id
        d.get("number"),                       # number
        d.get("state"),                        # state
        (d.get("user") or {}).get("login"),    # author (user can be null for deleted accounts)
        d.get("title"),                        # title
        d.get("created_at"),                   # created_at
        d.get("updated_at"),                   # updated_at
        d.get("closed_at"),                    # closed_at
        d.get("pull_request", {}).get("merged_at"),  # merged_at
        json.dumps(item, default=str),         # full data blob
    )


def main():
    args = parse_args()

    from_date = None
    if args.from_date:
        from_date = datetime.strptime(args.from_date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )

    logger.info(
        "Starting fetch: %s/%s  |  from_date=%s  |  tokens=%d  |  output=%s",
        OWNER, REPO,
        from_date or "beginning of time",
        len(args.token),
        args.output,
    )

    conn = sqlite3.connect(args.output)
    # WAL mode: faster writes, allows concurrent reads while writing
    conn.execute("PRAGMA journal_mode=WAL")
    # Relax fsync for speed; data is still safe on Python crash, just not power loss
    conn.execute("PRAGMA synchronous=NORMAL")
    init_db(conn)

    insert_sql = """
        INSERT OR REPLACE INTO pull_requests
            (id, number, state, author, title, created_at, updated_at, closed_at, merged_at, data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    batch = []
    total = 0
    try:
        for item in fetch_pull_requests(
            tokens=args.token,
            from_date=from_date,
            sleep_for_rate=args.sleep_for_rate,
        ):
            batch.append(item_to_row(item))
            total += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany(insert_sql, batch)
                conn.commit()
                batch.clear()

        # Flush any remaining rows
        if batch:
            conn.executemany(insert_sql, batch)
            conn.commit()

    finally:
        conn.close()

    logger.info("All done. %d pull requests written to %s", total, args.output)


if __name__ == "__main__":
    main()
