# Tasks: PR Author Replied Indicator

## Phase 1 — Backend: New Fields and Subquery

- [x] **1.1** Update `PRResponse` in `src/staged_recipe_dashboard/backend/routes/api.py`:
  Add `last_commenter: str | None = None` and `author_replied: bool = False` to the Pydantic
  model. Both default to safe values for backward compatibility.

- [x] **1.2** Add `_last_human_commenter_subquery()` helper in `api.py`. It should use
  `union_all` to combine:
  - `pr_review_comments` filtered to `commenter_type == 'User'`, selecting `pr_number`,
    `commenter`, `created_at` as `ts`
  - `pr_reviews` filtered to `reviewer_type == 'User'`, selecting `pr_number`, `reviewer` as
    `commenter`, `submitted_at` as `ts`
  The combined subquery is ordered by `ts DESC`, limited to 1 row, correlated on
  `PullRequest.number`, and returned as a scalar subquery labeled `"last_commenter"`.
  Import `union_all` from `sqlalchemy` at the top of the file.

- [x] **1.3** Add `_last_human_commenter_subquery()` to the `select_cols` list in the main
  `list_prs()` query path (the non-starred branch). The subquery is added unconditionally —
  it does not depend on `username`.

- [x] **1.4** Apply the same subquery addition to the `numbers` (starred) SELECT path in
  `list_prs()` so starred PR cards also receive the `last_commenter` value.

- [x] **1.5** Update `_to_pr_response()` (or the equivalent inline row-processing logic) to
  read `last_commenter = getattr(row, "last_commenter", None)` from the query row and derive
  `author_replied = bool(last_commenter and last_commenter == pr.author)`. Pass both values
  to the `PRResponse` constructor.

## Phase 2 — Frontend: `PRCard.svelte`

- [x] **2.1** Add two reactive declarations to `PRCard.svelte`:
  ```js
  $: authorReplied = pr.author_replied ?? false
  $: lastCommenter = pr.last_commenter ?? null
  ```

- [x] **2.2** Update the `<li>` element's conditional classes so the blocked-state classes
  (`border-start`, `border-3`, `border-warning`, `opacity-75`) only apply when
  `isBlocked && !authorReplied`. Add an inline `style` binding that sets
  `background-color: #d1f0e0` when `authorReplied` is true, and an empty string otherwise.

- [x] **2.3** In the second metadata row `<div>`, add a conditional block after the existing
  team labels and role badges:
  ```svelte
  {#if authorReplied && lastCommenter}
    <span class="text-secondary" aria-hidden="true">·</span>
    <span class="text-success-emphasis" style="font-size: 0.85em;">
      last: @{lastCommenter}
    </span>
  {/if}
  ```
  This displays the last commenter's GitHub login only when `author_replied` is true.
