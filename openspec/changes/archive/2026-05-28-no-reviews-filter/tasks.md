# Tasks: No Reviews Yet Filter

## Phase 1 — Backend

- [x] **1.1** Add `_no_human_formal_review_filter()` helper to
  `src/staged_recipe_dashboard/backend/routes/api.py`. The function returns a `not_(exists(...))`
  correlated subquery that selects from `pr_reviews` where `pr_number == PullRequest.number`,
  `reviewer_type != 'Bot'`, and `state IN ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED')`.
  Follow the same pattern as the existing `_has_label()` helper.

- [x] **1.2** Add `unreviewed: bool = Query(False)` parameter to `list_prs()` in `api.py`.
  When `unreviewed` is `True`, append `_no_human_formal_review_filter()` to `base_conditions`
  (after the existing `status` and `team` conditions). This ensures the COUNT query and the
  data query both apply the filter, keeping pagination correct.

## Phase 2 — Frontend: `api.js`

- [x] **2.1** Add `unreviewed = false` option to `getPRs()` in `frontend/src/lib/api.js`.
  When `unreviewed` is truthy, append `unreviewed=true` to the URL query params before
  calling `fetchJSON`.

## Phase 3 — Overview: Toggle and State

- [x] **3.1** Add `showUnreviewed` state to `frontend/src/routes/Overview.svelte`. Initialize
  from the URL: `let showUnreviewed = _init.get('unreviewed') === 'true'`. Add
  `toggleUnreviewed()` function that flips `showUnreviewed` and resets `currentPage = 1`.

- [x] **3.2** Update `fetchTeamPRs()` in `Overview.svelte` to accept an `unreviewed`
  parameter. In the non-starred branch, pass `params.unreviewed = true` to `getPRs()` when
  the parameter is truthy. Update the reactive call:
  `$: fetchTeamPRs(selectedTeam, currentPage, showStarred, $preferences.profile.githubUsername, selectedRoles, showUnreviewed)`.

- [x] **3.3** Update `syncURL()` in `Overview.svelte` to accept and include `unreviewed`.
  When `unreviewed` is true, set `params.set('unreviewed', 'true')`. Update the reactive call:
  `$: syncURL(selectedTeam, currentPage, showStarred, selectedRoles, showUnreviewed)`.

- [x] **3.4** Add the "No reviews yet" toggle button to the filters bar in `Overview.svelte`,
  immediately after the existing Starred button. Use `btn btn-sm` with `btn-info` when active
  and `btn-outline-secondary` when inactive. Include a `bi-eye-slash` icon. Bind `on:click`
  to `toggleUnreviewed`.
