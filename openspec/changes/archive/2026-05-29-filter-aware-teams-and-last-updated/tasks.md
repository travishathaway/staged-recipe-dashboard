# Tasks: Filter-Aware Team Counts and Last Updated Timestamp

## Phase 1 — Backend: `PRListResponse` last_updated_at

- [x] **1.1** Add `last_updated_at: datetime | None = None` to the `PRListResponse` Pydantic
  model in `src/staged_recipe_dashboard/backend/routes/api.py`.

- [x] **1.2** In `list_prs`, add a `SELECT MAX(pull_requests.updated_at) WHERE state = 'open'`
  scalar query immediately before each `return PRListResponse(...)` call (both the `numbers`
  path and the main paginated path). Pass the result as `last_updated_at=last_updated` in both
  `PRListResponse` constructors.

## Phase 2 — Backend: `list_teams` filter parameters

- [x] **2.1** Add `username: str | None = Query(None)`, `roles: str | None = Query(None)`, and
  `unreviewed: bool = Query(False)` parameters to the `list_teams` endpoint function in
  `api.py`. Keep all defaults so the existing `list_teams(db=db)` call in `get_stats` is
  unaffected.

- [x] **2.2** Inside `list_teams`, after the existing `team_labels` discovery query, parse
  `roles` into `role_list` (same pattern as `list_prs`). Build an `extra_conditions` list:
  add `or_(*role_conditions)` when `username` and `role_list` are both set (author equality
  check + EXISTS subqueries for reviewer/commenter), and append
  `_no_human_formal_review_filter()` when `unreviewed` is true.

- [x] **2.3** Spread `*extra_conditions` into each per-team `needs_review` and `blocked`
  COUNT query's `.where()` call so the filter conditions are applied to both counts.

## Phase 3 — Frontend: `api.js` — `getTeams()` update

- [x] **3.1** Update `getTeams()` in `frontend/src/lib/api.js` to accept an options object
  `{ username = null, roles = [], unreviewed = false } = {}`. Build a `URLSearchParams` and
  append `username`, `roles` (comma-joined), and `unreviewed=true` when non-empty/truthy.
  Update the JSDoc comment accordingly.

## Phase 4 — Frontend: `Overview.svelte` — reactive teams fetch

- [x] **4.1** Add `let teamsLoaded = false` state variable to `Overview.svelte`. Remove the
  `teams = await getTeams()` and `totalWaiting = teams.reduce(...)` lines from `onMount`. Add
  the `$: totalWaiting = teams.reduce((sum, t) => sum + t.needs_review_count, 0)` reactive
  declaration in the script block.

- [x] **4.2** Add the `fetchTeams(username, roles, unreviewed, starred)` async function to
  `Overview.svelte`. When `starred` is true, set `teamsLoaded = true` (if not already) and
  return early. Otherwise call `getTeams({ username, roles: roles?.size > 0 ? [...roles] : [],
  unreviewed })`, assign the result to `teams`, and set `teamsLoaded = true` in a `finally`
  block. Catch errors silently (non-fatal — sidebar degrades gracefully).

- [x] **4.3** Replace the manual `let loading = true` / `loading = false` pattern with a
  reactive declaration: `$: loading = !teamsLoaded`. Remove the `loading = false` assignment
  from `onMount` (keep the `onMount` block for its `error` handling if needed, otherwise
  simplify it). Verify the page loading gate still works correctly.

- [x] **4.4** Add the reactive statement:
  `$: fetchTeams($githubUsername, selectedRoles, showUnreviewed, showStarred)`
  This must be placed after the `fetchTeams` function definition and the `$githubUsername`
  import is already in scope from the existing reactive fetch statement.

## Phase 5 — Frontend: `Overview.svelte` — last updated display

- [x] **5.1** Add `let lastUpdatedAt = null` state variable to `Overview.svelte`.

- [x] **5.2** Add the `timeAgo(isoString)` helper function to the script block: returns
  `'just now'` for < 1 minute, `'N minute(s) ago'` for < 1 hour, `'N hour(s) ago'` for
  < 24 hours, `'N day(s) ago'` otherwise. Returns `null` if `isoString` is falsy.

- [x] **5.3** In `fetchTeamPRs`, after `teamPRs = data.results ?? []` and
  `filteredTotal = data.total ?? 0`, add:
  `if (data.last_updated_at && !lastUpdatedAt) { lastUpdatedAt = data.last_updated_at }`
  to capture the value on the first successful fetch only.

- [x] **5.4** In the `Overview.svelte` template, immediately after the closing `</h3>` of the
  "Reviews requested" heading (which contains the `{totalWaiting}` span), add:
  ```svelte
  {#if lastUpdatedAt}
    <p class="text-secondary small mb-0">Last updated: {timeAgo(lastUpdatedAt)}</p>
  {/if}
  ```

## Phase 6 — Frontend: `PRCard.svelte` — always show last commenter

- [x] **6.1** In `frontend/src/lib/components/PRCard.svelte`, change the condition on the
  "last commenter" display from `{#if authorReplied && lastCommenter}` to
  `{#if lastCommenter}`. Change the color class from the unconditional `text-success-emphasis`
  to `text-success-emphasis` when `authorReplied` is true and `text-secondary` otherwise, so
  the green highlight is preserved as a signal that the author specifically was the last to
  comment.
