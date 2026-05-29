# Design: Filter-Aware Team Counts and Last Updated Timestamp

## Architecture Overview

```
Browser                                       Backend
──────────────────────────────────────        ────────────────────────────────────
$: fetchTeams($githubUsername,
              selectedRoles,
              showUnreviewed)
  │
  │  GET /api/teams?username=travis
  │                &roles=author,reviewer
  │                &unreviewed=true
  │                                          list_teams(username, roles, unreviewed)
  │                                            per-team COUNT with extra WHERE clauses
  ◀── [{ name, needs_review_count, ... }]
  │
  teams[] → sidebar badges + totalWaiting

$: fetchTeamPRs(selectedTeam, currentPage,
                showStarred, $githubUsername,
                selectedRoles, showUnreviewed)
  │
  │  GET /api/prs?...
  │                                          list_prs(...)
  │                                            + SELECT MAX(updated_at) scalar
  ◀── { results, total, last_updated_at }
  │
  teamPRs[]                                  ← unchanged
  lastUpdatedAt → "Last updated: 3 min ago"  ← new
```

---

## Backend: `PRListResponse` — add `last_updated_at`

### Pydantic model change

```python
class PRListResponse(BaseModel):
    results: list[PRResponse]
    total: int
    last_updated_at: datetime | None = None   # NEW
```

### Population in `list_prs`

Replace the final `return` statement with:

```python
last_updated = db.scalar(
    select(func.max(PullRequest.updated_at)).where(PullRequest.state == "open")
)
return PRListResponse(results=results, total=total, last_updated_at=last_updated)
```

This applies to both the `numbers` path (line 270) and the main paginated path (line 339) —
both `return PRListResponse(...)` calls get the field. The query is a single `SELECT MAX()`
on an already-filtered table and adds negligible overhead.

---

## Backend: `list_teams` — filter parameters

### New signature

```python
@router.get("/teams", response_model=list[TeamResponse])
def list_teams(
    username: str | None = Query(None),
    roles: str | None = Query(None),
    unreviewed: bool = Query(False),
    db: Session = Depends(get_db),
):
```

All three parameters default to `None`/`False`, so the existing direct call from `get_stats`
(`list_teams(db=db)`) continues to work without changes.

### Filter conditions

Parse roles and build a shared list of extra WHERE conditions to add to each COUNT query:

```python
role_list = [r.strip() for r in roles.split(",") if r.strip()] if roles else []

extra_conditions = []

# Role filter: OR across the requested roles
if username and role_list:
    role_conditions = []
    if "author" in role_list:
        role_conditions.append(PullRequest.author == username)
    if "reviewer" in role_list:
        role_conditions.append(
            exists(select(PRReview.id).where(
                PRReview.pr_number == PullRequest.number,
                PRReview.reviewer == username,
            ))
        )
    if "commenter" in role_list:
        role_conditions.append(
            exists(select(PRReviewComment.id).where(
                PRReviewComment.pr_number == PullRequest.number,
                PRReviewComment.commenter == username,
            ))
        )
    if role_conditions:
        extra_conditions.append(or_(*role_conditions))

if unreviewed:
    extra_conditions.append(_no_human_formal_review_filter())
```

Each per-team COUNT then spreads `extra_conditions` into its `.where()`:

```python
needs_review = db.scalar(
    select(func.count()).select_from(PullRequest).where(
        _needs_review_filter(),
        _has_label(team_name),
        *extra_conditions,
    )
) or 0

blocked = db.scalar(
    select(func.count()).select_from(PullRequest).where(
        _blocked_filter(),
        _has_label(team_name),
        *extra_conditions,
    )
) or 0
```

---

## Frontend: `api.js` — `getTeams()` update

```js
/**
 * @param {{ username?: string|null, roles?: string[], unreviewed?: boolean }} opts
 * @returns {Promise<Array<{name: string, needs_review_count: number, blocked_count: number}>>}
 */
export function getTeams({ username = null, roles = [], unreviewed = false } = {}) {
  const params = new URLSearchParams()
  if (username) params.set('username', username)
  if (roles.length > 0) params.set('roles', roles.join(','))
  if (unreviewed) params.set('unreviewed', 'true')
  const qs = params.toString()
  return fetchJSON(`${BASE}/teams${qs ? '?' + qs : ''}`)
}
```

The call signature mirrors `getPRs` in style. Called with no arguments it hits
`GET /api/teams` exactly as before — no behavior change for any existing callers.

---

## Frontend: `Overview.svelte` changes

### New state variable

```js
let lastUpdatedAt = null   // datetime string from first successful fetchTeamPRs
```

### Replace `onMount` `getTeams()` with a reactive `fetchTeams` function

