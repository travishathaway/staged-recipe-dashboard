"""Fetch label application timestamps from the GitHub Events API.

Supplements perceval (which doesn't fetch issue events) to record when
`review-requested` was first applied to each open PR.
"""

import logging
import time
from typing import Iterator

import httpx
import psycopg2

from staged_recipe_dashboard.config import AppConfig

OWNER = "conda-forge"
REPO = "staged-recipes"
EVENTS_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/issues/{{number}}/events"

logger = logging.getLogger(__name__)


def _connect(cfg: AppConfig):
    return psycopg2.connect(database=cfg.database.name, host=cfg.database.socket_dir)


def _paginate(client: httpx.Client, url: str) -> Iterator[dict]:
    """Yield all events from a paginated GitHub events endpoint."""
    while url:
        resp = client.get(url)
        resp.raise_for_status()

        remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
        if remaining == 0:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(0, reset - time.time()) + 1
            logger.warning("Rate limit hit; sleeping %ds", wait)
            time.sleep(wait)

        yield from resp.json()
        url = resp.links.get("next", {}).get("url", "")


def _find_label_applied_at(client: httpx.Client, pr_number: int, label: str) -> str | None:
    """Return the ISO timestamp when `label` was first applied to `pr_number`, or None."""
    for event in _paginate(client, EVENTS_URL.format(number=pr_number)):
        if event.get("event") == "labeled" and event.get("label", {}).get("name") == label:
            return event.get("created_at")
    return None


def sync_label_history(cfg: AppConfig) -> None:
    """For open PRs missing review-requested history, fetch it from the Events API."""
    if not cfg.worker.github_tokens:
        logger.warning("No GitHub tokens configured; skipping label history sync.")
        return

    conn = _connect(cfg)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT pr.number
            FROM pull_requests pr
            JOIN pr_labels l
              ON pr.number = l.pr_number AND l.label_name = 'review-requested'
            LEFT JOIN pr_label_history h
              ON pr.number = h.pr_number AND h.label_name = 'review-requested'
            WHERE pr.state = 'open'
              AND h.pr_number IS NULL
            ORDER BY pr.number
        """)
        pr_numbers = [row[0] for row in cur.fetchall()]

        if not pr_numbers:
            logger.info("Label history up to date; nothing to fetch.")
            return

        logger.info("Fetching label history for %d open PRs", len(pr_numbers))

        headers = {
            "Authorization": f"Bearer {cfg.worker.github_tokens[0]}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        with httpx.Client(headers=headers, timeout=30) as client:
            for i, number in enumerate(pr_numbers):
                applied_at = _find_label_applied_at(client, number, "review-requested")
                if applied_at:
                    cur.execute(
                        """
                        INSERT INTO pr_label_history (pr_number, label_name, applied_at)
                        VALUES (%s, 'review-requested', %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (number, applied_at),
                    )

                if (i + 1) % 50 == 0:
                    conn.commit()
                    logger.info("Processed %d/%d PRs", i + 1, len(pr_numbers))

        conn.commit()
        logger.info("Label history sync complete.")
    finally:
        cur.close()
        conn.close()
