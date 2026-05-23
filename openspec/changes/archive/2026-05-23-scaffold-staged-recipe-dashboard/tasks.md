# Tasks: Scaffold staged-recipe-dashboard

## Phase 1 — Project Foundation

- [x] **1.1** Create `pixi.toml` with multi-environment configuration (worker, backend, frontend, dev, db features; default and dev environments)
- [x] **1.2** Create `pyproject.toml` with package metadata, entry point `srdb = staged_recipe_dashboard.cli:app`, and build system (hatchling or flit)
- [x] **1.3** Create the Python package skeleton: `src/staged_recipe_dashboard/__init__.py`, `worker/__init__.py`, `backend/__init__.py`, `db/__init__.py`, `routes/__init__.py`
- [x] **1.4** Create `src/staged_recipe_dashboard/config.py` — loads `~/.config/staged-recipe-dashboard/config.toml` using `platformdirs`; provides defaults for data_dir, db port, sync interval, github tokens, server host/port
- [x] **1.5** Initialize Alembic: `alembic init src/staged_recipe_dashboard/db/migrations` and configure `alembic.ini` + `env.py` to read DB URL from the app config

## Phase 2 — Database Schema

- [x] **2.1** Create `src/staged_recipe_dashboard/db/schema.py` with raw DDL for `pull_requests`, `pr_labels`, `pr_label_history` tables and indexes (matches design.md)
- [x] **2.2** Create first Alembic migration (`alembic revision --autogenerate -m "initial schema"`) that creates all three tables
- [x] **2.3** Create `src/staged_recipe_dashboard/backend/models.py` — SQLAlchemy 2.x ORM models for the three tables, mapped to the schema

## Phase 3 — CLI Skeleton

- [x] **3.1** Create `src/staged_recipe_dashboard/cli.py` with Typer app and all top-level commands as stubs: `init`, `start`, `stop`, `status`, `sync`, `worker`, `serve`, `build-ui`
- [x] **3.2** Add `db` subgroup with `start`, `stop`, `shell` subcommands (Typer nested app)
- [x] **3.3** Implement `srdb db start` and `srdb db stop` using `subprocess` + `pg_ctl`; detect if postgres is already running via `pg_ctl status`
- [x] **3.4** Implement `srdb init`: run `initdb` (skip if data dir exists), patch `postgresql.conf`, call `srdb db start`, create database if missing, run `alembic upgrade head`
- [x] **3.5** Implement `srdb db shell`: exec `psql` with correct socket/port args
- [x] **3.6** Implement `srdb build-ui`: run `npm run build` inside `frontend/`, copy `frontend/dist/` to `src/staged_recipe_dashboard/static/`

## Phase 4 — Background Worker

- [x] **4.1** Create `src/staged_recipe_dashboard/worker/sync.py` — adapt `main.py` for postgres: replace `sqlite3` with `psycopg2`/SQLAlchemy, upsert `pull_requests`, rebuild `pr_labels` from `data['labels']` on each upsert
- [x] **4.2** Create `src/staged_recipe_dashboard/worker/events.py` — `httpx`-based client that calls `GET /repos/conda-forge/staged-recipes/issues/{n}/events`, finds first `labeled` event for `review-requested`, inserts into `pr_label_history` with `ON CONFLICT DO NOTHING`
- [x] **4.3** Create `src/staged_recipe_dashboard/worker/scheduler.py` — APScheduler `BlockingScheduler` with two jobs: `sync_prs` every 15 min, `sync_label_history` every 60 min
- [x] **4.4** Wire `srdb sync` CLI command to call `sync.run_once()` (single pass, no scheduler)
- [x] **4.5** Wire `srdb worker` CLI command to start APScheduler (blocking, handles SIGTERM gracefully)

## Phase 5 — FastAPI Backend