Remove from `onMount`:
```js
// REMOVE:
teams = await getTeams()
totalWaiting = teams.reduce((sum, t) => sum + t.needs_review_count, 0)
```

Add a new async function:
```js
async function fetchTeams(username, roles, unreviewed, starred) {
  if (starred) return   // sidebar counts not meaningful in starred mode
  try {
    teams = await getTeams({
      username,
      roles: roles && roles.size > 0 ? [...roles] : [],
      unreviewed,
    })
  } catch (e) {
    // non-fatal — sidebar counts become stale but PR list still works
  }
}
```

Add reactive statement (triggers only on filter changes, not team/page changes):
```js
$: fetchTeams($githubUsername, selectedRoles, showUnreviewed, showStarred)
```

`onMount` retains only the `getStats`-equivalent work (loading the global team list for the
treemap) — which in this case is just the initial `fetchTeams` triggered by the reactive
statement above on mount. The `onMount` block keeps the error/loading handling:

```js
onMount(async () => {
  try {
    // Initial teams fetch is now handled by the reactive $: fetchTeams statement.
    // onMount only needs to set loading = false after the first data arrives.
    // Keep any other onMount work here (none currently).
  } catch (e) {
    error = e.message
  } finally {
    loading = false
  }
})
```

Actually, since `loading` currently gates the entire page render and `teams` was previously
loaded in `onMount`, the reactive `fetchTeams` will fire on component init before `onMount`
completes. `loading` should remain `true` until both the first `fetchTeams` and the global
init are done. The simplest approach: set `loading = false` inside `fetchTeams` after the
first successful call (using a `firstLoad` flag), and keep `onMount` for anything that
doesn't depend on `teams`.

Revised approach — add a `teamsLoaded` flag:
```js
let teamsLoaded = false

async function fetchTeams(username, roles, unreviewed, starred) {
  if (starred) {
    if (!teamsLoaded) teamsLoaded = true  // unblock loading if first call is starred
    return
  }
  try {
    teams = await getTeams({ username, roles: roles && roles.size > 0 ? [...roles] : [], unreviewed })
  } catch (e) {
    // non-fatal
  } finally {
    teamsLoaded = true
  }
}
```

`onMount` sets `loading = false` only after `teamsLoaded` is true. Since `fetchTeams` fires
synchronously as a reactive statement on init, and `onMount` runs after the first render tick,
in practice the async `getTeams()` call resolves and sets `teamsLoaded` before or around the
same time `onMount` runs. Use a simple `tick()` + poll or just let reactivity handle it:
the cleanest approach is to derive `loading` from `teamsLoaded` directly:

```js
// Remove the manual loading/error state for teams; derive from teamsLoaded
$: loading = !teamsLoaded
```

And keep `error` only for catastrophic failures.

### `totalWaiting` becomes reactive

```js
// REMOVE from onMount:
totalWaiting = teams.reduce((sum, t) => sum + t.needs_review_count, 0)

// ADD as reactive declaration:
$: totalWaiting = teams.reduce((sum, t) => sum + t.needs_review_count, 0)
```

### Capture `last_updated_at` in `fetchTeamPRs`

In the non-starred branch of `fetchTeamPRs`, after `const data = await getPRs(params)`:

```js
teamPRs = data.results ?? []
filteredTotal = data.total ?? 0
if (data.last_updated_at && !lastUpdatedAt) {
  lastUpdatedAt = data.last_updated_at  // capture on first successful fetch only
}
```

### `timeAgo` helper

Add a small helper (no library needed):

```js
function timeAgo(isoString) {
  if (!isoString) return null
  const ms = Date.now() - new Date(isoString).getTime()
  const minutes = Math.floor(ms / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}
```

### "Last updated" display

Below the existing "Reviews requested" heading (lines 170–172 of `Overview.svelte`):

```svelte
<h3>Reviews requested: <br />
  <span style="font-size:4rem">{totalWaiting}</span>
</h3>
{#if lastUpdatedAt}
  <p class="text-secondary small mb-0">
    Last updated: {timeAgo(lastUpdatedAt)}
  </p>
{/if}
```

---

## File Changelist

| File | Change |
|------|--------|
| `src/staged_recipe_dashboard/backend/routes/api.py` | Add `last_updated_at` to `PRListResponse`; populate it in both return paths of `list_prs`; add `username`, `roles`, `unreviewed` params to `list_teams`; apply extra filter conditions to per-team COUNTs |
| `frontend/src/lib/api.js` | Update `getTeams()` to accept and forward `username`, `roles`, `unreviewed` |
| `frontend/src/routes/Overview.svelte` | Add `lastUpdatedAt` state; add `timeAgo()` helper; add `fetchTeams()` function + reactive `$:` call; move `totalWaiting` to reactive declaration; capture `last_updated_at` in `fetchTeamPRs`; render "Last updated" line |
