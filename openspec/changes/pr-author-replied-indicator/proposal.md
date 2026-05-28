# Proposal: PR Author Replied Indicator

## What

Add a visual indicator to PR list items when the PR author was the last human to comment. When a
reviewer has left feedback and the author has since replied — signaling they may have addressed
the review — the PR card gets a light green background and the last commenter's GitHub login is
shown in the metadata row.

The green background overrides the existing blocked (orange border + dimmed) visual treatment when
both conditions are present. Bot comments are excluded from the "last commenter" determination.

## Why

The staged-recipes queue is sorted by how long a PR has been waiting for review, but "waiting for
review" doesn't distinguish between two very different states:

- A PR where a reviewer last spoke — the author may still be working on it
- A PR where the author last spoke — they've likely responded to feedback and want another look

Without this signal, reviewers scanning the queue have no way to prioritize PRs where the author
has already replied. The green highlight makes those PRs immediately visible, reducing the cost of
identifying "low-hanging fruit" in a long queue.

The data needed already exists in the database (`pr_review_comments` and `pr_reviews` tables store
commenter login and timestamp per PR). This is a read-only query change with a small frontend
rendering addition.

## Goals

- Add `last_commenter: str | None` and `author_replied: bool` fields to the `GET /api/prs`
  response. `last_commenter` is the GitHub login of the most recent human commenter/reviewer
  across both `pr_review_comments` and `pr_reviews`. `author_replied` is true when
  `last_commenter == pr.author`.
- Exclude bot users (`commenter_type = 'Bot'` / `reviewer_type = 'Bot'`) from the
  last-commenter determination.
- Show a light green background (`#d1f0e0`) on PR cards where `author_replied` is true.
- The green background takes visual precedence over the existing blocked state (orange left
  border + reduced opacity), which is suppressed when `author_replied` is true.
- Display the last commenter's GitHub login in the PR card metadata row when `author_replied`
  is true, so reviewers know at a glance who last spoke.

## Non-goals

- Storing or displaying the text of the last comment — only the commenter's login and the
  derived boolean are needed.
- Dark mode / theme support — a single hardcoded light green color is sufficient for now.
- Showing last-commenter info when `author_replied` is false — the signal is specifically about
  author replies, not general comment activity.
- Changing the sort order based on `author_replied` — the queue continues to sort by
  `waiting_since`.
- Adding a filter for author-replied PRs — visual indicator only for this change.

## Constraints

- PRs with no human comments at all will have `last_commenter = null` and `author_replied =
  false`. No green background in that case.
- The subquery unioning `pr_review_comments` and `pr_reviews` must filter to `reviewer_type /
  commenter_type = 'User'` to exclude bots before picking the most recent entry.
- The new fields are additive to the existing `PRResponse` shape — no breaking changes.
- The frontend change is confined to `PRCard.svelte`; no changes to `Overview.svelte` or
  `Team.svelte` are required.
