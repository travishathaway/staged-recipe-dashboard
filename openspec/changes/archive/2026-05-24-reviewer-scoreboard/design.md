# Design: Reviewer Scoreboard

## Database Schema — Two New Tables

```sql
-- Formal PR reviews (APPROVED, CHANGES_REQUESTED, DISMISSED, COMMENTED)
CREATE TABLE pr_reviews (
    id             BIGINT       PRIMARY KEY,   -- GitHub review ID
    pr_number      INTEGER      NOT NULL REFERENCES pull_requests(number) ON DELETE CASCADE,
    reviewer       TEXT         NOT NULL,
    reviewer_type  TEXT         NOT NULL,      -- 'User' | 'Bot'
    state          TEXT         NOT NULL,      -- APPROVED | CHANGES_REQUESTED | DISMISSED | COMMENTED
    submitted_at   TIMESTAMPTZ
);

CREATE INDEX idx_pr_reviews_pr_number    ON pr_reviews (pr_number);
CREATE INDEX idx_pr_reviews_reviewer     ON pr_reviews (reviewer);
CREATE INDEX idx_pr_reviews_submitted_at ON pr_reviews (submitted_at);

-- Inline PR review comments (code-level comments on diff hunks)
CREATE TABLE pr_review_comments (
    id              BIGINT       PRIMARY KEY,  -- GitHub comment ID
    pr_number       INTEGER      NOT NULL REFERENCES pull_requests(number) ON DELETE CASCADE,
    commenter       TEXT         NOT NULL,
    commenter_type  TEXT         NOT NULL,     -- 'User' | 'Bot'
    created_at      TIMESTAMPTZ
);

CREATE INDEX idx_pr_review_comments_pr_number  ON pr_review_comments (pr_number);
CREATE INDEX idx_pr_review_comments_commenter  ON pr_review_comments (commenter);
CREATE INDEX idx_pr_review_comments_created_at ON pr_review_comments (created_at);
```

Both tables upsert by their GitHub ID, so re-syncing a PR is idempotent.

## Extraction Logic

Perceval's GitHub backend already fetches and stores the following inside each `pull_requests.data`
JSONB blob when a PR is synced:

- `data['reviews_data']` — list of review objects:
  ```json
  {
    "id": 12345,
    "user": {"login": "username", "type": "User"},
    "state": "APPROVED",
    "submitted_at": "2024-03-10T14:22:00Z",
    "body": "..."
  }
  ```
- `data['review_comments_data']` — dict keyed by comment ID, values are comment objects:
  ```json
  {
    "id": 67890,
    "user": {"login": "username", "type": "User"},
    "created_at": "2024-03-10T14:25:00Z",
    "body": "..."
  }
  ```

No additional GitHub API calls are needed for the backfill or for ongoing syncs.

The extraction function signature:

```python
# worker/reviews.py
def extract_reviews_from_row(pr_number: int, data: dict) -> tuple[list[dict], list[dict]]:
    """Parse reviews_data and review_comments_data from a perceval JSONB blob.

    Returns (reviews, review_comments) ready for upsert.
    """

def upsert_reviews(cur, reviews: list[dict], review_comments: list[dict]) -> None:
    """Upsert into pr_reviews and pr_review_comments."""
```

## Sync Integration

### Ongoing sync (zero extra API calls)

`_sync_batch` in `worker/sync.py` gains one additional step after upserting PR data:

```
for each PR in batch:
  1. upsert pull_requests          (existing)
  2. rebuild pr_labels             (existing)
  3. extract + upsert pr_reviews   (new)
  4. extract + upsert pr_review_comments  (new)
```

The `data` JSONB field is already available in `_item_to_row` output — no schema changes to the
existing pipeline.

### Backfill command (new)

```
srdb extract-reviews [--pr-state open|closed|all] [--batch-size N]
```

- Reads `(number, data)` from `pull_requests` filtered by `--pr-state`
- Extracts and upserts reviews + review comments for each row
- Commits every `--batch-size` rows (default: 500)
- No GitHub API calls — pure JSONB mining
- Safe to run multiple times (upserts by GitHub ID)

Default: `--pr-state all` to backfill everything. Use `open` for a fast partial import.

## Scoreboard Query Logic

### Metric definitions

