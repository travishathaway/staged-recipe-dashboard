# Design: PR Role Annotations and Filter

## Architecture Overview

```
Browser                                    Backend
──────────────────────────────────         ──────────────────────────────────
preferences.profile.githubUsername
  │
  ▼
api.js: getPRs({ username, roles })
  │
  │  GET /api/prs?username=travis
  │              &roles=author,reviewer
  │              &team=python&offset=20
  │
  ▼                                        list_prs()
                                             + LEFT JOIN pr_reviews ON reviewer=username
                                             + LEFT JOIN pr_review_comments ON commenter=username
                                             + compute roles[] per PR
                                             + WHERE role filter (if roles param set)
                                             + paginate over filtered set
  │
  ◀── [{...pr, roles: ["author"]}, ...]
  │
Overview.svelte
  ├── selectedRoles: Set<string>
  ├── checkboxes (only when username set)
  ├── visiblePRs = teamPRs (no client filtering)
  └── PRCard: renders role badges from pr.roles
```

The `username` param is an annotation context. When provided with no `roles` filter, the full
unfiltered PR set is returned with each PR annotated. When `roles` is also provided, the server
filters to PRs where the user holds at least one of those roles, and pagination applies to
that filtered set.

---

## Backend: `GET /api/prs` Changes

### New query parameters

```python
username: str | None = Query(None, description="GitHub login for role annotation and filtering")
roles: list[str] = Query([], description="Filter to PRs where username holds these roles: author, reviewer, commenter")
```

### `PRResponse` schema update

Add `roles: list[str]` to the Pydantic model. It is always present; empty list when no
`username` was provided or user has no role on the PR.

```python
class PRResponse(BaseModel):
    number: int
    title: str | None
    author: str | None
    state: str
    html_url: str | None
    created_at: datetime | None
    waiting_since: datetime | None
    labels: list[str]
    roles: list[str]   # NEW — e.g. ["author", "reviewer"]
```

### Role annotation query

When `username` is provided, compute roles per PR using EXISTS subqueries (efficient, avoids
row multiplication from JOINs on one-to-many relationships):

```python
def _role_annotations(username: str):
    """Return three boolean columns: is_author, is_reviewer, is_commenter."""
    is_author = (PullRequest.author == username).label("is_author")

    is_reviewer = exists(
        select(PRReview.id).where(
            PRReview.pr_number == PullRequest.number,
            PRReview.reviewer == username,
        )
    ).label("is_reviewer")

    is_commenter = exists(
        select(PRReviewComment.id).where(
            PRReviewComment.pr_number == PullRequest.number,
            PRReviewComment.commenter == username,
        )
    ).label("is_commenter")

    return is_author, is_reviewer, is_commenter
```

These are added to the SELECT when `username` is present. The `_to_pr_response` helper is
extended to accept the boolean flags and build the `roles` list:

```python
def _build_roles(is_author: bool, is_reviewer: bool, is_commenter: bool) -> list[str]:
    roles = []
    if is_author:    roles.append("author")
    if is_reviewer:  roles.append("reviewer")
    if is_commenter: roles.append("commenter")
    return roles
```

### Role filter (when `roles` param provided)

When `roles` is non-empty and `username` is set, add a WHERE clause that requires at least one
of the requested roles to be true:

```python
if username and roles:
    role_conditions = []
    if "author" in roles:
        role_conditions.append(PullRequest.author == username)
    if "reviewer" in roles:
        role_conditions.append(
            exists(select(PRReview.id).where(
                PRReview.pr_number == PullRequest.number,
                PRReview.reviewer == username,
            ))
        )
    if "commenter" in roles:
        role_conditions.append(
            exists(select(PRReviewComment.id).where(
                PRReviewComment.pr_number == PullRequest.number,
                PRReviewComment.commenter == username,
            ))
        )
    if role_conditions:
        stmt = stmt.where(or_(*role_conditions))
```

Pagination (`limit` / `offset`) applies after this filter, so the client gets correct page
counts for the filtered set.

### The `numbers` (starred) path

The existing `numbers` path (starred PRs) also gains role annotation when `username` is
provided, using the same EXISTS subquery approach.

---

## Frontend: `api.js`

Update `getPRs` to accept and forward `username` and `roles`:

