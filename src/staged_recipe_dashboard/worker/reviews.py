"""Extract PR comment data from stored perceval JSONB and upsert review data."""

import logging

logger = logging.getLogger(__name__)

# Reviews are fetched via the GitHub API (see review_sync.py), not from JSONB.
# The perceval sync uses the issues API which does not include reviews_data.

UPSERT_REVIEW_SQL = """
    INSERT INTO pr_reviews (id, pr_number, reviewer, reviewer_type, state, submitted_at)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        state        = EXCLUDED.state,
        submitted_at = EXCLUDED.submitted_at
"""

UPSERT_COMMENT_SQL = """
    INSERT INTO pr_review_comments (id, pr_number, commenter, commenter_type, created_at)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (id) DO NOTHING
"""


def extract_comments_from_row(pr_number: int, item: dict) -> list[tuple]:
    """Parse comments_data from a stored perceval item (issues API format).

    Returns a list of tuples ready for upsert into pr_review_comments.
    Formal reviews are not available in the JSONB; use review_sync.sync_reviews instead.
    """
    pr_data = item.get("data", {})
    comments = []

    for comment in pr_data.get("comments_data", []):
        comment_id = comment.get("id")
        if not comment_id:
            continue
        user = comment.get("user") or {}
        commenter = user.get("login")
        if not commenter:
            continue
        commenter_type = user.get("type", "User")
        created_at = comment.get("created_at")
        comments.append((comment_id, pr_number, commenter, commenter_type, created_at))

    return comments


def upsert_comments(cur, review_comments: list[tuple]) -> None:
    """Upsert extracted PR comments into pr_review_comments."""
    if review_comments:
        cur.executemany(UPSERT_COMMENT_SQL, review_comments)


def upsert_reviews(cur, reviews: list[tuple]) -> None:
    """Upsert formal reviews into pr_reviews."""
    if reviews:
        cur.executemany(UPSERT_REVIEW_SQL, reviews)
