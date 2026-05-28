# Proposal: Local User Preferences

## What

Add a client-side preferences system to the dashboard that lets reviewers personalize their
experience without requiring login or server-side identity. The first capabilities are:

- **GitHub username**: stored locally, shown as a profile avatar in the nav with a dropdown to
  access settings.
- **Starred PRs**: reviewers can star individual PRs and filter the Overview queue to show only
  their starred items.
- **Export / import**: preferences are portable — exportable as a JSON file and importable on
  another device or browser.

A new `/profile` settings page provides a home for all preference management, including a starred
PR summary, clear-all action, and the export/import controls.

## Why

Reviewers return to the dashboard repeatedly and want continuity. Today there is no way to mark
a PR as "I'm watching this one" without leaving a comment or keeping a separate note. A starred
list solves this. The GitHub username unlocks future personalization (e.g. highlighting your own
PRs, pre-filtering by your team) and gives the nav a human touch without the complexity of
authentication.

Keeping all state in `localStorage` means zero server changes for the preference store itself —
no user table, no sessions, no auth tokens. Export/import solves the portability problem without
any backend involvement.

## Goals

- Store GitHub username and a starred PR list in browser `localStorage`.
- Display GitHub avatar in the top-right nav; clicking it opens a dropdown with the username and
  a link to `/profile`.
- Highlight active nav route; remove "Review Dashboard" subtitle text from the nav.
- Add a "Starred" filter toggle to the Overview page that fetches only starred open PRs.
- Add a star/unstar button to each `PRCard`.
- Add a `/profile` settings page with: username field, starred count + clear action, export and
  import controls.
- Support exporting preferences as `staged-recipe-dashboard-settings.json` and importing/replacing
  them with a confirmation when existing data is present.
- Design the preferences store as an extensible foundation for future settings (filters, display
  options, etc.) using a versioned schema.

## Non-goals

- Server-side user accounts or authentication.
- Syncing preferences across devices in real time (export/import covers the portability need).
- Merging preferences on import (replace-only).
- A "hide blocked PRs" filter in this change (can be added to the filters bar later).
- Validating that the entered GitHub username actually exists (cosmetic use only for now).

## Constraints

- All preference state lives in the browser — no new backend tables or migrations.
- The starred filter requires a new `?numbers=` query parameter on `GET /api/prs` so the backend
  can return exactly the starred open PRs regardless of pagination.
- GitHub avatars are fetched from `https://github.com/<username>.png?size=32` — public, no auth.
- The preferences schema must carry a `version` integer so future schema changes can be migrated
  on load without data loss.
- The Svelte app has no existing shared state (all state is local to each component); this change
  introduces the first Svelte writable stores.
