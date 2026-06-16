# Design: GitHub OAuth Authentication

## Architecture Overview

```
Browser                        Backend (FastAPI)              GitHub API
───────────────────────        ───────────────────────        ──────────
Session cookie (HttpOnly) ──→  Read session → user_id
                               Look up preferences
                               Serve personalized data ──────────────────
                                                          (login only)
                                                          GET /user
                                                          ← login, id,
                                                            avatar_url
```

The backend gains three new route modules:
- `backend/routes/auth.py` — OAuth login/callback/logout
- `backend/routes/prefs.py` — user preferences CRUD
- `backend/routes/me.py` — current user identity endpoint

The existing `api.py` is modified to:
- Remove `username` query parameter from all endpoints
- Derive the current user's GitHub login from the session (when present)

Three new DB tables are added via a single Alembic migration `004`:
- `users` — GitHub identity
- `sessions` — session tokens
- `user_preferences` — starred/ignored/notes per user per PR

The frontend:
- Replaces `store.js` localStorage mutations with API calls
- Derives identity from `GET /api/me` on load
- Adds login/logout UI in the nav
- Adds a first-login migration prompt

---

## Configuration

Add `[auth]` section to `config.toml`. Extend `config.py` with `AuthConfig`:

```python
@dataclass
class AuthConfig:
    github_client_id: str = ""
    github_client_secret: str = ""
    # Scheme+host used to build the redirect_uri sent to GitHub.
    # E.g. "https://srdb.example.com" for production, "http://localhost:5173" for dev.
    base_url: str = "http://localhost:5173"

    @classmethod
    def from_dict(cls, d: dict) -> "AuthConfig":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)
```

`AppConfig` gains `auth: AuthConfig = field(default_factory=AuthConfig)`.

`load_config()` reads `raw.get("auth", {})` and passes to `AuthConfig.from_dict`.

Example `config.toml` additions:

```toml
[auth]
github_client_id = "Iv1.abc123"
github_client_secret = "secret"
base_url = "https://srdb.example.com"
```

---

## Database: New Models (`models.py`)

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preferences: Mapped[list["UserPreference"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String, primary_key=True)   # 32-byte random hex
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    pref_type: Mapped[str] = mapped_column(String, primary_key=True)   # 'starred' | 'ignored' | 'note'
    pr_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict | None] = mapped_column(JSONB)                   # null for starred/ignored; {"text": "..."} for note

    user: Mapped["User"] = relationship(back_populates="preferences")
```

---

## Database: Migration 004

New file: `src/staged_recipe_dashboard/db/migrations/versions/004_add_auth_tables.py`

```
revision: "004"
down_revision: "003"
```

Creates:
- `users` table with `idx_users_github_id` unique index
- `sessions` table with `idx_sessions_user_id` index, `idx_sessions_expires_at` index
- `user_preferences` table with `idx_user_preferences_user_id` index

---

## Backend: Auth Routes (`backend/routes/auth.py`)

```
GET  /auth/login     → redirect to GitHub authorize URL
GET  /auth/callback  → exchange code, upsert user, create session, set cookie
GET  /auth/logout    → delete session row, clear cookie
```

### `/auth/login`

Generates a random `state` token (stored in a short-lived cookie `oauth_state`), then
returns a 302 redirect to:

```
https://github.com/login/oauth/authorize
  ?client_id=<client_id>
  &redirect_uri=<base_url>/auth/callback
  &scope=read:user
  &state=<state>
```

### `/auth/callback`

1. Verify `state` cookie matches the `state` query param. Clear `oauth_state` cookie.
2. `POST https://github.com/login/oauth/access_token` with `code`, `client_id`, `client_secret`.
   Parse `access_token` from response.
3. `GET https://api.github.com/user` with `Authorization: Bearer <access_token>`.
   Extract `id` (github_id), `login`, `avatar_url`.
4. Upsert into `users`: if `github_id` exists update `github_login` and `avatar_url`,
   otherwise insert.
5. Create a `sessions` row: token = `secrets.token_hex(32)`, expires in 30 days.
6. Set `Set-Cookie: session=<token>; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000`.
7. Redirect to `<base_url>/` (or a `next` query param if provided).

### `/auth/logout`

Read `session` cookie. Delete matching row from `sessions`. Clear the cookie.
Redirect to `/`.

---

## Backend: Auth Dependency (`backend/app.py`)

Add two FastAPI dependencies:

```python
def get_current_user(
    session_token: str | None = Cookie(default=None, alias="session"),
    db: Session = Depends(get_db),
) -> User | None:
    """Returns the authenticated User, or None if not logged in / session expired."""
    if not session_token:
        return None
    now = datetime.now(timezone.utc)
    session = db.execute(
        select(Session).where(
            Session.token == session_token,
            Session.expires_at > now,
        ).join(Session.user)
    ).scalar_one_or_none()
    return session.user if session else None


def require_user(user: User | None = Depends(get_current_user)) -> User:
    """Like get_current_user but raises 401 if not authenticated."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
```