- [x] **5.1** Create `src/staged_recipe_dashboard/backend/app.py` — FastAPI app factory; include API router; add static file mount for `static/` directory; add catch-all route returning `index.html` for SPA
- [x] **5.2** Create `src/staged_recipe_dashboard/backend/routes/api.py` with four endpoints: `GET /api/prs`, `GET /api/teams`, `GET /api/stats`, `GET /api/prs/{number}`
- [x] **5.3** Implement `GET /api/teams` query: distinct team labels (excluding status labels) with `needs_review` and `blocked` counts
- [x] **5.4** Implement `GET /api/prs` query with `needs_review` filter (state=open + review-requested label + no "Awaiting author contribution" label) and optional `team` filter; join `pr_label_history` for `waiting_since`
- [x] **5.5** Implement `GET /api/stats` aggregate query
- [x] **5.6** Implement `GET /api/prs/{number}` detail endpoint including label history
- [x] **5.7** Wire `srdb serve` CLI command to launch uvicorn programmatically with host/port from config

## Phase 6 — Frontend Scaffold

- [x] **6.1** Initialize Svelte + Vite project inside `frontend/`: `npm create vite@latest frontend -- --template svelte`; add `svelte-routing` (or `page.js`) for client-side routing; add `plotly.js-dist-min` dependency
- [x] **6.2** Configure `vite.config.js` with a dev proxy so `/api` requests forward to `localhost:8000` during development
- [x] **6.3** Create `frontend/src/lib/api.js` with typed fetch helpers for all four API endpoints
- [x] **6.4** Create `frontend/src/App.svelte` with route declarations: `/` → Overview, `/team/:name` → Team
- [x] **6.5** Create `frontend/src/routes/Overview.svelte`: fetch `/api/teams` and `/api/prs?limit=10` per team; display a ranked list of longest-waiting PRs across all teams; include a Plotly bar chart of `needs_review` count per team
- [x] **6.6** Create `frontend/src/routes/Team.svelte`: fetch `/api/prs?team={name}`; display full queue sorted by `waiting_since`; show PR title, author, labels, and a human-readable "waiting N days" duration
- [x] **6.7** Create `frontend/src/lib/components/PRCard.svelte` — reusable PR card component used by both Overview and Team views
- [x] **6.8** Create `frontend/src/lib/components/WaitingBar.svelte` — thin Plotly.js wrapper component for the team bar chart

## Phase 7 — Process Supervision & `srdb start`

- [x] **7.1** Implement `srdb start` in `cli.py`: start postgres (if not running), then launch worker and uvicorn as `subprocess.Popen` children; install `SIGTERM`/`SIGINT` handlers that stop all three in reverse order
- [x] **7.2** Implement `srdb stop`: send SIGTERM to running worker and uvicorn PIDs (stored in `platformdirs.user_runtime_dir` as `.pid` files); run `pg_ctl stop`
- [x] **7.3** Implement `srdb status`: check each PID file, verify the process is alive, report running/stopped for each component

## Phase 8 — Conda Recipe

- [x] **8.1** Create `recipe/meta.yaml` with package name, version from `pyproject.toml`, source from local path, build script, and full runtime dependency list (python, postgresql, perceval, fastapi, uvicorn, sqlalchemy, alembic, psycopg2, httpx, apscheduler, typer, platformdirs)
- [x] **8.2** Add a build script (`recipe/build.sh`) that installs the Python package and copies pre-built frontend assets into the package's `static/` directory; document that `srdb build-ui` must be run before `conda build`

## Phase 9 — Developer Experience

- [x] **9.1** Add pixi tasks for common dev workflows: `pixi run init`, `pixi run sync`, `pixi run serve`, `pixi run worker`, `pixi run build-ui`, `pixi run dev` (starts all components)
- [x] **9.2** Add `ruff.toml` (or `[tool.ruff]` in `pyproject.toml`) with basic linting config
- [x] **9.3** Create `tests/` directory with a placeholder `test_schema.py` that verifies table creation against a test postgres instance
- [x] **9.4** Update `CLAUDE.md` with project overview, setup steps (`srdb init`, `pixi install`), component descriptions, and development workflow