| Metric            | Source                                                                 |
|-------------------|------------------------------------------------------------------------|
| Formal reviews    | `pr_reviews` WHERE `state IN ('APPROVED','CHANGES_REQUESTED','DISMISSED')` |
| Approved          | `pr_reviews` WHERE `state = 'APPROVED'`                                |
| Changes requested | `pr_reviews` WHERE `state = 'CHANGES_REQUESTED'`                       |
| Dismissed         | `pr_reviews` WHERE `state = 'DISMISSED'`                               |
| Review comments   | `pr_review_comments` rows + `pr_reviews` WHERE `state = 'COMMENTED'`  |

COMMENTED-state rows stay in `pr_reviews` (accurate storage) but are counted alongside
`pr_review_comments` at query time.

### Period filter

Applied to `submitted_at` / `created_at` columns:

| UI label | Filter                              |
|----------|-------------------------------------|
| 30d      | `>= NOW() - INTERVAL '30 days'`     |
| 90d      | `>= NOW() - INTERVAL '90 days'`     |
| 1y       | `>= NOW() - INTERVAL '1 year'`      |
| 3y       | `>= NOW() - INTERVAL '3 years'`     |

### Team filter

When `?team=<label>` is provided, restrict to PRs that carry that label:

```sql
AND pr_number IN (
    SELECT pr_number FROM pr_labels WHERE label_name = :team
)
```

### Bot split

`reviewer_type = 'User'` → human table.
`reviewer_type = 'Bot'` → bots section.

## API Endpoint

```
GET /api/scoreboard
  ?period=30d|90d|1y|3y        (required, no default — forces explicit choice)
  ?team=<label>                 (optional)

Response:
{
  "period": "90d",
  "team": null,
  "human_reviewers": [
    {
      "login": "isuruf",
      "formal_reviews": 42,
      "approved": 15,
      "changes_requested": 20,
      "dismissed": 7,
      "review_comments": 87,
      "last_active": "2026-05-20T10:00:00Z"
    },
    ...
  ],
  "bots": [
    {
      "login": "conda-forge-admin",
      "formal_reviews": 240,
      "approved": 0,
      "changes_requested": 0,
      "dismissed": 0,
      "review_comments": 0,
      "last_active": "2026-05-22T08:00:00Z"
    },
    ...
  ]
}
```

Both lists sorted by `formal_reviews DESC` then `review_comments DESC`.

`last_active` = most recent timestamp across both `pr_reviews.submitted_at` and
`pr_review_comments.created_at` for that user within the selected period.

## Frontend — `/scoreboard` Route

New Svelte route at `frontend/src/routes/Scoreboard.svelte`.

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Scoreboard                                                      │
│                                                                  │
│  Period: [30d] [90d] [1y] [3y]        Team: [All teams ▾]       │
│                                                                  │
│  Human Reviewers                                                 │
│  ┌────────────────┬───────────────────────────┬────────┬───────┐ │
│  │ Reviewer       │ Reviews  ✓  ↩   ✗         │ Comments│ Last │ │
│  ├────────────────┼───────────────────────────┼────────┼───────┤ │
│  │ isuruf         │  42     15  20   7         │   87   │ 3d   │ │
│  │ hmaarrfk       │  35      9   5   1         │   32   │ 1w   │ │
│  │ ...            │                            │        │      │ │
│  └────────────────┴───────────────────────────┴────────┴───────┘ │
│                                                                  │
│  ▶ Bots (6)          ← collapsible section                       │
│  ┌──────────────────────┬────────────┬────────┬────────────────┐ │
│  │ Bot                  │ Reviews    │Comments│ Last active    │ │
│  ├──────────────────────┼────────────┼────────┼────────────────┤ │
│  │ conda-forge-admin    │  240       │   0    │ 1h ago         │ │
│  └──────────────────────┴────────────┴────────┴────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

Column tooltips explain metric definitions:
- "Reviews" = formal reviews (approved + changes requested + dismissed)
- "✓ / ↩ / ✗" = breakdown columns (approved / changes-requested / dismissed)
- "Comments" = review comments + comment-only reviews

### State management

- Period and team selection held in component state, triggering reactive fetch on change.
- Team dropdown populated from `/api/teams` (reuses existing endpoint).
- Loading and empty states handled inline.

### Navigation

Add "Scoreboard" link to the existing nav bar in `App.svelte`.

## Migration

New Alembic migration: `002_add_review_tables.py`

Creates `pr_reviews` and `pr_review_comments` with all indexes. No changes to existing tables.
