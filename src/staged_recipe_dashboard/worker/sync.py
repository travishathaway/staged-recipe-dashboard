"""Sync pull requests from GitHub into PostgreSQL via perceval."""

import json
import logging
from datetime import datetime, timedelta, timezone

import psycopg2
from perceval.backends.core.github import GitHub

from staged_recipe_dashboard.config import AppConfig, RUNTIME_DIR
from staged_recipe_dashboard.worker.reviews import extract_comments_from_row, upsert_comments

OWNER = "conda-forge"
REPO = "staged-recipes"
BATCH_SIZE = 200
# Overlap subtracted from last-sync time to catch any PRs whose updated_at
# was slightly behind the clock when the previous sync ran.
OVERLAP_MINUTES = 15

logger = logging.getLogger(__name__)

_STATE_FILE = RUNTIME_DIR / "last_sync.txt"


def _read_last_sync() -> datetime | None:
    if _STATE_FILE.exists():
        return datetime.fromisoformat(_STATE_FILE.read_text().strip())
    return None


def _write_last_sync(dt: datetime) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(dt.isoformat())

UPSERT_PR_SQL = """
    INSERT INTO pull_requests
        (id, number, state, author, title, html_url,
         created_at, updated_at, closed_at, merged_at, data)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        state      = EXCLUDED.state,
        author     = EXCLUDED.author,
        title      = EXCLUDED.title,
        html_url   = EXCLUDED.html_url,
        updated_at = EXCLUDED.updated_at,
        closed_at  = EXCLUDED.closed_at,
        merged_at  = EXCLUDED.merged_at,
        data       = EXCLUDED.data
"""


def _connect(cfg: AppConfig):
    return psycopg2.connect(database=cfg.database.name, host=cfg.database.socket_dir)


def _item_to_row(item: dict) -> tuple:
    d = item["data"]
    return (
        item["uuid"],
        d.get("number"),
        d.get("state"),
        (d.get("user") or {}).get("login"),
        d.get("title"),
        d.get("html_url"),
        d.get("created_at"),
        d.get("updated_at"),
        d.get("closed_at"),
        d.get("pull_request", {}).get("merged_at"),
        json.dumps(item, default=str),
        [label["name"] for label in d.get("labels", [])],
    )


def _sync_batch(cur, batch: list[tuple]) -> None:
    for row in batch:
        pr_row = row[:-1]
        labels = row[-1]
        number = row[1]

        cur.execute(UPSERT_PR_SQL, pr_row)

        cur.execute("DELETE FROM pr_labels WHERE pr_number = %s", (number,))
        if labels:
            cur.executemany(
                "INSERT INTO pr_labels (pr_number, label_name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                [(number, label) for label in labels],
            )

        # row[10] is the JSON string of the full perceval item stored in the data column
        item = json.loads(row[10])
        comments = extract_comments_from_row(number, item)
        upsert_comments(cur, comments)


def run_once(cfg: AppConfig, from_date: datetime | None = None) -> None:
    """Fetch PRs from GitHub and upsert into postgres.

    from_date behavior:
      - Explicitly provided (e.g. via --from-date): used as-is.
      - Not provided and last_sync.txt exists: uses last sync time minus
        OVERLAP_MINUTES to avoid missing PRs at the boundary.
      - Not provided and no state file: full sync from the beginning of time.

    Writes the sync start time to last_sync.txt on success so the next
    incremental run knows where to start.
    """
    # Resolve from_date from state file if not explicitly given.
    if from_date is None:
        last = _read_last_sync()
        if last is not None:
            from_date = last - timedelta(minutes=OVERLAP_MINUTES)
            logger.info(
                "Incremental sync: using last sync time minus %dm overlap → %s",
                OVERLAP_MINUTES, from_date.isoformat(),
            )
        else:
            logger.info("No previous sync found; performing full sync.")

    sync_start = datetime.now(timezone.utc)
    logger.info("PR sync starting: %s/%s from_date=%s", OWNER, REPO, from_date or "beginning")

    if not cfg.worker.github_tokens:
        logger.error("No GitHub tokens configured. Set [worker] github_tokens in config.toml.")
        return

    repo = GitHub(
        owner=OWNER,
        repository=REPO,
        api_token=cfg.worker.github_tokens,
        sleep_for_rate=True,
    )

    kwargs: dict = {}
    if from_date:
        kwargs["from_date"] = from_date

    conn = _connect(cfg)
    cur = conn.cursor()
    try:
        batch: list[tuple] = []
        total = 0
        seen = 0

        for item in repo.fetch(**kwargs):
            seen += 1
            if "pull_request" not in item["data"]:
                continue
            batch.append(_item_to_row(item))
            total += 1

            if len(batch) >= BATCH_SIZE:
                _sync_batch(cur, batch)
                conn.commit()
                batch.clear()
                logger.info("Synced %d PRs (scanned %d items)…", total, seen)

        if batch:
            _sync_batch(cur, batch)
            conn.commit()

        _write_last_sync(sync_start)
        logger.info("PR sync complete. %d PRs synced (scanned %d items).", total, seen)
    finally:
        cur.close()
        conn.close()
