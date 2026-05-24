# Proposal: Reviewer Scoreboard

## What

Add a reviewer scoreboard to the dashboard that tracks and displays review activity across
conda-forge/staged-recipes pull requests. The scoreboard shows two distinct metrics per reviewer —
formal reviews (approved, changes requested, dismissed) and inline review comments — with separate
sections for human reviewers and bots.

A new `srdb extract-reviews` CLI command enables a fast one-shot backfill of historical data by
mining the review and review-comment payloads already stored in the `data` JSONB column, requiring
no additional GitHub API calls. Ongoing syncs populate the new tables automatically.

## Why

PR reviewers have no visibility into their own or others' contribution patterns. A scoreboard
surfaces this data, encourages sustained engagement, and helps maintainers identify who is doing
the work and who might need support. Bot activity is shown separately so it doesn't obscure human
contributions.

## Goals

- Track formal reviews (APPROVED / CHANGES_REQUESTED / DISMISSED) per reviewer with per-state breakdown.
- Track inline review comments per reviewer as a separate metric.
- Display a `/scoreboard` page with filterable rolling time windows (30 days, 90 days, 1 year, 3 years).
- Support filtering by team label (only count reviews on PRs tagged for a given team).
- Separate bot accounts from human reviewers; show bots in a collapsible section.
- Provide a fast backfill path (`srdb extract-reviews`) that mines existing JSONB with no API calls.

## Non-goals

- Tracking issue-level (general discussion) comments — only formal reviews and inline review comments are captured.
- Authentication or per-user private scoreboards.
- Gamification features (badges, streaks, etc.) beyond the table view.
- Cross-repository tracking.

## Constraints

- Review and review-comment data is already fetched by perceval and stored in `data->>'reviews_data'` and `data->>'review_comments_data'`. The backfill requires no GitHub API calls.
- Bot detection uses the `type` field on the GitHub user object (present in the stored JSONB) — `"Bot"` vs `"User"`.
- COMMENTED-state formal reviews are folded into the review comments metric at query time; they are stored in `pr_reviews` with their actual state.
- DISMISSED reviews count as formal reviews (reviewer did real work even if superseded).
- The scoreboard is a new top-level Svelte route at `/scoreboard`.
