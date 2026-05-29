# Tasks: PR Role Annotations and Filter

## Phase 1 — Backend: Role Annotation and Filter

- [x] **1.1** Update `PRResponse` in `src/staged_recipe_dashboard/backend/routes/api.py`:
  Add `roles: list[str]` field to the Pydantic model. Default to empty list. Update
  `_to_pr_response()` to accept and populate the new field.

- [x] **1.2** Add `_role_annotations(username: str)` helper in `api.py` that returns three
  SQLAlchemy EXISTS subquery expressions: `is_author` (`PullRequest.author == username`),
  `is_reviewer` (EXISTS in `pr_reviews` where `reviewer == username`), `is_commenter`
  (EXISTS in `pr_review_comments` where `commenter == username`). Import `PRReview` and
  `PRReviewComment` models at the top of the file.

- [x] **1.3** Add `_build_roles(is_author, is_reviewer, is_commenter) -> list[str]` helper
  that constructs the roles list from the three boolean flags, in order:
  `["author", "reviewer", "commenter"]` for whichever are true.

- [x] **1.4** Add `username: str | None = Query(None)` and
  `roles: list[str] = Query([])` parameters to `list_prs()`. When `username` is provided,
  add the three annotation columns from `_role_annotations()` to the SELECT and pass the
  resulting booleans to `_to_pr_response()` via `_build_roles()`. When both `username` and
  `roles` are non-empty, add a WHERE clause using `or_()` across the matching role conditions
  (author equality check or EXISTS subqueries for reviewer/commenter). This filter is applied
  before `limit`/`offset` so pagination operates on the filtered set.

- [x] **1.5** Apply the same `username` annotation logic to the `numbers` (starred) path in
  `list_prs()` so starred PR cards also display role badges.

## Phase 2 — Frontend: `api.js`

- [x] **2.1** Update `getPRs()` in `frontend/src/lib/api.js` to accept `username` and `roles`
  options (both optional, defaulting to `null` and `[]` respectively). When `username` is
  truthy, append `username=<value>` to the query params. When `roles` is non-empty, append
  `roles=<comma-separated>` to the query params.

## Phase 3 — Overview: Role Checkboxes and Fetch

- [x] **3.1** Add `selectedRoles` state to `frontend/src/routes/Overview.svelte`. Initialize
  from the URL param `?roles=`: parse the comma-separated string into a `Set`. Add
  `toggleRole(role)` function that adds/removes the role from `selectedRoles`, reassigns the
  set to trigger Svelte reactivity, and resets `currentPage = 1`.

- [x] **3.2** Update `fetchTeamPRs()` in `Overview.svelte` to accept `username` and `roles`
  parameters. In the non-starred branch, pass them to `getPRs()` when present. Update the
  reactive call: `$: fetchTeamPRs(selectedTeam, currentPage, showStarred,
  $preferences.profile.githubUsername, selectedRoles)`.

- [x] **3.3** Update `syncURL()` in `Overview.svelte` to include `roles=<comma-separated>`
  in the URL params when `selectedRoles.size > 0`. Update the reactive `syncURL(...)` call
  to pass `selectedRoles`.

- [x] **3.4** Add the role checkboxes UI to the filters bar in `Overview.svelte`. Wrap in
  `{#if $preferences.profile.githubUsername}` so they only appear when a username is set.
  Use Bootstrap `form-check form-check-inline` for each checkbox. The three checkboxes are
  labelled "Author", "Reviewer", "Commenter". Each is checked when its role is in
  `selectedRoles` and calls `toggleRole(role)` on change. Precede the group with a small
  label "Your roles:".

## Phase 4 — PRCard: Role Badges

- [x] **4.1** Update `frontend/src/lib/components/PRCard.svelte` to render role badges.
  Add `$: roleBadges = pr.roles ?? []`. In the second row (alongside team labels and
  `@author`), render a badge for each role in `roleBadges` only when `roleBadges.length > 0`.
  Separate role badges from team labels with a `·` character or a subtle `|` divider.
  Use Bootstrap contextual badge classes per role:
  - `author`    → `bg-primary-subtle text-primary-emphasis`
  - `reviewer`  → `bg-success-subtle text-success-emphasis`
  - `commenter` → `bg-secondary-subtle text-secondary-emphasis`