---

## Backend: `/api/me` Endpoint

New file: `backend/routes/me.py`

```
GET /api/me
```

- If `get_current_user` returns a user: `{ "login": "...", "avatar_url": "...", "authenticated": true }`
- If not authenticated: `{ "authenticated": false }`

Always returns 200. The frontend uses `authenticated: false` to show the login button.

---

## Backend: Preferences Routes (`backend/routes/prefs.py`)

All endpoints require `require_user`.

```
GET    /api/prefs              → all prefs for current user
PUT    /api/prefs/star/{pr_number}
DELETE /api/prefs/star/{pr_number}
PUT    /api/prefs/ignore/{pr_number}
DELETE /api/prefs/ignore/{pr_number}
PUT    /api/prefs/note/{pr_number}    body: { "text": "..." }
DELETE /api/prefs/note/{pr_number}
POST   /api/prefs/migrate             body: localStorage blob (raw srdb-preferences JSON)
```

### `GET /api/prefs`

Returns:
```json
{
  "starred":  [1234, 5678],
  "ignored":  [9999],
  "notes":    { "1234": "follow up with author", "5678": "needs rebase" }
}
```

### `PUT /api/prefs/star/{pr_number}` / `DELETE /api/prefs/star/{pr_number}`

Upsert / delete a `user_preferences` row with `pref_type='starred'`.

### `PUT /api/prefs/ignore/{pr_number}` / `DELETE /api/prefs/ignore/{pr_number}`

Same pattern for `pref_type='ignored'`.

### `PUT /api/prefs/note/{pr_number}`

Upsert `pref_type='note'`, `data={"text": body.text}`.

### `DELETE /api/prefs/note/{pr_number}`

Delete `pref_type='note'` row.

### `POST /api/prefs/migrate`

Accepts the raw `srdb-preferences` v1/v2/v3 JSON blob. Applies the same migration logic as the
existing frontend `migrate()` function (Python re-implementation). Writes rows to `user_preferences`
for:
- Each key in `starred.prs` → `pref_type='starred'`
- Each key in `ignored.prs` → `pref_type='ignored'`
- Each key in `notes.prs` → `pref_type='note'` with `data={"text": value}`

Full PR objects in `starred.prs` are reduced to just the number (the key). Does not overwrite
existing preferences (idempotent — uses INSERT ... ON CONFLICT DO NOTHING).

Returns `{ "imported": { "starred": N, "ignored": N, "notes": N } }`.

---

## Backend: `api.py` Changes

### Remove `username` parameter

Remove `username: str | None = Query(None)` from `list_prs`, `list_teams`, and any other
endpoint that accepts it. Replace usage with `current_user = Depends(get_current_user)` and
use `current_user.github_login if current_user else None` wherever the username was used.

This is a clean break (Option A from the exploration). Unauthenticated users get no role
annotations. The `roles` field on `PRResponse` will be an empty list for unauthenticated
requests.

### Wire auth router

In `app.py`, include the new routers:

```python
from staged_recipe_dashboard.backend.routes.auth import router as auth_router
from staged_recipe_dashboard.backend.routes.me import router as me_router
from staged_recipe_dashboard.backend.routes.prefs import router as prefs_router

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(prefs_router)
```

---

## Frontend: New `api.js` Additions

```js
// Identity
export const getMe = () => fetchJSON('/api/me')

// Preferences
export const getPrefs = () => fetchJSON('/api/prefs')
export const starPR = (n) => fetchJSON(`/api/prefs/star/${n}`, { method: 'PUT' })
export const unstarPR = (n) => fetchJSON(`/api/prefs/star/${n}`, { method: 'DELETE' })
export const ignorePR = (n) => fetchJSON(`/api/prefs/ignore/${n}`, { method: 'PUT' })
export const unignorePR = (n) => fetchJSON(`/api/prefs/ignore/${n}`, { method: 'DELETE' })
export const setNote = (n, text) =>
  fetchJSON(`/api/prefs/note/${n}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ text }) })
export const deleteNote = (n) => fetchJSON(`/api/prefs/note/${n}`, { method: 'DELETE' })
export const migrateLocalStorage = (blob) =>
  fetchJSON('/api/prefs/migrate', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(blob) })
