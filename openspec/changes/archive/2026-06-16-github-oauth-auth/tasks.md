# Tasks: GitHub OAuth Authentication

## Phase 1 — Configuration

- [x] **1.1** Add `AuthConfig` dataclass to `src/staged_recipe_dashboard/config.py` with fields:
  `github_client_id: str = ""`, `github_client_secret: str = ""`, `base_url: str = "http://localhost:5173"`.
  Add `from_dict` classmethod (same pattern as other config classes). Add `auth: AuthConfig`
  field to `AppConfig`. Wire `AuthConfig.from_dict(raw.get("auth", {}))` into `load_config()`.

## Phase 2 — Database Models and Migration

- [x] **2.1** Add `User`, `Session`, and `UserPreference` ORM models to
  `src/staged_recipe_dashboard/backend/models.py` as specified in design.md. Import `BigInteger`
  (already imported), `ForeignKey` (already imported). Add `timezone` to the datetime import.
  Add `relationship` imports where needed. Session token is a 32-byte random hex string PK.
  UserPreference PK is `(user_id, pref_type, pr_number)`.

- [x] **2.2** Create Alembic migration `src/staged_recipe_dashboard/db/migrations/versions/004_add_auth_tables.py`.
  `revision="004"`, `down_revision="003"`. `upgrade()` creates:
  - `users` table: `id` (Integer PK autoincrement), `github_id` (BigInteger unique not null),
    `github_login` (String not null), `avatar_url` (String nullable), `created_at`
    (DateTime(timezone=True) not null).
  - `sessions` table: `token` (String PK), `user_id` (Integer FK→users.id CASCADE not null),
    `created_at` (DateTime(timezone=True) not null), `expires_at` (DateTime(timezone=True) not null).
  - `user_preferences` table: `user_id` (Integer FK→users.id CASCADE), `pref_type` (String),
    `pr_number` (Integer), `data` (JSONB nullable), PK `(user_id, pref_type, pr_number)`.
  - Indexes: `idx_users_github_id` (unique), `idx_sessions_user_id`, `idx_sessions_expires_at`,
    `idx_user_preferences_user_id`.
  `downgrade()` drops all three tables in reverse order.

## Phase 3 — Backend Auth Dependencies

- [x] **3.1** Add `get_current_user` and `require_user` FastAPI dependencies to
  `src/staged_recipe_dashboard/backend/app.py`. `get_current_user` reads the `session` cookie,
  queries `sessions` joined to `users` where token matches and `expires_at > now(UTC)`, returns
  the `User` ORM object or `None`. `require_user` wraps `get_current_user` and raises HTTP 401
  if the result is `None`. Import `Cookie`, `Depends`, `HTTPException` from fastapi; import
  `Session` and `User` models.

## Phase 4 — Auth Routes

- [x] **4.1** Create `src/staged_recipe_dashboard/backend/routes/auth.py` with an `APIRouter(prefix="/auth")`.
  Implement `GET /auth/login`: generate a random `state` via `secrets.token_hex(16)`, build the
  GitHub authorize URL with `client_id`, `redirect_uri` (`{base_url}/auth/callback`), `scope=read:user`,
  and `state`. Set a `oauth_state` cookie (HttpOnly, SameSite=Lax, Max-Age=300) and return a
  `RedirectResponse` to GitHub. Load `client_id` and `base_url` from `load_config().auth`.

- [x] **4.2** Implement `GET /auth/callback` in `auth.py`. Steps:
  1. Verify `oauth_state` cookie matches `state` query param; raise 400 on mismatch.
  2. POST to `https://github.com/login/oauth/access_token` with `client_id`, `client_secret`,
     `code`. Parse `access_token` from URL-encoded response body.
  3. GET `https://api.github.com/user` with `Authorization: Bearer <token>` and
     `Accept: application/json`. Extract `id`, `login`, `avatar_url`.
  4. Upsert into `users` table: SELECT by `github_id`; if exists update `github_login` and
     `avatar_url`; otherwise INSERT.
  5. INSERT into `sessions`: `token=secrets.token_hex(32)`, `expires_at = now + timedelta(days=30)`.
  6. Build response: `RedirectResponse` to `base_url + "/"`. Set `session` cookie: HttpOnly,
     SameSite=Lax, Path=/, Max-Age=2592000. Clear `oauth_state` cookie (Max-Age=0).
  Use `httpx` (or `urllib.request`) for HTTP calls to GitHub; `httpx` is preferred.

- [x] **4.3** Implement `GET /auth/logout` in `auth.py`. Read `session` cookie. If present,
  delete the matching row from `sessions` (silently skip if not found). Return `RedirectResponse`
  to `/`. Clear the `session` cookie (Max-Age=0, same attributes as set).

## Phase 5 — `/api/me` Endpoint

- [x] **5.1** Create `src/staged_recipe_dashboard/backend/routes/me.py` with an
  `APIRouter(prefix="/api")`. Implement `GET /api/me` using `get_current_user` dependency.
  If authenticated: return `{"authenticated": True, "login": user.github_login, "avatar_url": user.avatar_url}`.
  If not: return `{"authenticated": False, "login": None, "avatar_url": None}`. Always 200.
  Define a `MeResponse` Pydantic model.

## Phase 6 — Preferences Routes

