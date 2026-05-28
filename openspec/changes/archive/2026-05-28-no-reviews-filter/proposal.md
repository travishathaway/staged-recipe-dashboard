# Proposal: No Reviews Yet Filter

## What

Add a "No reviews yet" toggle to the Overview page that filters the `needs_review` PR queue to
show only PRs that have not yet received any formal human review — meaning no `APPROVED`,
`CHANGES_REQUESTED`, or `DISMISSED` review from a non-bot reviewer. PRs with only human
comments, bot reviews of any kind, or no reviews at all are included.

The toggle appears in the existing filters bar alongside Starred and the role checkboxes. When
active, the backend applies an additional `NOT EXISTS` filter over `pr_reviews` and the URL is
updated with `?unreviewed=true` for deep-linking.

## Why

Reviewers wanting to answer "what should I review next?" currently have no way to distinguish
PRs that are genuinely untouched from PRs that already have a `CHANGES_REQUESTED` verdict
waiting on the author. Both appear identically in the queue today. In practice, a PR with a
pending `CHANGES_REQUESTED` review does not need a new reviewer — the author just hasn't
responded yet.

The queue is sorted by "waiting since" (oldest first), so a PR that has been waiting 60 days
with zero formal reviews is the highest-priority target for a new reviewer. The filter makes
that signal explicit and actionable.

## Goals

- Add an `unreviewed` boolean query parameter to `GET /api/prs`. When `true`, the result set
  is restricted to PRs where no non-bot reviewer has submitted an `APPROVED`,
  `CHANGES_REQUESTED`, or `DISMISSED` review. `COMMENTED` state reviews are ignored entirely
  (both from bots and humans).
- Add a "No reviews yet" toggle button to the Overview page filters bar. When active, it
  passes `unreviewed=true` to the API and resets pagination to page 1.
- Sync the toggle state to the URL (`?unreviewed=true`) for deep-linking and browser
  back/forward.
- The toggle is independent of team selection, role filters, and the starred filter — it
  composes with them.

## Non-goals

- Surfacing this filter on the Team page (Overview only for now).
- Tracking *how many* reviews a PR has received (just zero vs. non-zero).
- Counting or displaying bot reviews anywhere.
- Any changes to how review data is synced (the `pr_reviews` table already has the needed data).

## Constraints

- `COMMENTED` state reviews never disqualify a PR — a reviewer leaving inline comments without
  submitting a formal verdict does not count as "reviewed" for this filter.
- Bot reviews (where `reviewer_type = 'Bot'`) are always excluded from the check regardless
  of state.
- When `unreviewed=true` is combined with other filters (team, roles, starred), all filters
  apply together. Pagination operates over the fully-filtered set.
- The filter only applies to the main non-starred fetch path. The starred path bypasses it
  (starred PRs are fetched by explicit number and the filter is not meaningful there).
