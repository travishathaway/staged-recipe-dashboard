# Design: Scaffold staged-recipe-dashboard

## Project Structure

```
staged-recipe-dashboard/
├── pixi.toml                          # multi-environment workspace
├── pixi.lock
├── pyproject.toml                     # Python package definition
├── src/
│   └── staged_recipe_dashboard/
│       ├── __init__.py
│       ├── cli.py                     # Typer CLI ("srdb" entry point)
│       ├── config.py                  # config.toml loader (platformdirs)
│       ├── worker/
│       │   ├── __init__.py
│       │   ├── sync.py                # perceval → postgres (adapted from main.py)
│       │   ├── events.py              # httpx → GitHub Events API → pr_label_history
│       │   └── scheduler.py           # APScheduler: sync every 15m, events every 60m
│       ├── backend/
│       │   ├── __init__.py
│       │   ├── app.py                 # FastAPI app factory
│       │   ├── models.py              # SQLAlchemy ORM models
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── api.py             # /api/prs, /api/teams, /api/stats
│       │       └── pages.py           # serves built Svelte SPA (catch-all)
│       └── db/
│           ├── __init__.py
│           ├── schema.py              # raw DDL (pull_requests, pr_labels, pr_label_history)
│           └── migrations/            # Alembic env + versions
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.svelte                 # router root
│       ├── lib/
│       │   ├── api.js                 # fetch helpers
│       │   └── components/
│       │       ├── PRCard.svelte
│       │       └── WaitingBar.svelte  # Plotly.js wrapper
│       └── routes/
│           ├── Overview.svelte        # / — all teams, longest waiting
│           └── Team.svelte            # /team/[name]
└── recipe/
    └── meta.yaml                      # conda recipe
```

## Pixi Environments

```toml
[workspace]
name = "staged-recipe-dashboard"
channels = ["conda-forge"]
platforms = ["linux-64", "linux-aarch64", "osx-arm64"]

[dependencies]
python = ">=3.11"

[feature.worker.dependencies]
psycopg2 = ">=2.9"
httpx = ">=0.27"
apscheduler = ">=3.10"

[feature.worker.pypi-dependencies]
perceval = ">=0.20"          # not on conda-forge

[feature.backend.dependencies]
fastapi = ">=0.110"
uvicorn = ">=0.29"
sqlalchemy = ">=2.0"
alembic = ">=1.13"
psycopg2 = ">=2.9"
typer = ">=0.12"
platformdirs = ">=4.2"

[feature.db.dependencies]
postgresql = ">=16"          # server binaries: initdb, pg_ctl, psql, createdb

[feature.frontend.dependencies]
nodejs = ">=20"

[feature.dev.dependencies]
pytest = ">=8"
ruff = ">=0.4"
mypy = ">=1.10"

[feature.app.pypi-dependencies]
staged-recipe-dashboard = { path = ".", editable = true }

[environments]
default  = { features = ["worker", "backend", "db", "app"], solve-group = "default" }
dev      = { features = ["worker", "backend", "db", "dev", "app"], solve-group = "default" }
frontend = { features = ["frontend"] }

[tasks]
init    = "srdb init"
sync    = "srdb sync"
serve   = "srdb serve"
worker  = "srdb worker"
start   = "srdb start"

[feature.frontend.tasks]
build-ui = { cmd = "npm run build", cwd = "frontend" }
```

## CLI Design (Typer)

Entry point: `srdb` (installed via pyproject.toml `[project.scripts]`)

```
srdb init                          # db start (with auto-initdb) + alembic upgrade head
srdb start                         # postgres + worker + server (VPS entrypoint)
srdb stop                          # graceful shutdown of all three
srdb status                        # show process status

srdb sync [--from-date YYYY-MM-DD] # one-shot sync; uses last_sync.txt if no date given
srdb worker                        # start APScheduler background worker
srdb serve                         # start uvicorn

srdb db start                      # initdb (if needed) + pg_ctl start + createdb (if needed)
srdb db stop                       # pg_ctl stop
srdb db shell                      # open psql

srdb build-ui                      # npm run build → copy dist/ to package static/
```

`srdb db start` is self-contained: it runs `initdb` if the data directory doesn't exist, patches `postgresql.conf` to use the runtime dir for the Unix socket, starts postgres, then creates the application database if it doesn't exist. All other commands that need postgres running call `db_start` internally.

`srdb start` is the single VPS deployment command. It ensures postgres is running, then launches the worker and uvicorn as signal-aware subprocesses.

## Database Schema

```sql
CREATE TABLE pull_requests (
    id          TEXT        PRIMARY KEY,        -- perceval uuid
    number      INTEGER     UNIQUE NOT NULL,
    state       TEXT        NOT NULL,           -- 'open' | 'closed'
    author      TEXT,
    title       TEXT,
    html_url    TEXT,                           -- GitHub PR URL (extracted for fast access)
    created_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ,
    closed_at   TIMESTAMPTZ,
    merged_at   TIMESTAMPTZ,
    data        JSONB       NOT NULL            -- full perceval item
);

-- Current labels on each PR (rebuilt on each sync from data blob)
CREATE TABLE pr_labels (
    pr_number   INTEGER REFERENCES pull_requests(number) ON DELETE CASCADE,
    label_name  TEXT    NOT NULL,
    PRIMARY KEY (pr_number, label_name)
);

-- When each label was first applied (from GitHub Events API)
-- Set once, never updated — used for "waiting since" calculation
CREATE TABLE pr_label_history (
    pr_number   INTEGER REFERENCES pull_requests(number) ON DELETE CASCADE,
    label_name  TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (pr_number, label_name)
);

CREATE INDEX idx_pr_state      ON pull_requests (state);
CREATE INDEX idx_pr_author     ON pull_requests (author);
CREATE INDEX idx_pr_created_at ON pull_requests (created_at);
CREATE INDEX idx_label_name    ON pr_labels (label_name);
CREATE INDEX idx_history_label ON pr_label_history (label_name);
```