- [x] **6.1** Create `src/staged_recipe_dashboard/backend/routes/prefs.py` with an
  `APIRouter(prefix="/api")`. All endpoints use `require_user` dependency. Implement:
  - `GET /api/prefs`: query all `UserPreference` rows for `user.id`. Return
    `{ "starred": [list of pr_numbers], "ignored": [list of pr_numbers], "notes": { "pr_number": "text" } }`.
    Define a `PrefsResponse` Pydantic model.
  - `PUT /api/prefs/star/{pr_number}`: upsert `pref_type='starred'`, `data=None`.
    Use `INSERT ... ON CONFLICT DO NOTHING`.
  - `DELETE /api/prefs/star/{pr_number}`: delete row where `user_id`, `pref_type='starred'`,
    `pr_number`. 200 even if not found.
  - Same pair for `pref_type='ignored'`.
  - `PUT /api/prefs/note/{pr_number}`: body `{ "text": str }`. Upsert `pref_type='note'`,
    `data={"text": body.text}`. If `text` is empty/whitespace, delete the row instead.
  - `DELETE /api/prefs/note/{pr_number}`: delete `pref_type='note'` row.

- [x] **6.2** Implement `POST /api/prefs/migrate` in `prefs.py`. Accepts a JSON body matching
  the `srdb-preferences` v1/v2/v3 schema. Apply the same migration logic as the frontend
  `migrate()` function (Python version): handle version 1→2→3 upgrade, fall back to empty for
  unknown versions. Insert rows for each starred number (`pref_type='starred'`), ignored number
  (`pref_type='ignored'`), and note entry (`pref_type='note'`, `data={"text": value}`).
  Use `INSERT ... ON CONFLICT DO NOTHING` so it's safe to call multiple times.
  Return `{ "imported": { "starred": N, "ignored": N, "notes": N } }`.

## Phase 7 — Wire New Routers into App

- [x] **7.1** Update `src/staged_recipe_dashboard/backend/app.py` to import and include the three
  new routers: `auth_router` (from `routes/auth.py`), `me_router` (from `routes/me.py`),
  `prefs_router` (from `routes/prefs.py`). Add all three `app.include_router(...)` calls in
  `create_app()`.

## Phase 8 — Update `api.py`: Remove `username` Parameter

- [x] **8.1** Update `src/staged_recipe_dashboard/backend/routes/api.py`:
  - Remove `username: str | None = Query(None)` from `list_prs`, `list_teams`, and any other
    endpoint that accepts it.
  - Add `current_user: User | None = Depends(get_current_user)` to those same endpoints.
  - Replace all uses of `username` with `current_user.github_login if current_user else None`.
  - Import `get_current_user` from `staged_recipe_dashboard.backend.app` and `User` from models.

## Phase 9 — Frontend: `api.js` Additions

- [x] **9.1** Add the following exports to `frontend/src/lib/api.js`:
  `getMe()`, `getPrefs()`, `starPR(n)`, `unstarPR(n)`, `ignorePR(n)`, `unignorePR(n)`,
  `setNote(n, text)`, `deleteNote(n)`, `migrateLocalStorage(blob)`.
  Follow the existing `fetchJSON` pattern. See design.md for exact URL and method mappings.

## Phase 10 — Frontend: Replace `store.js`

- [x] **10.1** Replace `frontend/src/lib/store.js` entirely. The new store:
  - On module load, calls `getMe()` and (if authenticated) `getPrefs()` to initialise state.
  - Exposes `authUser` readable store: `{ authenticated, login, avatar_url }`.
  - Exposes `preferences` writable-like store with the same mutation method names as before
    (`starPR(number)`, `unstarPR(number)`, `ignorePR(number)`, `unignorePR(number)`,
    `setNote(number, text)`), but each method calls the corresponding API function instead of
    writing to localStorage.
  - Exposes `githubUsername` derived store for backward compat in `Overview.svelte` (derives
    `login` from `authUser`).
  - Does NOT write to localStorage.
  - Exports a `refreshPrefs()` function to re-fetch prefs from the server (used after migration).

## Phase 11 — Frontend: Vite Dev Proxy

- [x] **11.1** Update `frontend/vite.config.js` to add `/auth` to the dev proxy target alongside
  the existing `/api` proxy, both pointing to `http://localhost:8000`.

## Phase 12 — Frontend: Nav and Migration Modal

- [x] **12.1** Update `frontend/src/App.svelte`:
  - Import `authUser` from `store.js`.
  - Replace the username-based avatar/dropdown with an `authUser`-reactive block:
    - If `$authUser.authenticated`: show GitHub avatar image in a Bootstrap dropdown.
      Dropdown contains `@{$authUser.login}` text, a divider, a `/profile` link, and a
      "Logout" link pointing to `/auth/logout` (full-page navigation, not `use:link`).
    - If not authenticated: show a "Login with GitHub" button/link pointing to `/auth/login`
      (full-page navigation).
  - Add a `MigrationModal` inline or as a separate component. After `$authUser` first becomes
    `authenticated`, check: does `localStorage.getItem('srdb-preferences')` have non-default
    content (any stars/ignored/notes)? And are server-side prefs all empty? If both true, show
    the migration modal with counts of each category. On "Import": call `migrateLocalStorage`,
    then `refreshPrefs()`, then clear localStorage. On "Start fresh": just clear localStorage.

## Phase 13 — Frontend: `Profile.svelte` Changes

- [x] **13.1** Update `frontend/src/routes/Profile.svelte`:
  - Remove the GitHub username text input section.
  - Remove the JSON export/import section.
  - Add a read-only "GitHub Account" section showing `$authUser.avatar_url` image and
    `@{$authUser.login}` login, plus a "Logout" link/button pointing to `/auth/logout`.
  - Keep the starred PRs count + clear all, ignored PRs count + clear all, and notes management.
  - Update all preference mutations to use the new `preferences` store API (same method names,
    so most of the code is unchanged).

## Phase 14 — Dependency: Add `httpx`

- [x] **14.1** Add `httpx` as a Python dependency for making HTTP calls to GitHub in the auth
  routes. Add it to `pyproject.toml` under `[project] dependencies` and to `pixi.toml` under
  the appropriate environment's dependencies.