```

---

## Frontend: `store.js` Replacement

`store.js` is replaced entirely. The new version:

1. Calls `GET /api/me` on initialisation to determine auth state and identity.
2. If authenticated, calls `GET /api/prefs` to load server-side preferences.
3. Exposes the same Svelte store interface, but mutations call the API instead of writing
   to localStorage.
4. Exposes an `authUser` store: `{ authenticated, login, avatar_url }`.

```
store.js public API (unchanged contract):
  preferences  — writable: { starred, ignored, notes }
  authUser     — readable: { authenticated, login, avatar_url } | null

  preferences.starPR(number)
  preferences.unstarPR(number)
  preferences.ignorePR(number)
  preferences.unignorePR(number)
  preferences.setNote(number, text)
  preferences.clearOrphanedNotes()   ← no-op (server cleans up naturally)

  [removed]:
  preferences.setUsername()          ← username now from session
  preferences.exportJSON()           ← removed (or kept as download of server prefs)
  preferences.importJSON()           ← replaced by migrateLocalStorage() flow
  preferences.reset()                ← replaced by logout
```

No data is written to localStorage after this change.

---

## Frontend: First-Login Migration Prompt

In `App.svelte` (or a dedicated `MigrationModal.svelte` component), after `authUser` becomes
authenticated for the first time:

1. Check if `localStorage.getItem('srdb-preferences')` exists and has non-default content
   (any starred/ignored/notes keys, or a username).
2. If so, and if the server-side prefs are empty (all three arrays empty), show a one-time modal:

```
┌─────────────────────────────────────────────────────────┐
│  Import your local preferences?                         │
│                                                         │
│  We found preferences stored on this device:            │
│  • 12 starred PRs                                       │
│  • 3 notes                                              │
│  • 1 ignored PR                                         │
│                                                         │
│  Import them to your account so they sync everywhere?   │
│                                                         │
│  [Import]          [Start fresh]                        │
└─────────────────────────────────────────────────────────┘
```

3. On **Import**: call `migrateLocalStorage(blob)`, reload prefs from server, clear localStorage.
4. On **Start fresh**: just clear localStorage, dismiss modal.

The prompt is suppressed on subsequent logins by checking if server-side prefs are non-empty
(meaning migration has already happened).

---

## Frontend: Nav Changes

`App.svelte` nav changes:

- Remove the manual GitHub username input and avatar display tied to `$preferences.profile.githubUsername`.
- Replace with `$authUser`-based display:
  - If `$authUser.authenticated`:
    - Show `<img src="{$authUser.avatar_url}" ...>` in a Bootstrap dropdown.
    - Dropdown: `@{$authUser.login}` display + divider + `/profile` link + "Logout" link
      (`href="/auth/logout"` — full page navigation, not client-side).
  - If not authenticated:
    - Show a "Login with GitHub" button (`href="/auth/login"` — full page navigation).

---

## Frontend: `Profile.svelte` Changes

- Remove the GitHub username input section (username now comes from session).
- Remove the export/import JSON section (replaced by the one-time migration flow).
- Keep: starred PRs count + clear all action, ignored PRs count + clear all, notes management.
- Add: GitHub account display (avatar + login, read-only), logout button.

---

## Frontend: Vite Dev Proxy

Add `/auth` to the Vite dev proxy config alongside the existing `/api` proxy, so OAuth
redirects work during local development:

```js
// vite.config.js
proxy: {
  '/api': 'http://localhost:8000',
  '/auth': 'http://localhost:8000',
}
```

---

## File Changelist

| File | Change |
|------|--------|
| `src/staged_recipe_dashboard/config.py` | Add `AuthConfig` dataclass, wire into `AppConfig` and `load_config()` |
| `src/staged_recipe_dashboard/backend/models.py` | Add `User`, `Session`, `UserPreference` ORM models |
| `src/staged_recipe_dashboard/db/migrations/versions/004_add_auth_tables.py` | **New** — create users, sessions, user_preferences tables |
| `src/staged_recipe_dashboard/backend/app.py` | Add `get_current_user` + `require_user` deps; include new routers |
| `src/staged_recipe_dashboard/backend/routes/auth.py` | **New** — `/auth/login`, `/auth/callback`, `/auth/logout` |
| `src/staged_recipe_dashboard/backend/routes/me.py` | **New** — `GET /api/me` |
| `src/staged_recipe_dashboard/backend/routes/prefs.py` | **New** — preferences CRUD + migrate |
| `src/staged_recipe_dashboard/backend/routes/api.py` | Remove `username` param; replace with session-derived identity |
| `frontend/src/lib/store.js` | Replace localStorage store with API-backed store + `authUser` |
| `frontend/src/lib/api.js` | Add `getMe`, `getPrefs`, `starPR`, `unstarPR`, `ignorePR`, `unignorePR`, `setNote`, `deleteNote`, `migrateLocalStorage` |
| `frontend/src/App.svelte` | Replace username-based nav with `authUser` nav; add migration modal |
| `frontend/src/routes/Profile.svelte` | Remove username input + export/import; add account display + logout |
| `frontend/vite.config.js` | Add `/auth` to dev proxy |
