# Design: Fix Scoreboard Self-Review Attribution

## Root Cause

The scoreboard query in `get_scoreboard` (`api.py:518–558`) counts all rows in `pr_reviews` and
`pr_review_comments` without checking whether the reviewer/commenter is the same person who
authored the PR. The `pull_requests` table holds the `author` column, and `pr_reviews.pr_number`
/ `pr_review_comments.pr_number` are FK-joined to it — but the query never uses this join.

## Fix: Two JOIN + filter additions in the SQL string

Both CTEs in the query need the same treatment: join to `pull_requests` on `pr_number` and add a
`WHERE reviewer != pr_author` (or `commenter != pr_author`) condition.

### `review_stats` CTE — before

```sql
FROM pr_reviews r
WHERE r.submitted_at >= :cutoff
  {team_subquery}
GROUP BY r.reviewer, r.reviewer_type
```

### `review_stats` CTE — after

```sql
FROM pr_reviews r
JOIN pull_requests p ON p.number = r.pr_number
WHERE r.submitted_at >= :cutoff
  AND r.reviewer != p.author
  {team_subquery}
GROUP BY r.reviewer, r.reviewer_type
```

### `comment_stats` CTE — before

```sql
FROM pr_review_comments c
WHERE c.created_at >= :cutoff
  {comment_team_subquery}
GROUP BY c.commenter, c.commenter_type
```

### `comment_stats` CTE — after

```sql
FROM pr_review_comments c
JOIN pull_requests p ON p.number = c.pr_number
WHERE c.created_at >= :cutoff
  AND c.commenter != p.author
  {comment_team_subquery}
GROUP BY c.commenter, c.commenter_type
```

## NULL safety

`pull_requests.author` is declared `TEXT` (nullable). If `author` is `NULL`, the condition
`reviewer != NULL` evaluates to `NULL` (unknown) in SQL, which means the row would be silently
excluded. This is acceptable: a PR with no recorded author is an anomalous data state, and
excluding its review rows from the scoreboard is safer than counting them. No special `COALESCE`
handling is needed.

## Performance

Both `pr_reviews.pr_number` and `pr_review_comments.pr_number` are already indexed
(`idx_pr_reviews_pr_number`, `idx_pr_review_comments_pr_number`). The join to `pull_requests`
on `pull_requests.number` (PK) will use an index scan and adds negligible overhead to a query
that is already grouping across the full time-window dataset.

## File Changelist

| File | Change |
|------|--------|
| `src/staged_recipe_dashboard/backend/routes/api.py` | Add `JOIN pull_requests p ON p.number = r.pr_number` and `AND r.reviewer != p.author` to `review_stats` CTE; add `JOIN pull_requests p ON p.number = c.pr_number` and `AND c.commenter != p.author` to `comment_stats` CTE |

No other files require changes.
