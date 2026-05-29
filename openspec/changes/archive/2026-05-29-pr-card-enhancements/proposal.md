# Proposal: PR Card Enhancements

## What

Three visual and interactive improvements to the PR card component in the staged-recipe dashboard:

1. **Ignore button** — A new icon button on each PR card to mark a PR as ignored. Ignored PRs remain in the list but are rendered at 50% opacity to visually recede, signalling "I've seen this, it's not relevant to me right now." Toggling again restores normal display. No separate filter is added.

2. **Border-based status styling** — Replace the hard-coded light-green background on "author replied / ready for review" PRs with a colored left border, matching the existing design language of the "blocked" state. All cards get a 5px left border with rounded corners: green (Bootstrap `--bs-success`) for ready-to-review, gray for neutral, and the existing orange remains for blocked. The inline `background-color` hack is removed.

3. **Inline PR annotations** — A pencil icon button on each PR card opens an inline editable text area directly on the card. The user can type personal notes about a PR. Notes are saved on blur. When a note exists, the pencil icon renders in the Bootstrap primary color; when empty, it renders in muted gray. The note text is displayed below the existing two rows as a third row, styled as small italic muted text. A "Clear orphaned notes" action is added to the Profile page to purge notes for PRs that are no longer in the local starred cache or whose PR number no longer appears in the active list.

## Why

Reviewers process a large, ever-changing queue. The current card UI gives no way to record personal context, deprioritize noise, or distinguish "I need to look at this" from "I already know what's happening here." These three additions give reviewers a lightweight personal workspace layer on top of the shared queue — all stored locally, no backend required.

The border-based status styling also removes the visual inconsistency between the "blocked" state (left orange border) and the "ready" state (full background color), unifying them into a single left-border vocabulary.

## Goals

- Add an ignore button to `PRCard.svelte` with `bi-eye-slash` icon; store ignored state in `preferences.ignored.prs` (key → `true`); apply `opacity-50` class to the `<li>` when ignored.
- Replace the `background-color: #cdffe552` inline style on "author replied" PRs with a `5px` left green border using Bootstrap's success color. Add a `5px` left gray border to all other cards for visual consistency. Apply rounded corners via `border-radius` scoped CSS.
- Add a pencil icon button (`bi-pencil`) to each PR card. Clicking it reveals an inline `<textarea>` on the card. Notes persist in `preferences.notes.prs` (PR number → string). Pencil icon uses `text-primary` when a note exists, `text-secondary` when empty.
- Display the note text as a third row on the card when a note exists (read-only unless editing).
- Add a "Clear orphaned notes" button on the Profile page that removes note entries for PR numbers not present in `preferences.starred.prs`.
- Bump the preferences store schema to `version: 3` with a migration that adds `ignored: { prs: {} }` and `notes: { prs: {} }` to existing `version: 2` data.

## Non-goals

- No server-side persistence of ignored state or notes — all localStorage only.
- No filter UI for ignored PRs (they stay in the list, faded).
- No rich text / markdown in annotations — plain textarea only.
- No "clear all notes" or bulk-clear beyond the orphaned-notes cleanup on Profile.
- No changes to the Team page layout beyond inheriting the updated PRCard component.

## Constraints

- All changes are entirely frontend (no backend API changes).
- The existing `border-start` / `border-warning` classes on "blocked" PRs continue to work; the new border system must coexist cleanly.
- The star and ignore buttons are mutually exclusive in intent but not technically enforced — a user can have a PR both starred and ignored; the UI should handle that gracefully (both icons active simultaneously is fine).
- The preferences migration must be additive and non-destructive: existing starred data is preserved exactly.
