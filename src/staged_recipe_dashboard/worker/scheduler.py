"""APScheduler configuration for background sync jobs."""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from staged_recipe_dashboard.config import AppConfig

logger = logging.getLogger(__name__)


def start_scheduler(cfg: AppConfig) -> None:
    """Start the blocking scheduler; runs until interrupted."""
    from staged_recipe_dashboard.worker.sync import run_once
    from staged_recipe_dashboard.worker.events import sync_label_history
    from staged_recipe_dashboard.worker.review_sync import sync_reviews

    scheduler = BlockingScheduler()

    scheduler.add_job(
        lambda: run_once(cfg),
        trigger=IntervalTrigger(minutes=cfg.worker.sync_interval_minutes),
        id="sync_prs",
        name="Sync PRs from GitHub",
        next_run_time=datetime.now(timezone.utc),  # run immediately on first start
    )

    scheduler.add_job(
        lambda: sync_label_history(cfg),
        trigger=IntervalTrigger(minutes=cfg.worker.events_interval_minutes),
        id="sync_label_history",
        name="Sync label history from GitHub Events API",
        next_run_time=datetime.now(timezone.utc),
    )

    scheduler.add_job(
        lambda: sync_reviews(cfg, open_only=True),
        trigger=IntervalTrigger(minutes=cfg.worker.review_sync_interval_minutes),
        id="sync_reviews",
        name="Sync formal reviews from GitHub Reviews API",
        next_run_time=datetime.now(timezone.utc),
    )

    logger.info(
        "Scheduler started (PR sync every %dm, label history every %dm, reviews every %dm)",
        cfg.worker.sync_interval_minutes,
        cfg.worker.events_interval_minutes,
        cfg.worker.review_sync_interval_minutes,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
