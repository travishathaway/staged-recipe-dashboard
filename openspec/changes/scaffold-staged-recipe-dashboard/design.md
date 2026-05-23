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
# pixi.toml (sketch — not final syntax)

[project]
name = "staged-recipe-dashboard"
channels = ["conda-forge"]
platforms = ["linux-64", "osx-arm64", "osx-64"]

[feature.worker.dependencies]
python = ">=3.11"
perceval = "*"          # from conda-forge
psycopg2 = "*"
httpx = "*"
apscheduler = ">=3"

[feature.backend.dependencies]
python = ">=3.11"
fastapi = "*"
uvicorn = "*"
sqlalchemy = ">=2"
alembic = "*"
psycopg2 = "*"

[feature.frontend.dependencies]
nodejs = ">=20"

[feature.dev.dependencies]
pytest = "*"
ruff = "*"
mypy = "*"

[feature.db.dependencies]
postgresql = "*"        # server binaries: initdb, pg_ctl, psql

[environments]
default  = ["worker", "backend", "db"]
dev      = ["worker", "backend", "db", "dev"]
frontend = ["frontend"]

[tasks]
# Dev convenience tasks
sync     = "srdb sync"
serve    = "srdb serve"
worker   = "srdb worker"
build-ui = "srdb build-ui"
init     = "srdb init"
```

## CLI Design (Typer)

Entry point: `srdb` (installed via pyproject.toml `[project.scripts]`)

```
srdb init            # initdb + create DB + run Alembic migrations
srdb start           # start postgres + worker + server (VPS entrypoint)
srdb stop            # graceful shutdown of all three
srdb status          # show process status

srdb sync            # one-shot GitHub → postgres sync (postgres must be running)
srdb worker          # start APScheduler background worker
srdb serve           # start uvicorn

srdb db start        # start just postgres (pg_ctl start)
srdb db stop         # stop just postgres
srdb db shell        # open psql

srdb build-ui        # npm run build --prefix frontend → bundle into static/
```

`srdb start` is the single VPS deployment command. It starts postgres (via `pg_ctl`), waits for it to be ready, then launches the worker and uvicorn as subprocesses under signal-aware Python supervision.

## Database Schema

```sql
CREATE TABLE pull_requests (
    id          TEXT        PRIMARY KEY,        -- perceval uuid
    number      INTEGER     UNIQUE NOT NULL,
    state       TEXT        NOT NULL,           -- 'open' | 'closed'
    author      TEXT,
    title       TEXT,
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

### Phase 1 — PR sync (every 15 min via APScheduler)

Uses perceval `GitHub` backend (same as `main.py`) but targeting postgres:

1. Upsert into `pull_requests`
2. Delete then re-insert `pr_labels` for each PR (labels are the live state of `data['labels']`)
3. On incremental syncs, only process PRs updated since last run (perceval `from_date`)

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

`srdb init` runs:
1. `initdb -D <data_dir>` (skip if already initialized)
2. Writes a minimal `postgresql.conf` patch (Unix socket dir, port)
3. `pg_ctl start -D <data_dir>`
4. `createdb staged_recipe_dashboard`
5. `alembic upgrade head`

`srdb start` ensures postgres is running before launching Python processes. All connections use the Unix socket (no password, `trust` auth for the local user).

## Conda Package

`recipe/meta.yaml` declares:
- Build: `python setup.py install` (or pip wheel)
- Run deps: `python`, `postgresql`, `perceval`, `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg2`, `httpx`, `apscheduler`, `typer`, `platformdirs`
- The built Svelte SPA (`frontend/dist/`) is copied into `src/staged_recipe_dashboard/static/` at build time and shipped as package data
