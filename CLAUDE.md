# staged-recipe-dashboard

Dashboard for conda-forge staged-recipe PR reviewers. Shows which pull requests need review, organized by language team (python, rust, c-cpp, julia, r, etc.), sorted by how long `review-requested` has been applied.

## Architecture

Three components, all managed via the `srdb` CLI:

```
worker/     Background sync: perceval + GitHub Events API → PostgreSQL
backend/    FastAPI REST API (SQLAlchemy + Alembic)
frontend/   Svelte SPA (Vite + Plotly.js for charts)
```

PostgreSQL is **bundled** (from conda-forge) — no external database required. The `srdb` CLI manages the postgres process via `pg_ctl`.

## First-Time Setup

```bash
# Install environments (Python + Node toolchains)
pixi install

# Build the frontend assets
pixi run -e frontend build-ui

# Initialize postgres + DB + run migrations
pixi run init            # runs: srdb init

# Add GitHub token(s) to config
mkdir -p ~/.config/staged-recipe-dashboard
cat > ~/.config/staged-recipe-dashboard/config.toml <<EOF
[worker]
github_tokens = ["ghp_YOUR_TOKEN_HERE"]
EOF
```

## Development Workflow

```bash
# Start everything at once
pixi run start           # postgres + worker + server

# Or run components separately (separate terminals)
pixi run -e default srdb db start
pixi run worker          # APScheduler (15-min PR sync, 60-min label history)
pixi run serve           # uvicorn on http://localhost:8000

# Frontend dev server (proxies /api to localhost:8000)
pixi run -e frontend npm run dev --prefix frontend

# One-shot sync (useful for testing)
pixi run sync
```

## Key Files

| File | Purpose |
|------|---------|
| `src/staged_recipe_dashboard/cli.py` | `srdb` CLI — all management commands |
| `src/staged_recipe_dashboard/config.py` | Config loader; defaults + `~/.config/.../config.toml` |
| `src/staged_recipe_dashboard/worker/sync.py` | perceval → postgres PR sync |
| `src/staged_recipe_dashboard/worker/events.py` | GitHub Events API → `pr_label_history` |
| `src/staged_recipe_dashboard/backend/routes/api.py` | REST endpoints |
| `frontend/src/routes/Overview.svelte` | All-teams overview page |
| `frontend/src/routes/Team.svelte` | Per-team PR queue (deep-linkable) |
| `recipe/meta.yaml` | conda recipe (run `srdb build-ui` before `conda build`) |

## "Needs Review" Logic

A PR appears in the queue when:
1. `state = 'open'`
2. Has the `review-requested` label (applied by bot when `@conda-forge/help-<team>` is mentioned)
3. Does **not** have the `Awaiting author contribution` label

"Waiting since" = when `review-requested` was first applied (from `pr_label_history`, sourced from GitHub Events API). This is what the queue sorts by.

## Database Schema

Three tables in PostgreSQL:
- `pull_requests` — one row per PR (perceval uuid PK, full JSONB blob + extracted columns)
- `pr_labels` — current labels on each open PR (rebuilt on every sync)
- `pr_label_history` — when each label was first applied (set once, never updated)

## Running Tests

```bash
# Requires srdb init to have been run first
pixi run -e dev pytest tests/
```
