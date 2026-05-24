"""Fetch formal PR reviews from the GitHub Reviews API.

Supplements the perceval sync (which uses the issues API and therefore does not
include reviews_data) by calling the dedicated pulls reviews endpoint per PR.
"""

import logging
import time
from typing import Iterator

import httpx
import psycopg2

from staged_recipe_dashboard.config import AppConfig
from staged_recipe_dashboard.worker.reviews import upsert_reviews

OWNER = "conda-forge"
REPO = "staged-recipes"
REVIEWS_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{{number}}/reviews"

logger = logging.getLogger(__name__)


def _connect(cfg: AppConfig):
    return psycopg2.connect(database=cfg.database.name, host=cfg.database.socket_dir)


def _paginate(client: httpx.Client, url: str) -> Iterator[dict]:
    """Yield all review objects from a paginated GitHub reviews endpoint."""
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


def _reviews_for_pr(client: httpx.Client, pr_number: int) -> list[tuple]:
    """Return upsert tuples for all reviews on a single PR."""
    rows = []
    for review in _paginate(client, REVIEWS_URL.format(number=pr_number)):
        user = review.get("user") or {}
        reviewer = user.get("login")
        if not reviewer:
            continue
        rows.append((
            review["id"],
            pr_number,
            reviewer,
            user.get("type", "User"),
            review.get("state", ""),
            review.get("submitted_at"),
        ))
    return rows


def sync_reviews(cfg: AppConfig, open_only: bool = False) -> None:
    """Fetch formal reviews from the GitHub Reviews API and upsert into pr_reviews.

    open_only=False (default / backfill):
        Processes open PRs + any PR that has never had reviews fetched.
    open_only=True (scheduled runs):
        Processes only open PRs, since reviews on closed PRs are immutable.
    """
    if not cfg.worker.github_tokens:
        logger.warning("No GitHub tokens configured; skipping review sync.")
        return

    conn = _connect(cfg)
    cur = conn.cursor()
    try:
        if open_only:
            cur.execute(
                "SELECT number FROM pull_requests WHERE state = 'open' ORDER BY number"
            )
        else:
            cur.execute("""
                SELECT number FROM pull_requests
                WHERE state = 'open'
                   OR number NOT IN (SELECT DISTINCT pr_number FROM pr_reviews)
                ORDER BY number
            """)
        pr_numbers = [row[0] for row in cur.fetchall()]

        if not pr_numbers:
            logger.info("Reviews up to date; nothing to fetch.")
            return

        logger.info("Fetching reviews for %d PRs", len(pr_numbers))

        headers = {
            "Authorization": f"Bearer {cfg.worker.github_tokens[0]}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        with httpx.Client(headers=headers, timeout=30) as client:
            for i, number in enumerate(pr_numbers):
                rows = _reviews_for_pr(client, number)
                upsert_reviews(cur, rows)

                if (i + 1) % 50 == 0:
                    conn.commit()
                    logger.info("Processed %d/%d PRs", i + 1, len(pr_numbers))

        conn.commit()
        logger.info("Review sync complete. Processed %d PRs.", len(pr_numbers))
    finally:
        cur.close()
        conn.close()
