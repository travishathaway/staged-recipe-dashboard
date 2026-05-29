# Tasks: Fix Scoreboard Self-Review Attribution

## Phase 1 — Backend: Exclude self-reviews from `review_stats` CTE

- [x] **1.1** In `src/staged_recipe_dashboard/backend/routes/api.py`, locate the `review_stats`
  CTE inside the `get_scoreboard` SQL string (around line 530). Add
  `JOIN pull_requests p ON p.number = r.pr_number` immediately after the `FROM pr_reviews r`
  line. Add `AND r.reviewer != p.author` as an additional WHERE condition after
  `r.submitted_at >= :cutoff`.

## Phase 2 — Backend: Exclude self-comments from `comment_stats` CTE

- [x] **2.1** In the same SQL string, locate the `comment_stats` CTE (around line 541). Add
  `JOIN pull_requests p ON p.number = c.pr_number` immediately after the
  `FROM pr_review_comments c` line. Add `AND c.commenter != p.author` as an additional WHERE
  condition after `c.created_at >= :cutoff`.

## Phase 3 — Verification

- [x] **3.1** Run the test suite (`pixi run -e dev pytest tests/`) and confirm no regressions.

- [ ] **3.2** Manually verify the fix by checking a known PR author against the scoreboard:
  confirm that review/comment activity they posted on their own PRs no longer inflates their
  count. A quick spot-check via `psql` against the local DB is sufficient:
  ```sql
  SELECT r.reviewer, r.state, p.author
  FROM pr_reviews r
  JOIN pull_requests p ON p.number = r.pr_number
  WHERE r.reviewer = p.author
  LIMIT 10;
  ```
  These rows should no longer appear in scoreboard counts after the fix.
