# Design: PR Card Enhancements

## Architecture Overview

All changes are purely frontend. Three PRCard UI features share one common foundation: the preferences store in `store.js`, which gains two new top-level sections (`ignored` and `notes`) and a version bump to `v3`.

```
localStorage["srdb-preferences"]  (v3)
  ├── version: 3
  ├── profile:  { githubUsername }
  ├── starred:  { prs: { "1234": <PR object>, ... } }   ← unchanged
  ├── ignored:  { prs: { "1234": true, ... } }           ← NEW
  └── notes:    { prs: { "1234": "text...", ... } }       ← NEW

        ↕ (loaded on init, persisted on every mutation)

  store.js (Svelte writable)
        ↕ ($preferences reactive subscription)

  PRCard.svelte
    ├── isIgnored  → opacity-50, eye-slash icon active
    ├── isEditing  → shows <textarea> in third row
    ├── hasNote    → pencil icon text-primary, note row visible
    └── border state → left border color (green / gray)

  Profile.svelte
    └── "Clear orphaned notes" section  ← NEW
```

---

## 1. Store Changes (`store.js`)

### New default structure (v3)

```js
const DEFAULT_PREFS = {
  version: 3,
  profile: { githubUsername: null },
  starred:  { prs: {} },
  ignored:  { prs: {} },   // NEW — { "1234": true }
  notes:    { prs: {} },   // NEW — { "1234": "note text" }
}
```

### Migration v2 → v3

```js
function migrate(raw) {
  if (raw.version === 3) return raw
  if (raw.version === 2) {
    return {
      ...raw,
      version: 3,
      ignored: { prs: {} },
      notes:   { prs: {} },
    }
  }
  // v1 → v2 path unchanged (becomes v3 via two-step migration)
  if (raw.version === 1) {
    const v2 = { ...raw, version: 2, starred: { prs: {} } }
    return migrate(v2)  // recurse to v2→v3
  }
  return structuredClone(DEFAULT_PREFS)
}
```

### New store methods

```js
// Ignore / unignore
ignorePR(number) {
  persist(p => ({
    ...p,
    ignored: { prs: { ...p.ignored.prs, [String(number)]: true } }
  }))
},
unignorePR(number) {
  persist(p => {
    const { [String(number)]: _removed, ...rest } = p.ignored.prs
    return { ...p, ignored: { prs: rest } }
  })
},

// Notes
setNote(number, text) {
  const key = String(number)
  persist(p => {
    if (!text || !text.trim()) {
      // empty note → remove the key entirely
      const { [key]: _removed, ...rest } = p.notes.prs
      return { ...p, notes: { prs: rest } }
    }
    return { ...p, notes: { prs: { ...p.notes.prs, [key]: text } } }
  })
},

// Clear notes for PR numbers not in starred.prs
clearOrphanedNotes() {
  persist(p => {
    const starredKeys = new Set(Object.keys(p.starred.prs))
    const filtered = Object.fromEntries(
      Object.entries(p.notes.prs).filter(([k]) => starredKeys.has(k))
    )
    return { ...p, notes: { prs: filtered } }
  })
},
```

---

## 2. PRCard Changes (`PRCard.svelte`)

### New reactive declarations

```js
$: isIgnored  = String(pr.number) in $preferences.ignored.prs
$: noteText   = $preferences.notes.prs[String(pr.number)] ?? ''
$: hasNote    = noteText.length > 0
let isEditing = false
```

### Toggle handlers

```js
function toggleIgnore(e) {
  e.preventDefault()
  e.stopPropagation()
  if (isIgnored) {
    preferences.unignorePR(pr.number)
  } else {
    preferences.ignorePR(pr.number)
  }
}

function openNote(e) {
  e.preventDefault()
  e.stopPropagation()
  isEditing = true
}

function saveNote(e) {
  preferences.setNote(pr.number, e.target.value)
  isEditing = false
}
```

### Updated `<li>` element — border system

The `style` inline background is removed. The `<li>` now carries a CSS class that drives the left border color. Scoped CSS handles the actual border widths and border-radius:

```svelte
<li class="list-group-item list-group-item-action py-2 px-3 pr-card"
  class:pr-card--ready={authorReplied && !isBlocked}
  class:pr-card--blocked={isBlocked && !authorReplied}
  class:opacity-50={isIgnored}>
```

```css
/* Scoped <style> in PRCard.svelte */
.pr-card {
  border-radius: 6px !important;
  border-left: 5px solid var(--bs-border-color) !important;  /* default: gray */
}

.pr-card--ready {
  border-left-color: var(--bs-success) !important;
}

.pr-card--blocked {
  border-left-color: var(--bs-warning) !important;
  opacity: 0.75;
}
```

The existing `class:border-start`, `class:border-3`, `class:border-warning`, `class:opacity-75`, and inline `style={authorReplied ? ...}` are all removed. The old `.border-start { border-left-width: 4px !important }` override is also removed.

