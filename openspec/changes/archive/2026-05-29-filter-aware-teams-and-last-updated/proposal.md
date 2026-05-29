# Proposal: Filter-Aware Team Counts and Last Updated Timestamp

## What

Two related improvements to the Overview page:

1. **Filter-aware sidebar counts** — The `/api/teams` endpoint gains the same `username`, `roles`,
   and `unreviewed` filter parameters as `/api/prs`. The Overview page re-fetches team counts
   reactively whenever those filters change, so the sidebar badges always reflect the currently
   active filter rather than the unfiltered totals.

2. **Last updated timestamp** — The `/api/prs` response gains a `last_updated_at` scalar field
   computed as `MAX(pull_requests.updated_at)` over open PRs. The Overview page displays this
   value as a human-readable relative time ("Last updated: 3 minutes ago") directly beneath the
   "Reviews requested" stat in the top content area.

## Why

Currently, toggling the "No reviews yet" filter or activating role filters changes the PR list
but leaves the sidebar team counts showing the full unfiltered totals. A reviewer who filters to
unreviewed PRs sees, say, "python: 47" in the sidebar while the list shows 8 — the mismatch is
confusing and makes the sidebar useless as a navigation aid when filters are active.

The "last updated" addition answers a natural question that any dashboard user has: "Is this
data fresh?" The `pull_requests.updated_at` column is overwritten on every worker upsert with
the GitHub-sourced timestamp, making `MAX(updated_at)` a reliable proxy for data freshness
without requiring any new infrastructure.

## Goals

- Add `username`, `roles`, and `unreviewed` query parameters to `GET /api/teams`. When provided,
  the per-team `needs_review_count` and `blocked_count` are computed over the filtered subset of
  PRs, using the same filter logic already in `GET /api/prs`.
- Update `getTeams()` in `frontend/src/lib/api.js` to accept and forward those three parameters.
- In `Overview.svelte`, replace the one-time `onMount` `getTeams()` call with a reactive fetch
  that re-runs when `$githubUsername`, `selectedRoles`, or `showUnreviewed` changes. The fetch
  is skipped when `showStarred` is true (starred mode doesn't use team counts meaningfully).
- `totalWaiting` (the "All teams" aggregate) becomes a reactive derivation from `teams[]` so it
  updates alongside the sidebar badges.
- Add `last_updated_at: datetime | None` to `PRListResponse`. It is populated with
  `SELECT MAX(updated_at) FROM pull_requests WHERE state = 'open'` on every `/api/prs` call.
- Display `last_updated_at` in `Overview.svelte` below the "Reviews requested:" heading as small
  muted text: "Last updated: X minutes ago" (or "just now", "X hours ago", etc.). The value is
  captured from the first successful PR fetch and not refreshed automatically.

## Non-goals

- No changes to the `/api/stats` endpoint or `Scoreboard`/`Team` pages.
- `get_stats` continues to call `list_teams` with no arguments (unfiltered counts for stats).
- No auto-refresh timer for the "last updated" value.
- No changes to the starred-mode team count behaviour — sidebar counts are left as-is when
  `showStarred` is true.
- The `numbers` (starred) path in `list_prs` is not affected by `last_updated_at` — the field
  is included in all `PRListResponse` returns regardless.

## Constraints

- The `list_teams` signature change must be fully backward-compatible: all new parameters default
  to `None`/`False` so the existing direct call from `get_stats` requires no modification.
- The `last_updated_at` field must default to `None` in `PRListResponse` so existing callers
  that don't read the field are unaffected.
- The teams reactive fetch must not trigger on `selectedTeam` or `currentPage` changes, as those
  don't affect per-team counts.
