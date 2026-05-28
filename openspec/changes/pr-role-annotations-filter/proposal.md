# Proposal: PR Role Annotations and Filter

## What

Enrich the PR list API and Overview page with per-user role context. When a GitHub username is
stored in local preferences, it is sent as a `username` query parameter on every PR fetch. The
backend uses it to annotate each returned PR with the roles the user holds on that PR:
`"author"`, `"reviewer"`, or `"commenter"` (any combination, as a list).

The Overview page gains a set of role checkboxes — **Author**, **Reviewer**, **Commenter** —
that are only shown when a GitHub username is configured. Selecting one or more roles adds a
`roles` filter to the API request so the server returns only PRs where the user holds at least
one of those roles. Each PR card displays the user's role(s) as small colored badges.

## Why

Reviewers frequently want to track their own involvement in the staged-recipes queue — PRs they
authored, PRs they have already reviewed, or PRs where they left a comment but haven't formally
reviewed. Today there is no way to answer "which of these PRs am I already involved in?" without
visiting GitHub. The new filter turns the dashboard into a personal work queue, not just a
global queue.

The design keeps things simple: the username already lives in `localStorage` from the existing
preferences feature, so no new auth or data entry is required. The backend already stores
`pr_reviews` and `pr_review_comments` with reviewer/commenter logins, so the annotation query
is a natural join over existing data.

## Goals

- Add a `username` query parameter to `GET /api/prs`. When present, each PR in the response
  includes a `roles: list[str]` field listing which roles (`"author"`, `"reviewer"`,
  `"commenter"`) the given user holds on that PR. When absent, `roles` is an empty list.
- Add a `roles` query parameter to `GET /api/prs`. When provided alongside `username`, the
  result set is filtered to only PRs where the user holds at least one of the specified roles.
  Pagination applies to this filtered set normally.
- Show role filter checkboxes (Author, Reviewer, Commenter) on the Overview page, visible only
  when `githubUsername` is set in preferences. Toggling any checkbox triggers a server refetch
  and resets to page 1.
- Display role badges on each PR card when `pr.roles` is non-empty, using distinct colors per
  role for quick visual scanning.
- Sync the active role selection to the URL (`?roles=author,reviewer`) for deep-linking.

## Non-goals

- Client-side role filtering (filtering is done server-side for correct pagination).
- Any changes to how the GitHub username is set (that is handled by the existing preferences
  feature).
- Filtering by roles on the Team page (Overview only for now).
- Showing roles for other users (only the logged-in user's own roles are annotated).

## Constraints

- The `username` param is purely an annotation/filter context — it does not change the default
  result set (no roles selected = full unfiltered results, just annotated).
- `roles: []` means the username was provided but the user has no role on this PR.
  `roles: []` with no username sent is the same shape but carries different semantics — the
  frontend knows whether it sent a username, so no ambiguity in practice.
- Pagination must continue to work correctly when `roles` filter is active — the server paginates
  over the already-filtered set.
- Changing the role selection always resets to page 1 to avoid empty-page edge cases.
- Pagination is hidden when the total result count is <= `PAGE_SIZE` (20), same as today's logic.