Bootstrap's `list-group` normally applies `border-radius` only to the first/last items. The `.pr-card` scoped rule overrides this globally on every card. Since `PRCard` renders as standalone `<li>` items inside the `list-group`, the parent `list-group` itself should be given `border-radius: 0` or the `rounded-0` utility if needed — but in practice the individual card `border-radius` override is enough.

### Row 1: Icon buttons (star + ignore + pencil)

The button group in row 1 gains two new buttons:

```
Row 1: [#1234 title text...]  [14d]  [✏]  [👁]  [★]
                                      ↑    ↑    ↑
                                  pencil  ignore star
```

```svelte
<!-- Pencil / notes button -->
<button class="btn btn-sm p-0 border-0 bg-transparent"
  style="line-height:1; font-size:1rem"
  on:click={openNote}
  title={hasNote ? 'Edit note' : 'Add note'}
  aria-label={hasNote ? 'Edit note' : 'Add note'}>
  <i class="bi bi-pencil"
    class:text-primary={hasNote}
    class:text-secondary={!hasNote}></i>
</button>

<!-- Ignore button -->
<button class="btn btn-sm p-0 border-0 bg-transparent"
  style="line-height:1; font-size:1rem"
  on:click={toggleIgnore}
  title={isIgnored ? 'Un-ignore PR' : 'Ignore PR'}
  aria-label={isIgnored ? 'Un-ignore' : 'Ignore'}>
  <i class="bi"
    class:bi-eye-slash-fill={isIgnored}
    class:bi-eye-slash={!isIgnored}
    class:text-secondary={!isIgnored}
    class:text-muted={isIgnored}></i>
</button>
```

### Row 3: Note display / editing

Appended after the existing row 2 (`small text-secondary` row):

```svelte
{#if hasNote && !isEditing}
  <div class="mt-1 small text-secondary fst-italic note-row">
    {noteText}
  </div>
{/if}

{#if isEditing}
  <div class="mt-1">
    <textarea
      class="form-control form-control-sm"
      rows="2"
      value={noteText}
      on:blur={saveNote}
      on:keydown={(e) => { if (e.key === 'Escape') isEditing = false }}
      autofocus
    ></textarea>
  </div>
{/if}
```

`on:blur={saveNote}` means notes save automatically when focus leaves the textarea. Pressing `Escape` cancels without saving. The `autofocus` attribute ensures the textarea is focused as soon as it mounts.

---

## 3. Profile Page Changes (`Profile.svelte`)

A new section is added between "Starred Pull Requests" and "Export & Import":

### Scope: what counts as "orphaned"

An orphaned note is one whose PR number is **not present in `starred.prs`**. The rationale: starred PRs are the only locally cached PR objects, so if a PR isn't starred it may no longer be open or relevant. This is a lightweight heuristic — the user can always keep notes around by starring the PR.

### New section markup pattern

Follows the same `showClearConfirm` two-step confirmation pattern already used for "Clear all starred":

```js
let showClearOrphanedConfirm = false

function confirmClearOrphaned() {
  preferences.clearOrphanedNotes()
  showClearOrphanedConfirm = false
}
```

```
// Computed count of orphaned notes
$: orphanedNoteCount = Object.keys($preferences.notes.prs)
     .filter(k => !(k in $preferences.starred.prs)).length
```

The section is disabled (button greyed out) when `orphanedNoteCount === 0`.

---

## 4. Visual Summary

```
┌───────────────────────────────────────────────────────────────────┐
│  CARD STATES                                                       │
├─────┬─────────────────────────────────────────────────────────────┤
│  ▌  │  Normal card — 5px gray left border, rounded corners         │
│  ▌  │                                                              │
│  ▌  │  #1234 Some recipe title        14d  [✏] [👁] [★]           │
│  ▌  │  @author  [python]                                           │
├─────┴─────────────────────────────────────────────────────────────┤
│                                                                    │
│  ▌  Ready for review — 5px green (--bs-success) left border        │
│  ▌  (authorReplied && !isBlocked)                                  │
│  ▌                                                                 │
│  ▌  Blocked — 5px orange (--bs-warning) left border + 75% opacity  │
│  ▌  (isBlocked && !authorReplied)                                  │
│  ▌                                                                 │
│     Ignored — gray border + 50% opacity (any state)               │
│     (isIgnored)                                                    │
│                                                                    │
│  ▌  With note — pencil in text-primary color                       │
│  ▌  #1234 Some recipe title        14d  [✏] [👁] [★]              │
│  ▌  @author  [python]                                              │
│  ▌  This PR needs type stubs before I can approve it.  ← row 3    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## File Changelist

| File | Change |
|------|--------|
| `frontend/src/lib/store.js` | Bump to v3; add `ignored`/`notes` defaults; add v2→v3 migration; add `ignorePR`, `unignorePR`, `setNote`, `clearOrphanedNotes` methods |
| `frontend/src/lib/components/PRCard.svelte` | New reactive state; remove old inline style + border classes; add `.pr-card` scoped CSS; add ignore + pencil buttons; add note row 3 |
| `frontend/src/routes/Profile.svelte` | Add "Notes" section with orphaned-note count and clear-confirm action |
