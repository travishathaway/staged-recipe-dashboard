"""Fetch formal PR reviews from the GitHub Reviews API.

Supplements the perceval sync (which uses the issues API and therefore does not
include reviews_data) by calling the dedicated pulls reviews endpoint per PR.
"""

import logging

import httpx

from staged_recipe_dashboard.config import AppConfig
from staged_recipe_dashboard.worker.github import OWNER, REPO, _connect, _paginate
from staged_recipe_dashboard.worker.reviews import upsert_reviews

REVIEWS_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{{number}}/reviews"

logger = logging.getLogger(__name__)


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
            # Resume backfill from the PR after the highest one already processed.
            # This avoids re-scanning from PR #1 when a previous run was interrupted.
            # Open PRs are always refreshed regardless of the resume point.
            cur.execute("SELECT COALESCE(MAX(pr_number) + 1, 0) FROM pr_reviews")
            resume_from = cur.fetchone()[0]
            logger.info("Backfill resume point: PR #%d", resume_from)
            cur.execute(
                """
                SELECT number FROM pull_requests
                WHERE state = 'open' OR number >= %s
                ORDER BY number
                """,
                (resume_from,),
            )
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
