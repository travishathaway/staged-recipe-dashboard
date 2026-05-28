# Design: PR Author Replied Indicator

## Architecture Overview

```
Database                           Backend                        Frontend
────────────────────────           ──────────────────────────     ─────────────────────────
pr_review_comments                 GET /api/prs
  pr_number                          ↓
  commenter (login)                  list_prs()
  commenter_type ('User'|'Bot')        + lateral subquery:
  created_at                           UNION pr_review_comments
                                       UNION pr_reviews
pr_reviews                             WHERE type = 'User'
  pr_number                            ORDER BY ts DESC
  reviewer (login)                     LIMIT 1 per PR
  reviewer_type ('User'|'Bot')        ↓
  submitted_at                     PRResponse:
                                     last_commenter: str | None
                                     author_replied: bool
                                         ↓
                                   PRCard.svelte
                                     green bg if author_replied
                                     show last_commenter login
```

---

## Backend: New Fields on `PRResponse`

### Pydantic model update

Add two fields to the existing `PRResponse` model in `api.py`:

```python
class PRResponse(BaseModel):
    number: int
    title: str | None
    author: str | None
    state: str
    html_url: str | None
    created_at: datetime | None
    waiting_since: datetime | None
    labels: list[str]
    roles: list[str] = []
    last_commenter: str | None = None   # NEW — GitHub login of most recent human commenter
    author_replied: bool = False         # NEW — True when last_commenter == author
```

Both fields default to safe values so they are backward-compatible with any callers that don't
yet consume them.

### Subquery: most recent human commenter per PR

A scalar subquery is added to the SELECT clause that unions `pr_review_comments` and `pr_reviews`,
filters to human users only, picks the most recent entry, and returns the commenter login:

```python
from sqlalchemy import union_all, literal_column

def _last_human_commenter_subquery():
    """
    Returns a scalar subquery that yields the GitHub login of the most recent
    human commenter on a given PR, or NULL if there are none.
    Unions pr_review_comments (issue comments) and pr_reviews (formal reviews).
    Bots are excluded by filtering on commenter_type / reviewer_type = 'User'.
    """
    comments_q = (
        select(
            PRReviewComment.pr_number.label("pr_number"),
            PRReviewComment.commenter.label("commenter"),
            PRReviewComment.created_at.label("ts"),
        )
        .where(PRReviewComment.commenter_type == "User")
    )
    reviews_q = (
        select(
            PRReview.pr_number.label("pr_number"),
            PRReview.reviewer.label("commenter"),
            PRReview.submitted_at.label("ts"),
        )
        .where(PRReview.reviewer_type == "User")
    )
    combined = union_all(comments_q, reviews_q).subquery("all_human_comments")

    return (
        select(combined.c.commenter)
        .where(combined.c.pr_number == PullRequest.number)
        .order_by(combined.c.ts.desc())
        .limit(1)
        .correlate(PullRequest)
        .scalar_subquery()
        .label("last_commenter")
    )
```

This subquery is added unconditionally to `select_cols` in `list_prs()` — it does not require
a `username` parameter; it's useful for all PR list requests.

### Wiring into `_to_pr_response`

The `last_commenter` value is read from the row and `author_replied` is derived:

```python
def _to_pr_response(db, row, ...):
    pr = row.PullRequest
    last_commenter = getattr(row, "last_commenter", None)
    author_replied = bool(last_commenter and last_commenter == pr.author)
    labels = _get_labels(db, pr.number)
    ...
    return PRResponse(
        ...
        last_commenter=last_commenter,
        author_replied=author_replied,
    )
```

### The `numbers` (starred) path

The starred path in `list_prs()` currently fetches PRs by their numbers using a different query
path. The same `_last_human_commenter_subquery()` is added to that SELECT as well, so starred
PR cards also get the indicator.

---

## Frontend: `PRCard.svelte` Changes

### New reactive declarations

```js
$: authorReplied = pr.author_replied ?? false
$: lastCommenter = pr.last_commenter ?? null
```

### `<li>` conditional classes

The blocked state classes are guarded to only apply when `authorReplied` is false.
The green background is applied via inline style when `authorReplied` is true:

```svelte
<li class="list-group-item list-group-item-action py-2 px-3"
  class:border-start={isBlocked && !authorReplied}
  class:border-3={isBlocked && !authorReplied}
  class:border-warning={isBlocked && !authorReplied}
  class:opacity-75={isBlocked && !authorReplied}
  style={authorReplied ? 'background-color: #d1f0e0;' : ''}>
```

The color `#d1f0e0` is Bootstrap's `$green` (`#198754`) blended to ~15% opacity on white —
a soft mint that is clearly distinct from the default white background without being alarming.

### Last commenter display

When `authorReplied` is true, the last commenter's login is shown in the metadata row alongside
the author handle. It appears after the existing content, visually separated:

```
METADATA ROW (author_replied = false):
  @recipe-author  ·  [python]  [awaiting author]

METADATA ROW (author_replied = true):
  @recipe-author  ·  [python]  ·  last: @recipe-author
```

Implementation in the second-row `<div>`:

```svelte
{#if authorReplied && lastCommenter}
  <span class="text-secondary" aria-hidden="true">·</span>
  <span class="text-success-emphasis" style="font-size: 0.85em;">
    last: @{lastCommenter}
  </span>
{/if}
```

Using `text-success-emphasis` (Bootstrap's dark green text token) ties the text color to the
green theme without hardcoding a hex value for the text.

### Visual summary

```
┌──────────────────────────────────────────────────────────────────┐
│  DEFAULT PR CARD (no special state)                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ ⊙ #12345  Add recipe for foo-bar                   3d  ☆  │  │
│  │ @some-author  [python]                                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  BLOCKED PR (Awaiting author contribution label)                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  ║ ⊙ #12346  Add recipe for baz         (dimmed)     5d  ☆  │  │
│  ║ @other-author  [rust]  [awaiting author]                   │  │  ← orange left border
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  AUTHOR REPLIED (green bg, overrides blocked if present)         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│  │  ← #d1f0e0 green bg
│  │░⊙ #12347  Add recipe for qux                      8d  ☆ ░│  │
│  │░@qux-author  [julia]  ·  last: @qux-author              ░│  │  ← last commenter shown
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## File Changelist

| File | Change |
|------|--------|
| `src/staged_recipe_dashboard/backend/routes/api.py` | Add `last_commenter` + `author_replied` to `PRResponse`; add `_last_human_commenter_subquery()` helper; add subquery to both the main and starred SELECT paths; wire into `_to_pr_response()` |
| `frontend/src/lib/components/PRCard.svelte` | Add `authorReplied` + `lastCommenter` reactive declarations; guard blocked classes; add green inline style; render last commenter in metadata row |