## Sync Design

### Phase 1 — PR sync (every 1 min via APScheduler)

Uses perceval `GitHub` backend (same as `main.py`) but targeting postgres.

**Incremental sync with state tracking:**

`run_once` reads `RUNTIME_DIR/last_sync.txt` to determine `from_date`:

- **No state file** (first run): full sync from the beginning of time. Writes `last_sync.txt` on success.
- **State file exists**: uses `last_sync_time - 15 min` as `from_date` (overlap buffer to catch PRs whose `updated_at` lagged behind the previous sync's clock).
- **`--from-date` flag** (manual override via CLI): bypasses state file, uses the given date. Still writes `last_sync.txt` on success.

For each PR processed:
1. Upsert into `pull_requests`
2. Delete then re-insert `pr_labels` (reflects current label state from `data['labels']`)

**Production workflow:**
```bash
srdb sync          # full sync (first run, takes several minutes)
srdb worker        # scheduler takes over; each tick is a fast incremental sync
```

### Phase 2 — Label history sync (every 60 min)

Uses `httpx` to call `GET /repos/conda-forge/staged-recipes/issues/{n}/events`:

1. Find all open PRs where `pr_label_history` has no row for `review-requested`
2. For each, fetch events and find the first `"labeled"` event where `label.name == "review-requested"`
3. Insert into `pr_label_history` (INSERT … ON CONFLICT DO NOTHING)

Rate limit: ~400–600 open PRs × 1 call each = fits within one rate-limit window on first run. Subsequent runs are near-zero (only new PRs are missing history).

## "Needs Review" Query Logic

A PR needs review when:
- `state = 'open'`
- Has a `pr_labels` row for `'review-requested'`
- Does NOT have a `pr_labels` row for `'Awaiting author contribution'`

Team assignment: additional `pr_labels` rows matching known team names (`python`, `rust`, `c-cpp`, `julia`, `r`, etc.). These are discoverable dynamically by querying distinct label names excluding status labels.

"Waiting since" = `pr_label_history.applied_at` for `label_name = 'review-requested'`.

## Frontend Routes

```
/                    → Overview: all teams, top N longest-waiting PRs per team
/team/:name          → Team view: full queue for one team, sorted by waiting_since
```

Deep linking via Svelte's built-in client-side router (svelte-routing or page.js). FastAPI serves the SPA via a catch-all route that returns `index.html` for any non-`/api/` path.

## API Endpoints (FastAPI)

```
GET /api/prs
  ?team=python       filter by team label
  ?status=needs_review (default) | blocked | all
  ?limit=50&offset=0
  → [{number, title, author, created_at, waiting_since, labels, html_url}]

GET /api/teams
  → [{name, needs_review_count, blocked_count}]

GET /api/stats
  → {total_open, needs_review, blocked, by_team: [...]}

GET /api/prs/{number}
  → full PR detail including label history
```

## PostgreSQL Process Management

Postgres is a conda dependency (`postgresql` from conda-forge). The data directory defaults to `platformdirs.user_data_dir("staged-recipe-dashboard") / "pgdata"` and is configurable via `config.toml`.

`srdb db start` is the self-contained postgres bootstrap command:
1. `initdb -D <data_dir> --auth=trust` — skipped if `PG_VERSION` already exists
2. Appends `unix_socket_directories` and `port` to `postgresql.conf` — only on first init
3. `pg_ctl start -D <data_dir> -l <runtime_dir>/postgres.log`
4. Creates the application database via `createdb` — skipped if it already exists

`srdb init` calls `db_start` then runs `alembic upgrade head`.

`srdb start` calls `db_start` before launching Python subprocesses. All connections use the Unix socket (`trust` auth for the local user — no password needed).

Logging: postgres logs to `RUNTIME_DIR/postgres.log`. Python processes (worker, server) log to stderr by default, or to a file configured via `[logging] file` in `config.toml`.

## Configuration

Config is loaded from `config.toml`. Search order:
1. `./config.toml` — current working directory (useful for dev)
2. `<platform config dir>/staged-recipe-dashboard/config.toml`

A `config.toml.example` is included at the project root documenting all keys.

```toml
[database]
data_dir   = "~/.local/share/staged-recipe-dashboard/pgdata"
socket_dir = "/run/user/1000/staged-recipe-dashboard"
port       = 5432
name       = "staged_recipe_dashboard"

[worker]
github_tokens          = ["ghp_..."]
sync_interval_minutes  = 1    # incremental syncs are fast
events_interval_minutes = 60

[server]
host = "0.0.0.0"
port = 8000

[logging]
# file = "/var/log/staged-recipe-dashboard/app.log"  # omit to use stderr
level = "INFO"
```

Logging is configured once at startup by `_configure_logging(cfg)` in `cli.py`, called by `sync`, `worker`, `serve`, and `start`. When `logging.file` is set, a `FileHandler` is created (parent directories are created if needed); otherwise a `StreamHandler` to stderr is used. Uvicorn's log config is disabled so its records flow through the same handler.

## Conda Package

`recipe/meta.yaml` declares:
- Build: `python setup.py install` (or pip wheel)
- Run deps: `python`, `postgresql`, `perceval`, `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg2`, `httpx`, `apscheduler`, `typer`, `platformdirs`
- The built Svelte SPA (`frontend/dist/`) is copied into `src/staged_recipe_dashboard/static/` at build time and shipped as package data
