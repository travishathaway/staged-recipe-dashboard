# Design: Local User Preferences

## Architecture Overview

All user state lives in browser `localStorage`. No new database tables, no migrations, no
server-side user identity. A single Svelte writable store (`preferences`) is the source of truth;
it hydrates from `localStorage` on app load and auto-persists on every mutation.

The only backend change is a new `numbers` query parameter on `GET /api/prs` so the starred
filter can fetch exactly the starred open PRs (bypassing pagination, which otherwise would miss
starred PRs beyond the first page).

```
Browser                          Backend
─────────────────────────────    ─────────────────────────────
localStorage
  └─ "srdb-preferences" (JSON)
       │
       ▼
  store.js  (Svelte writable)
  ├── profile.githubUsername
  └── starred.prs[]
       │
       ├── PRCard.svelte ──── star toggle
       ├── Overview.svelte ── filters bar + starred fetch
       ├── App.svelte ──────── avatar + nav
       └── Profile.svelte ──── settings page
                                              GET /api/prs?numbers=123,456
                                              (new optional param)
```

---

## Preferences Schema

```json
{
  "version": 1,
  "profile": {
    "githubUsername": null
  },
  "starred": {
    "prs": []
  }
}
```

**Rules:**
- `version` is an integer. Increment when the shape changes; add a migration function per version
  in `store.js`.
- `starred.prs` is an array of integers (PR numbers), not a Set. Sets do not JSON-serialize.
- All fields are present even when null/empty so code can access them without defensive checks.
- The key in localStorage is `"srdb-preferences"`.

**Migration pattern:**

```js
// In store.js — run on load before exposing the store
function migrate(raw) {
  if (raw.version === 1) return raw          // current version, no-op
  // future: if (raw.version === 2) return upgrade_v2_to_v3(raw)
  return DEFAULT_PREFS                        // unknown version, reset
}
```

---

## `frontend/src/lib/store.js` (new file)

```js
import { writable } from 'svelte/store'

const KEY = 'srdb-preferences'

const DEFAULT_PREFS = {
  version: 1,
  profile: { githubUsername: null },
  starred: { prs: [] },
}

function loadPrefs() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY))
    if (!raw || typeof raw.version !== 'number') return { ...DEFAULT_PREFS }
    return migrate(raw)
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

function migrate(raw) {
  if (raw.version === 1) return raw
  return { ...DEFAULT_PREFS }
}

function createPreferencesStore() {
  const { subscribe, update, set } = writable(loadPrefs())

  function persist(fn) {
    update(prefs => {
      const next = fn(prefs)
      localStorage.setItem(KEY, JSON.stringify(next))
      return next
    })
  }

  return {
    subscribe,

    setUsername(username) {
      persist(p => ({ ...p, profile: { ...p.profile, githubUsername: username || null } }))
    },

    starPR(number) {
      persist(p => {
        if (p.starred.prs.includes(number)) return p
        return { ...p, starred: { prs: [...p.starred.prs, number] } }
      })
    },

    unstarPR(number) {
      persist(p => ({ ...p, starred: { prs: p.starred.prs.filter(n => n !== number) } }))
    },

    clearStarred() {
      persist(p => ({ ...p, starred: { prs: [] } }))
    },

    exportJSON() {
      const data = JSON.parse(localStorage.getItem(KEY) || '{}')
      const blob = new Blob([JSON.stringify({ ...data, exportedAt: new Date().toISOString() }, null, 2)],
        { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'staged-recipe-dashboard-settings.json'
      a.click()
      URL.revokeObjectURL(url)
    },

    importJSON(jsonString) {
      const parsed = JSON.parse(jsonString)
      if (typeof parsed.version !== 'number') throw new Error('Invalid settings file')
      const migrated = migrate(parsed)
      localStorage.setItem(KEY, JSON.stringify(migrated))
      set(migrated)
    },

    reset() {
      localStorage.removeItem(KEY)
      set({ ...DEFAULT_PREFS })
    },
  }
}

export const preferences = createPreferencesStore()
```

---

## Backend: `GET /api/prs` — New `numbers` Parameter

