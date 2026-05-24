# Tasks: Reviewer Scoreboard

## Phase 1 — Database

- [x] **1.1** Write Alembic migration `002_add_review_tables.py` that creates `pr_reviews` and
  `pr_review_comments` tables with all indexes as specified in design.md. No changes to existing
  tables.

- [x] **1.2** Add SQLAlchemy ORM models `PRReview` and `PRReviewComment` to
  `src/staged_recipe_dashboard/backend/models.py`, mapped to the two new tables.

## Phase 2 — Extraction Worker

- [x] **2.1** Create `src/staged_recipe_dashboard/worker/reviews.py` with:
  - `extract_reviews_from_row(pr_number, data)` — parses `data['reviews_data']` and
    `data['review_comments_data']` from a perceval JSONB blob; returns `(reviews_list, comments_list)`
    as lists of dicts ready for upsert. Handles missing/empty keys gracefully.
  - `upsert_reviews(cur, reviews, review_comments)` — bulk upserts into `pr_reviews` and
    `pr_review_comments` using `ON CONFLICT (id) DO UPDATE SET state = EXCLUDED.state, ...`

- [x] **2.2** Integrate extraction into `_sync_batch` in `worker/sync.py`: after the existing
  label upsert step, call `upsert_reviews` with data extracted from each item's JSONB blob.

## Phase 3 — Backfill CLI Command

- [x] **3.1** Add `srdb extract-reviews` command to `cli.py`:
  - Options: `--pr-state [open|closed|all]` (default: `all`), `--batch-size N` (default: 500)
  - Queries `SELECT number, data FROM pull_requests` filtered by `--pr-state`
  - Calls `extract_reviews_from_row` + `upsert_reviews` per batch, committing every `--batch-size` rows
  - Logs progress every batch (e.g. "Processed 500/12400 PRs…")
  - Safe to run multiple times (idempotent upserts)

## Phase 4 — API Endpoint

- [x] **4.1** Add `GET /api/scoreboard` to `backend/routes/api.py`:
  - Query params: `period` (required, one of `30d|90d|1y|3y`) and `team` (optional label string)
  - Aggregates `formal_reviews` (states APPROVED/CHANGES_REQUESTED/DISMISSED), per-state breakdowns,
    and `review_comments` (pr_review_comments rows + COMMENTED-state pr_reviews rows) per user
  - `last_active` = max timestamp across both tables for that user within the period
  - Applies team filter via subquery on `pr_labels` when `team` is provided
  - Splits results into `human_reviewers` (reviewer_type='User') and `bots` (reviewer_type='Bot')
  - Both lists sorted by `formal_reviews DESC`, then `review_comments DESC`

- [x] **4.2** Add Pydantic response models `ReviewerScore` and `ScoreboardResponse` to `api.py`.

## Phase 5 — Frontend

- [x] **5.1** Add `fetchScoreboard(period, team)` helper to `frontend/src/lib/api.js` that calls
  `GET /api/scoreboard`.

- [x] **5.2** Create `frontend/src/routes/Scoreboard.svelte`:
  - Period selector tabs: 30d / 90d / 1y / 3y (reactive, triggers re-fetch on change)
  - Team dropdown populated from existing `/api/teams` endpoint; default "All teams"
  - Human reviewers table with columns: Reviewer, Reviews (total), ✓ Approved, ↩ Changes Req'd,
    ✗ Dismissed, Review Comments, Last Active
  - Column header tooltips explaining each metric (title attribute is fine)
  - Collapsible bots section with simplified columns: Bot, Reviews, Comments, Last Active
  - Loading state while fetch is in progress; empty state message when no data

- [x] **5.3** Register the new route in `frontend/src/App.svelte`: add `<Route path="/scoreboard"
  component={Scoreboard} />` and import the component.

- [x] **5.4** Add a "Scoreboard" nav link in `App.svelte` alongside existing navigation links.
