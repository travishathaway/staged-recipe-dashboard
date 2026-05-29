# Tasks: PR Card Enhancements

## Phase 1 — Store: v3 Migration and New Methods

- [x] **1.1** Update `DEFAULT_PREFS` in `frontend/src/lib/store.js` to `version: 3` and add
  `ignored: { prs: {} }` and `notes: { prs: {} }` as top-level siblings of `starred`.

- [x] **1.2** Update `migrate()` in `store.js` to handle v2→v3: spread the v2 object, set
  `version: 3`, and attach empty `ignored: { prs: {} }` and `notes: { prs: {} }`. Chain the
  existing v1→v2 path through a recursive `migrate()` call so v1 data also gets the new fields.
  Leave the `return structuredClone(DEFAULT_PREFS)` fallback unchanged.

- [x] **1.3** Add `ignorePR(number)` method to the store: calls `persist()` to set
  `ignored.prs[String(number)] = true` (spread-safe, idempotent).

- [x] **1.4** Add `unignorePR(number)` method to the store: calls `persist()` to destructure
  out `String(number)` from `ignored.prs` and return the rest.

- [x] **1.5** Add `setNote(number, text)` method to the store: calls `persist()`. If `text`
  is empty or whitespace-only, remove the key from `notes.prs`; otherwise set
  `notes.prs[String(number)] = text`.

- [x] **1.6** Add `clearOrphanedNotes()` method to the store: calls `persist()` to filter
  `notes.prs` keeping only keys that exist in `starred.prs`.

## Phase 2 — PRCard: Border System Refactor

- [x] **2.1** In `frontend/src/lib/components/PRCard.svelte`, remove the inline `style` attribute
  that sets `background-color: #cdffe552` and remove the four `class:border-start`,
  `class:border-3`, `class:border-warning`, `class:opacity-75` bindings from the `<li>` element.
  Remove the existing `.border-start { border-left-width: 4px !important }` scoped CSS rule.

- [x] **2.2** Add the `pr-card` base class to the `<li>` element, plus two conditional modifier
  classes: `pr-card--ready` (when `authorReplied && !isBlocked`) and `pr-card--blocked` (when
  `isBlocked && !authorReplied`).

- [x] **2.3** Add scoped CSS to `PRCard.svelte`:
  - `.pr-card` — `border-radius: 6px !important` and `border-left: 5px solid var(--bs-border-color) !important` (the default gray border for all cards).
  - `.pr-card--ready` — `border-left-color: var(--bs-success) !important` (green for author-replied / ready to review).
  - `.pr-card--blocked` — `border-left-color: var(--bs-warning) !important` and `opacity: 0.75` (orange + dim for blocked).

## Phase 3 — PRCard: Ignore Feature

- [x] **3.1** Add reactive declarations to `PRCard.svelte`:
  `$: isIgnored = String(pr.number) in $preferences.ignored.prs`

- [x] **3.2** Add `toggleIgnore(e)` function: calls `e.preventDefault()` + `e.stopPropagation()`,
  then calls `preferences.unignorePR(pr.number)` if `isIgnored`, else `preferences.ignorePR(pr.number)`.

- [x] **3.3** Add `class:opacity-50={isIgnored}` to the `<li>` element.

- [x] **3.4** Add the ignore icon button to the button group in row 1, between the existing
  wait-badge and star button. Use `bi-eye-slash-fill` when `isIgnored`, `bi-eye-slash` when not.
  Icon color: `text-secondary` when not ignored, `text-muted` when ignored. Title/aria-label:
  "Ignore PR" / "Un-ignore PR".

## Phase 4 — PRCard: Inline Notes

- [x] **4.1** Add reactive declarations to `PRCard.svelte`:
  - `$: noteText = $preferences.notes.prs[String(pr.number)] ?? ''`
  - `$: hasNote = noteText.length > 0`
  - `let isEditing = false`

- [x] **4.2** Add `openNote(e)` function: calls `e.preventDefault()` + `e.stopPropagation()`,
  sets `isEditing = true`.

- [x] **4.3** Add `saveNote(e)` function: calls `preferences.setNote(pr.number, e.target.value)`,
  sets `isEditing = false`.

- [x] **4.4** Add the pencil icon button to the button group in row 1, to the left of the ignore
  button. Use `bi-pencil` icon. Color: `text-primary` when `hasNote`, `text-secondary` when not.
  Title/aria-label: "Edit note" / "Add note". On click: calls `openNote`.

- [x] **4.5** Add the note display row (row 3) to `PRCard.svelte` below row 2. When `hasNote &&
  !isEditing`, render a `<div class="mt-1 small text-secondary fst-italic">` containing `{noteText}`.
  When `isEditing`, render a `<div class="mt-1">` containing a `<textarea class="form-control
  form-control-sm" rows="2">` with `value={noteText}`, `on:blur={saveNote}`,
  `on:keydown` (Escape → `isEditing = false`), and `autofocus`.

## Phase 5 — Profile: Orphaned Notes Cleanup

- [x] **5.1** Add `showClearOrphanedConfirm` (boolean, starts `false`) and
  `confirmClearOrphaned()` function to `Profile.svelte`. The function calls
  `preferences.clearOrphanedNotes()` and resets the flag to `false`.

- [x] **5.2** Add a reactive declaration:
  `$: orphanedNoteCount = Object.keys($preferences.notes.prs).filter(k => !(k in $preferences.starred.prs)).length`

- [x] **5.3** Add a new "Notes" section to the Profile page between the "Starred Pull Requests"
  section and the `<hr>` before "Export & Import". Show the orphaned note count. Render a
  "Clear orphaned notes" button (disabled when `orphanedNoteCount === 0`) that, when clicked,
  sets `showClearOrphanedConfirm = true`. Follow the same two-step confirm/cancel pattern as
  the existing "Clear all starred" button.
