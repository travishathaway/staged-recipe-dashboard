# Proposal: Scaffold staged-recipe-dashboard

## What

Build the full project scaffold for **conda-forge staged-recipe dashboard** — a three-component application for helping staged-recipe reviewers see which pull requests need attention and from which review team.

The three components are:

1. **Background worker** — syncs the conda-forge/staged-recipes GitHub repository into a local PostgreSQL database using perceval + a supplementary GitHub Events API client. Runs on a schedule via APScheduler.
2. **Backend API** — a FastAPI server exposing PR queue endpoints, team views, and stats, backed by SQLAlchemy + Alembic.
3. **Frontend dashboard** — a plain Svelte (Vite SPA) with Plotly.js for visualizations, displaying open PRs organized by review team and sorted by how long `review-requested` has been applied.

## Why

conda-forge staged-recipes has hundreds of open PRs at any time. Review teams (python, rust, c-cpp, julia, r, etc.) have no dedicated view showing which PRs are actually waiting for them — the label-based system on GitHub is hard to query and visualize. Reviewers waste time triaging rather than reviewing.

The existing `main.py` proves the data collection approach works but uses SQLite and has no serving layer. This project evolves that into a proper multi-component application.

## Goals

- Provide reviewers with a clear view of what needs their attention, sorted by time waiting (when `review-requested` was applied, not PR creation time).
- Support deep-linking to per-team views (`/team/python`, `/team/rust`, etc.).
- Deploy as a single conda package to a VPS — batteries included (PostgreSQL bundled via conda-forge).
- Reproducible dev environment via pixi with per-component environment isolation.

## Non-goals

- Authentication / access control (dashboard is read-only and public).
- Real-time updates (polling/scheduled sync is sufficient).
- Support for repositories other than conda-forge/staged-recipes in v1.
- Hosting or CI/CD pipeline configuration.

## Constraints

- Dependency manager: **pixi** (conda-forge channel), with separate environments for worker, backend, and frontend.
- PostgreSQL is bundled as a conda dependency (not an external service), managed by the CLI. `srdb db start` handles full bootstrap (initdb → start → createdb) automatically.
- Package must be publishable to conda-forge as a single conda package.
- "Longest waiting" is defined by when the `review-requested` label was first applied (from GitHub Events API), not PR `created_at`.
- Sync strategy: one full sync on first run (`srdb sync`), then incremental every minute via the scheduler. State tracked in `last_sync.txt` with a 15-minute overlap buffer.
- A `config.toml.example` is provided at the project root documenting all configuration options.