```js
export function getPRs({ team, status = 'needs_review', limit = 50, offset = 0, username = null, roles = [] } = {}) {
  const params = new URLSearchParams({ status, limit, offset })
  if (team)     params.set('team', team)
  if (username) params.set('username', username)
  if (roles.length > 0) params.set('roles', roles.join(','))
  return fetchJSON(`${BASE}/prs?${params}`)
}
```

---

## Frontend: `Overview.svelte` Changes

### New state

```js
// Initialize selectedRoles from URL: ?roles=author,reviewer
const _rolesParam = _init.get('roles')
let selectedRoles = new Set(_rolesParam ? _rolesParam.split(',').filter(Boolean) : [])
```

### `fetchTeamPRs` update

Pass `username` and `selectedRoles` to `getPRs`:

```js
async function fetchTeamPRs(team, page, starred, username, roles) {
  teamPRsLoading = true
  try {
    if (starred) {
      // existing starred path — also gains username for annotation
      const starredPRs = Object.values($preferences.starred.prs)
      if (starredPRs.length === 0) { teamPRs = []; return }
      let results = starredPRs
      if (team) results = results.filter(pr => (pr.labels || []).includes(team))
      teamPRs = results
    } else {
      const params = {
        status: 'needs_review',
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }
      if (team)            params.team = team
      if (username)        params.username = username
      if (roles.size > 0)  params.roles = [...roles]
      teamPRs = await getPRs(params)
    }
  } finally {
    teamPRsLoading = false
  }
}
```

### Role checkbox toggle

```js
function toggleRole(role) {
  if (selectedRoles.has(role)) {
    selectedRoles.delete(role)
  } else {
    selectedRoles.add(role)
  }
  selectedRoles = selectedRoles   // trigger Svelte reactivity
  currentPage = 1                 // always reset to page 1
}
```

### URL sync update

```js
function syncURL(team, page, starred, roles) {
  const params = new URLSearchParams()
  if (team)         params.set('team', team)
  if (page > 1)     params.set('page', String(page))
  if (starred)      params.set('starred', 'true')
  if (roles.size > 0) params.set('roles', [...roles].join(','))
  const search = params.toString()
  navigate(search ? `/?${search}` : '/', { replace: true })
}
```

### Reactive fetch trigger

```js
$: syncURL(selectedTeam, currentPage, showStarred, selectedRoles)
$: fetchTeamPRs(selectedTeam, currentPage, showStarred, $preferences.profile.githubUsername, selectedRoles)
```

### Role checkboxes UI

Inserted into the filters bar, conditionally rendered when `githubUsername` is set:

```
FILTERS BAR:
┌──────────────────────────────────────────────────────────────┐
│  [★ Starred  3]                                              │
│                                                              │
│  (only shown when githubUsername set:)                       │
│  Your roles:  [✓] Author  [ ] Reviewer  [ ] Commenter        │
└──────────────────────────────────────────────────────────────┘
```

The checkboxes use Bootstrap's `form-check form-check-inline` pattern. The label reads
"Your roles:" to make the context clear.

---

## Frontend: `PRCard.svelte` Changes

`pr.roles` is already on the PR object passed as the `pr` prop. Add a reactive declaration
and badge rendering in the second row:

```js
$: roleBadges = pr.roles ?? []
```

Role badge colors:
- `author`    → `bg-primary-subtle text-primary-emphasis`   (blue)
- `reviewer`  → `bg-success-subtle text-success-emphasis`   (green)
- `commenter` → `bg-secondary-subtle text-secondary-emphasis` (gray)

Rendered alongside the existing team label badges:

```
CURRENT second row:
  @travis  [python] [rust]

PROPOSED second row (when roles non-empty):
  @travis  [python] [rust]  │  [author] [commenter]
                            ↑ subtle visual separator
```

A `·` separator or `|` divider between team labels and role badges keeps them visually distinct.
Role badges are only rendered when `roleBadges.length > 0`.

---

## File Changelist

| File | Change |
|------|--------|
| `src/staged_recipe_dashboard/backend/routes/api.py` | Add `username` + `roles` params; add `roles` field to `PRResponse`; add `_role_annotations()` helper; add role filter WHERE clause |
| `frontend/src/lib/api.js` | Forward `username` and `roles` in `getPRs()` |
| `frontend/src/routes/Overview.svelte` | Add `selectedRoles` state; role checkbox UI; update fetch + URL sync |
| `frontend/src/lib/components/PRCard.svelte` | Render role badges from `pr.roles` |
