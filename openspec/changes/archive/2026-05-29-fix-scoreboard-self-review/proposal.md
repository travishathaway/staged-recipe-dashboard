# Proposal: Fix Scoreboard Self-Review Attribution

## What

Exclude PR authors from their own PR's review counts on the scoreboard. Currently, comments and
reviews submitted by a PR's author on their own PR are counted toward that person's scoreboard
totals. This inflates scores for active contributors who author many PRs and then reply to
reviewer feedback on them.

## Why

GitHub does not allow a PR author to formally approve or request changes on their own PR — only
the GitHub UI enforces this. However, the GitHub API does record `COMMENTED`-state review events
and inline review comments from the PR author, and these get stored in `pr_reviews` and
`pr_review_comments`. The scoreboard query has no filter to exclude these self-interactions.

A user reported that review counts are inflated for at least one contributor who is a prolific PR
author. Attributing these self-interactions as "reviews" misrepresents the contributor's actual
review activity and makes the scoreboard misleading for the rest of the community.

## Goals

- In the `review_stats` CTE, exclude any row in `pr_reviews` where `reviewer` matches the
  `author` of the PR (joined from `pull_requests`).
- In the `comment_stats` CTE, exclude any row in `pr_review_comments` where `commenter` matches
  the `author` of the PR.
- No data model changes — `pull_requests.author` and the FK `pr_number` are already present in
  all relevant tables.

## Non-goals

- No changes to how data is collected or stored by the worker.
- No changes to any other endpoint or page (PR queue, team pages, stats).
- No changes to `APPROVED`, `CHANGES_REQUESTED`, or `DISMISSED` handling specifically — the fix
  applies uniformly to all review types, but in practice only `COMMENTED` rows are realistically
  authored by the PR author (GitHub blocks formal review states from the author at submission
  time; any `APPROVED` by the author would be a data anomaly and should also be excluded).

## Constraints

- The fix must be a pure SQL change within the existing query string in `api.py`. No new tables,
  columns, migrations, or Python logic required.
- Usernames in `pr_reviews.reviewer`, `pr_review_comments.commenter`, and
  `pull_requests.author` are stored with consistent casing, so a direct string equality join is
  correct.
- The change must not affect performance noticeably — adding a single FK join to an already-
  indexed column is negligible.