Add an optional `numbers` query parameter to `list_prs` in `backend/routes/api.py`.

When `numbers` is provided:
- It is a comma-separated list of PR numbers, e.g. `?numbers=123,456,789`.
- The endpoint ignores `status`, `team`, `limit`, and `offset` — it returns exactly the open PRs
  whose numbers appear in the list.
- Only open PRs are returned (merged/closed PRs are silently omitted).
- The response shape is identical to the existing `PRResponse` list.

```python
@router.get("/prs", response_model=list[PRResponse])
def list_prs(
    numbers: str | None = Query(None, description="Comma-separated PR numbers for starred fetch"),
    # ... existing params unchanged ...
):
    if numbers is not None:
        number_list = [int(n.strip()) for n in numbers.split(',') if n.strip().isdigit()]
        stmt = (
            select(PullRequest, waiting_since_col)
            .outerjoin(PRLabelHistory, ...)
            .where(
                PullRequest.state == "open",
                PullRequest.number.in_(number_list),
            )
            .order_by(PRLabelHistory.applied_at.asc().nullslast())
        )
        rows = db.execute(stmt).all()
        return [_to_pr_response(pr, ws, db) for pr, ws in rows]
    # ... existing logic unchanged ...
```

`api.js` gains a matching helper:

```js
export function getStarredPRs(numbers) {
  // numbers: number[]
  const params = new URLSearchParams({ numbers: numbers.join(',') })
  return fetchJSON(`${BASE}/prs?${params}`)
}
```

---

## Nav: `App.svelte` Changes

### Layout

```
BEFORE:
[brand]  Review Dashboard           [Overview]  [Scoreboard]

AFTER:
[brand]                [Overview]  [Scoreboard]             [avatar]
                        ─────────  (active underline)       dropdown ▾
```

- Remove the `<span class="text-secondary small ms-2 ...">Review Dashboard</span>`.
- Move `Overview` and `Scoreboard` links to the left (after the brand, before the avatar).
- Add active-route highlighting using `svelte-routing`'s `Link` component or by comparing
  `window.location.pathname` reactively with a Svelte store derived from the router. Since
  `svelte-routing` doesn't expose a current-path store natively, track it with a writable store
  updated in `onMount` and whenever `navigate` is called — or use the `use:link` directive plus
  a `class:active` binding comparing `href` to `$page` from a simple path store.

  Simplest workable approach: import a `currentPath` writable store, set it in `onMount` and
  after every navigation event, and add `class:active` to each nav link.

- Avatar section (right side):
  - If `$preferences.profile.githubUsername` is set: show
    `<img src="https://github.com/{username}.png?size=32" class="rounded-circle" width="32" height="32">`
  - If not set: show Bootstrap icon `bi-person-circle` (32px).
  - Wrap in a Bootstrap dropdown (`data-bs-toggle="dropdown"`).
  - Dropdown menu contents:
    - If username set: `<span class="dropdown-item-text fw-semibold">@{username}</span>` + divider
    - `<a class="dropdown-item" href="/profile" use:link>Profile</a>`
    - If username not set: small helper text "Set up your profile" above the link

---

## Overview: Filters Bar

Insert a filters bar between the mobile hamburger button and the PR list (inside the `col-12 col-md-9` panel).

```svelte
<!-- Filters bar -->
<div class="d-flex align-items-center gap-2 mb-3">
  <button
    class="btn btn-sm"
    class:btn-warning={showStarred}
    class:btn-outline-secondary={!showStarred}
    on:click={toggleStarred}
  >
    <i class="bi" class:bi-star-fill={showStarred} class:bi-star={!showStarred}></i>
    Starred
    {#if starredCount > 0}
      <span class="badge text-bg-light ms-1">{starredCount}</span>
    {/if}
  </button>
</div>
```

**State changes in `Overview.svelte`:**

- Import `preferences` from `store.js`.
- Add `let showStarred = false`.
- `$: starredCount = $preferences.starred.prs.length`
- `$: starredPRNumbers = $preferences.starred.prs`

**Fetch logic when `showStarred` is active:**

