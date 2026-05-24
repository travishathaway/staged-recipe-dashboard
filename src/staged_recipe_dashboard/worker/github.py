"""Shared GitHub API utilities: connection helpers and paginated fetching."""

import logging
import time
from typing import Iterator

import httpx
import psycopg2

from staged_recipe_dashboard.config import AppConfig

OWNER = "conda-forge"
REPO = "staged-recipes"

logger = logging.getLogger(__name__)


def _connect(cfg: AppConfig):
    return psycopg2.connect(database=cfg.database.name, host=cfg.database.socket_dir)


def _paginate(client: httpx.Client, url: str) -> Iterator[dict]:
    """Yield all items from a paginated GitHub API endpoint, respecting rate limits.

    Handles:
    - 429: primary rate limit; sleeps until Retry-After or X-RateLimit-Reset, then retries.
    - 403 with Retry-After: secondary rate limit; same treatment.
    - X-RateLimit-Remaining == 0 on a successful response: proactive sleep before next page.
    """
    while url:
        resp = client.get(url)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                wait = int(retry_after) + 1
            else:
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(0, reset - time.time()) + 1
            logger.warning("Primary rate limit (429); sleeping %ds", wait)
            time.sleep(wait)
            continue

        if resp.status_code == 403:
            wait = int(resp.headers.get("X-RateLimit-Remaining", 200)) + 1
            logger.warning("Secondary rate limit (403); sleeping %ds", wait)
            time.sleep(wait)
            continue

        if resp.status_code >= 500:
            logger.warning("GitHub API error %d for %s — retrying in 30s", resp.status_code, url)
            time.sleep(30)
            continue

        if not resp.is_success:
            logger.error("GitHub API error %d for %s — skipping", resp.status_code, url)
            return

        remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
        if remaining == 0:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(0, reset - time.time()) + 1
            logger.warning("Rate limit exhausted; sleeping %ds before next request", wait)
            time.sleep(wait)

        yield from resp.json()
        url = resp.links.get("next", {}).get("url", "")
