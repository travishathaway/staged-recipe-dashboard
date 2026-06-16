# Proposal: GitHub OAuth Authentication

## What

Add GitHub OAuth login to the dashboard, replacing the manual GitHub username entry and
localStorage-based preferences with server-side identity and per-user data storage. Users
authenticate via GitHub, and their personalisation (starred PRs, ignored PRs, notes) is
stored server-side and associated with their GitHub account.

Unauthenticated users retain full read-only access to the dashboard. Authenticated users gain:
- Stars, ignored PRs, and notes synced across all devices
- Automatic role annotations (author/reviewer/commenter) without manual username entry
- A one-time migration prompt to import any existing localStorage preferences on first login

## Why

The current localStorage approach breaks down across devices. A reviewer using the dashboard
on both a laptop and a work machine maintains two completely separate preference states with no
reliable way to keep them in sync (short of manual export/import). This is the primary pain
point driving this change.

Additionally, the manual username entry is unverified — any user can claim any GitHub login and
receive role-annotated views. OAuth replaces this with a cryptographically verified identity
issued by GitHub itself.

## Goals

- Add GitHub OAuth login/logout flow (`/auth/login`, `/auth/callback`, `/auth/logout`).
- Store authenticated sessions server-side (PostgreSQL `sessions` table), set as an HttpOnly
  cookie on the browser.
- Store user preferences (starred, ignored, notes) in a new `user_preferences` table, keyed by
  authenticated user identity.
- On first login, detect existing localStorage preferences and offer a one-time migration import.
- Replace manual GitHub username input with session-derived identity on the backend.
- Deprecate and remove the `?username=` query parameter from all API endpoints.
- Unauthenticated users continue to see the full PR queue, teams, and scoreboard (read-only).
- Authentication gates personalisation features: stars, ignore, notes, and role annotations.

## Non-goals

- Role-based access control or admin-only features.
- Persisting the GitHub OAuth access token long-term (used only during login to fetch the user
  profile, then discarded).
- Supporting multiple OAuth providers (GitHub only).
- Real-time preference sync across open tabs (a page reload is sufficient).
- Merging preferences on import (replace-only, matching existing export/import behaviour).
- Changing any PR data ingestion logic (worker, perceval, events sync).

## Constraints

- The GitHub OAuth App must be registered at github.com/settings/developers. The `client_id`
  and `client_secret` go into `config.toml` under a new `[auth]` section.
- Sessions use random 32-byte hex tokens stored in a `sessions` DB table — no JWTs.
- The `?username=` parameter is deprecated (Option A): removed from all endpoints. Unauthenticated
  browsing has no role annotations; role annotations are derived exclusively from the session.
- The full PR object is no longer cached in localStorage for starred PRs — only the PR number is
  stored server-side. The frontend refetches starred PR details from `GET /api/prs?numbers=...`.
- Three new DB tables require an Alembic migration: `users`, `sessions`, `user_preferences`.
- The existing `store.js` localStorage store is replaced by API calls; localStorage is cleared
  after a successful migration import.
