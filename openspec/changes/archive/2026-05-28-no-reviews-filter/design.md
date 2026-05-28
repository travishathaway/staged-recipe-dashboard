# Design: No Reviews Yet Filter

## Architecture Overview

```
Browser                                    Backend
──────────────────────────────────         ──────────────────────────────────
Overview.svelte
  │
  │  showUnreviewed: boolean (state)
  │  ← initialized from ?unreviewed=true in URL
  │
  ▼
api.js: getPRs({ ..., unreviewed: true })
  │
  │  GET /api/prs?status=needs_review
  │              &unreviewed=true
  │              &team=python&offset=0
  │
  ▼                                        list_prs()
                                             + _no_human_formal_review_filter()
                                             │  NOT EXISTS (
                                             │    SELECT 1 FROM pr_reviews
                                             │    WHERE pr_number = pr.number
                                             │      AND reviewer_type != 'Bot'
                                             │      AND state IN (
                                             │        'APPROVED',
                                             │        'CHANGES_REQUESTED',
                                             │        'DISMISSED'
                                             │      )
                                             │  )
                                             + appended to base_conditions
                                             + paginate over filtered set
  │
  ◀── { results: [...], total: N }
  │
Overview.svelte renders filtered PR list
```

---

## Backend: `GET /api/prs` Changes

### New query parameter

```python
unreviewed: bool = Query(False, description="If true, only return PRs with no formal human review (APPROVED/CHANGES_REQUESTED/DISMISSED)")
```

### New filter helper

```python
def _no_human_formal_review_filter():
    """Subquery: PR has no non-bot APPROVED/CHANGES_REQUESTED/DISMISSED review."""
    return not_(
        exists(
            select(PRReview.id).where(
                PRReview.pr_number == PullRequest.number,
                PRReview.reviewer_type != "Bot",
                PRReview.state.in_(["APPROVED", "CHANGES_REQUESTED", "DISMISSED"]),
            )
        )
    )
```

This follows the exact same pattern as the existing `_has_label()` helper — a `NOT EXISTS`
correlated subquery. `COMMENTED` state reviews are intentionally excluded from the `IN` list,
so a PR with only comment-type reviews still passes the filter.

### Integration into `list_prs()`

When `unreviewed=True`, append the filter to `base_conditions` alongside the existing
`status` and `team` filters:

```python
if unreviewed:
    base_conditions.append(_no_human_formal_review_filter())
```

This applies before the COUNT query and the data query, so pagination is correct over the
filtered set. The `numbers` (starred) path is not affected — unreviewed is not applied there.

---

## Frontend: `api.js`

Add `unreviewed` option to `getPRs()`:

```js
export function getPRs({
  team, status = 'needs_review', limit = 50, offset = 0,
  username = null, roles = [], unreviewed = false
} = {}) {
  const params = new URLSearchParams({ status, limit, offset })
  if (team)          params.set('team', team)
  if (username)      params.set('username', username)
  if (roles.length > 0)  params.set('roles', roles.join(','))
  if (unreviewed)    params.set('unreviewed', 'true')
  return fetchJSON(`${BASE}/prs?${params}`)
}
```

---

## Frontend: `Overview.svelte` Changes

### New state

```js
// Initialize from URL: ?unreviewed=true
let showUnreviewed = _init.get('unreviewed') === 'true'
```

### Toggle function

```js
function toggleUnreviewed() {
  showUnreviewed = !showUnreviewed
  currentPage = 1
}
```

### `fetchTeamPRs` update

Pass `unreviewed` to `getPRs()` in the non-starred branch:

```js
async function fetchTeamPRs(team, page, starred, username, roles, unreviewed) {
  // ...
  if (!starred) {
    const params = { status: 'needs_review', limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }
    if (team)       params.team = team
    if (username)   params.username = username
    if (roles.size > 0) params.roles = [...roles]
    if (unreviewed) params.unreviewed = true
    const data = await getPRs(params)
    teamPRs = data.results
    filteredTotal = data.total
  }
  // ...
}
```

### URL sync update

```js
function syncURL(team, page, starred, roles, unreviewed) {
  const params = new URLSearchParams()
  if (team)           params.set('team', team)
  if (page > 1)       params.set('page', String(page))
  if (starred)        params.set('starred', 'true')
  if (roles.size > 0) params.set('roles', [...roles].join(','))
  if (unreviewed)     params.set('unreviewed', 'true')
  const search = params.toString()
  navigate(search ? `/?${search}` : '/', { replace: true })
}
```

### Reactive triggers update

```js
$: syncURL(selectedTeam, currentPage, showStarred, selectedRoles, showUnreviewed)
$: fetchTeamPRs(selectedTeam, currentPage, showStarred, $preferences.profile.githubUsername, selectedRoles, showUnreviewed)
```

### Toggle button UI

Added to the filters bar alongside the existing Starred button:

```
FILTERS BAR:
┌───────────────────────────────────────────────────────────────┐
│  [★ Starred  3]  [👁 No reviews yet]                          │
│                                                               │
│  (when githubUsername set:)                                   │
│  Your roles:  [ ] Author  [ ] Reviewer  [ ] Commenter         │
└───────────────────────────────────────────────────────────────┘
```

The button uses the same `btn btn-sm` pattern as Starred:
- Inactive: `btn-outline-secondary`
- Active: `btn-info` (or `btn-outline-info` — consistent with the "informational" nature)

```svelte
<button
  class="btn btn-sm"
  class:btn-info={showUnreviewed}
  class:btn-outline-secondary={!showUnreviewed}
  on:click={toggleUnreviewed}
>
  <i class="bi bi-eye-slash"></i>
  No reviews yet
</button>
```

---

## File Changelist

| File | Change |
|------|--------|
| `src/staged_recipe_dashboard/backend/routes/api.py` | Add `unreviewed` param; add `_no_human_formal_review_filter()` helper; append filter to `base_conditions` when active |
| `frontend/src/lib/api.js` | Add `unreviewed` option to `getPRs()` |
| `frontend/src/routes/Overview.svelte` | Add `showUnreviewed` state; toggle button UI; update `fetchTeamPRs`, `syncURL`, and reactive triggers |