```js
async function fetchTeamPRs(team, page, starred, starredNumbers) {
  teamPRsLoading = true
  try {
    if (starred) {
      if (starredNumbers.length === 0) {
        teamPRs = []
        return
      }
      // Fetch starred open PRs; team filter applied client-side from returned results
      let results = await getStarredPRs(starredNumbers)
      if (team) results = results.filter(pr => pr.labels.includes(team))
      teamPRs = results
    } else {
      // existing path unchanged
      const params = { status: 'needs_review', limit: PAGE_SIZE, offset: (page-1)*PAGE_SIZE }
      if (team) params.team = team
      teamPRs = await getPRs(params)
    }
  } finally {
    teamPRsLoading = false
  }
}
```

When `showStarred` is active, pagination is hidden (the result set is small and complete).

URL sync: add `starred=true` to the URLSearchParams when active.

---

## `PRCard.svelte` — Star Toggle

Add a star button to the right side of each PRCard, alongside the existing wait-time badge.

```svelte
<script>
  import { preferences } from '../store.js'
  export let pr
  // ...existing reactive declarations...
  $: isStarred = $preferences.starred.prs.includes(pr.number)

  function toggleStar(e) {
    e.preventDefault()
    e.stopPropagation()
    if (isStarred) {
      preferences.unstarPR(pr.number)
    } else {
      preferences.starPR(pr.number)
    }
  }
</script>
```

In the template, add the star button next to the wait badge in the top-right `d-flex` row:

```svelte
<button
  class="btn btn-sm p-0 border-0 bg-transparent"
  style="line-height:1; font-size:1rem"
  on:click={toggleStar}
  title={isStarred ? 'Unstar PR' : 'Star PR'}
  aria-label={isStarred ? 'Unstar' : 'Star'}
>
  <i class="bi" class:bi-star-fill={isStarred} class:bi-star={!isStarred}
     class:text-warning={isStarred} class:text-secondary={!isStarred}></i>
</button>
```

---

## `/profile` Route: `Profile.svelte` (new file)

New route at `frontend/src/routes/Profile.svelte`. Registered in `App.svelte` as
`<Route path="/profile" component={Profile} />`.

### Sections

**GitHub Username**
```
GitHub Username
┌─────────────────────────────────┐
│ travishh                        │  [Save]
└─────────────────────────────────┘
Used to show your profile avatar in the nav.
```
- Controlled input bound to a local `draftUsername` variable.
- Save calls `preferences.setUsername(draftUsername)`.
- Show success feedback ("Saved") for 2 seconds after saving.

**Starred PRs**
```
Starred Pull Requests
You have 7 starred pull requests.

[Clear all starred]
```
- Count from `$preferences.starred.prs.length`.
- "Clear all starred" opens an inline confirmation:
  `"Are you sure? This will remove all starred PRs." [Confirm] [Cancel]`
- Confirm calls `preferences.clearStarred()`.

**Data / Portability**
```
Export & Import

[Export settings]   [Import settings]

Export saves your profile and starred PRs as a JSON file you can
import on another device.

Import replaces all current settings.
```
- Export: calls `preferences.exportJSON()`.
- Import: hidden `<input type="file" accept=".json">`, triggered by the Import button.
  - On file selected: read with `FileReader`, parse JSON, check if `$preferences` has any
    non-default data (username set OR starred list non-empty). If so, show confirmation:
    `"Importing will delete all your current settings on this site. Continue?"` [Import] [Cancel]
  - On confirm: call `preferences.importJSON(text)`.

---

## File Changelist

| File | Change |
|------|--------|
| `frontend/src/lib/store.js` | **New** — preferences store |
| `frontend/src/lib/api.js` | Add `getStarredPRs(numbers)` helper |
| `frontend/src/lib/components/PRCard.svelte` | Add star toggle button |
| `frontend/src/routes/Overview.svelte` | Import store; add filters bar; update fetch logic |
| `frontend/src/routes/Profile.svelte` | **New** — settings page |
| `frontend/src/App.svelte` | Redesign nav; add `/profile` route |
| `src/staged_recipe_dashboard/backend/routes/api.py` | Add `numbers` param to `GET /api/prs` |
