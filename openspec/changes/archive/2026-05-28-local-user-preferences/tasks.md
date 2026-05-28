# Tasks: Local User Preferences

## Phase 1 — Preferences Store

- [x] **1.1** Create `frontend/src/lib/store.js` with the `preferences` writable store as
  specified in design.md. Implement: `loadPrefs()` (loads + migrates from localStorage),
  `migrate(raw)` (v1 no-op, unknown version resets to defaults), and the store methods:
  `setUsername`, `starPR`, `unstarPR`, `clearStarred`, `exportJSON`, `importJSON`, `reset`.
  The localStorage key is `"srdb-preferences"`. The default schema is
  `{ version: 1, profile: { githubUsername: null }, starred: { prs: [] } }`.

## Phase 2 — Backend: `numbers` Filter

- [x] **2.1** Add optional `numbers: str | None` query parameter to `list_prs` in
  `src/staged_recipe_dashboard/backend/routes/api.py`. When provided, parse it as a
  comma-separated list of integers and return only open PRs whose `number` is in that list,
  ignoring `status`, `team`, `limit`, and `offset`. The response shape is unchanged
  (`list[PRResponse]`). Merged/closed PRs are silently omitted (the `.where(state == "open")`
  clause handles this naturally).

- [x] **2.2** Add `getStarredPRs(numbers)` to `frontend/src/lib/api.js`. It takes a `number[]`
  and calls `GET /api/prs?numbers=<comma-separated>`, returning the same PR objects as `getPRs`.

## Phase 3 — PRCard Star Toggle

- [x] **3.1** Update `frontend/src/lib/components/PRCard.svelte`:
  - Import `preferences` from `../store.js`.
  - Add reactive `$: isStarred = $preferences.starred.prs.includes(pr.number)`.
  - Add a star button (Bootstrap icon `bi-star` / `bi-star-fill`) in the top-right area next to
    the wait-time badge. The button calls `preferences.starPR(pr.number)` or
    `preferences.unstarPR(pr.number)`. Use `e.preventDefault(); e.stopPropagation()` to prevent
    the anchor from activating. Starred state uses `text-warning`; unstarred uses `text-secondary`.

## Phase 4 — Overview Filters Bar

- [x] **4.1** Update `frontend/src/routes/Overview.svelte`:
  - Import `preferences` and `getStarredPRs` from their respective modules.
  - Add `let showStarred = false` to component state. Initialize from URL param `?starred=true`
    alongside existing `team` and `page` init.
  - Add reactive `$: starredCount = $preferences.starred.prs.length`.
  - Insert filters bar HTML between the mobile hamburger button and the PR list: a single
    "Starred (N)" toggle button using Bootstrap `btn-outline-secondary` / `btn-warning` for
    inactive / active states and the `bi-star` / `bi-star-fill` icon.
  - Update `fetchTeamPRs` to branch on `showStarred`: when active, call `getStarredPRs` with
    `$preferences.starred.prs`, then optionally client-side filter by `selectedTeam` if set.
    When starred list is empty, set `teamPRs = []` directly. When not active, use existing logic.
  - Update `syncURL` to include `starred=true` in query params when `showStarred` is true.
  - Hide pagination controls when `showStarred` is active (the result set is complete).
  - Update the reactive `$: fetchTeamPRs(...)` call signature to include `showStarred` and
    `$preferences.starred.prs` so it re-fetches when the starred list changes while the filter
    is active.

## Phase 5 — Profile Page

- [x] **5.1** Create `frontend/src/routes/Profile.svelte`:
  - Import `preferences` from `../lib/store.js`.
  - **Username section**: a controlled text input bound to `draftUsername` (initialized from
    `$preferences.profile.githubUsername`). Save button calls `preferences.setUsername(draftUsername)`
    and shows a "Saved" inline confirmation for 2 seconds using a `saved` boolean + `setTimeout`.
  - **Starred PRs section**: display `$preferences.starred.prs.length` count. "Clear all starred"
    button shows an inline confirmation (`showClearConfirm` boolean). On confirm, call
    `preferences.clearStarred()` and reset `showClearConfirm`.
  - **Export & Import section**: Export button calls `preferences.exportJSON()`. Import button
    triggers a hidden `<input type="file" accept=".json">` via `.click()`. On file change, read
    with `FileReader`. If `$preferences` has any non-default data (username set OR starred
    list non-empty), show an inline confirmation:
    "Importing will delete all your current settings on this site. Continue?" [Import] [Cancel].
    On confirm (or immediately if no existing data), call `preferences.importJSON(text)`. Handle
    parse errors with an inline error message.

## Phase 6 — Nav Redesign and Route Registration

- [x] **6.1** Update `frontend/src/App.svelte`:
  - Remove the `<span class="text-secondary small ms-2 d-none d-md-inline">Review Dashboard</span>`.
  - Move `Overview` and `Scoreboard` nav links to immediately after the brand (left side). Add
    active-route highlighting: add a `currentPath` writable store (or use a simple reactive
    variable updated by a `navigate` subscription) and apply `class:active` on each nav link
    when its href matches.
  - Add a profile avatar section on the right side of the nav:
    - Subscribe to `$preferences.profile.githubUsername`.
    - If set: render `<img src="https://github.com/{username}.png?size=32">` in a Bootstrap
      dropdown trigger (`data-bs-toggle="dropdown"`).
    - If not set: render `<i class="bi bi-person-circle fs-4">` as the dropdown trigger.
    - Dropdown menu: username display (if set) + divider + "Profile" link (`href="/profile"
      use:link`). If not set, add helper text "Set up your profile" above the link.
  - Add `import Profile from './routes/Profile.svelte'` and
    `<Route path="/profile" component={Profile} />` to the router.
