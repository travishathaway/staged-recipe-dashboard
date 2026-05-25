# Proposal: VPS Deployment

## What

Add production deployment infrastructure to the repository so the dashboard can be deployed to a
generic Linux VPS. The deployment stack uses rattler-build to produce a `noarch` conda package,
pixi-pack to produce a self-extracting environment installer, and Ansible to provision and configure
the server.

A dedicated `deploy/` directory contains the full Ansible playbook and role. A `scripts/` directory
contains `build.sh` (builds the artifact) and `update.sh` (builds and deploys). Caddy serves as the
reverse proxy, handles HTTPS automatically via Let's Encrypt, and serves frontend static files
directly. FastAPI handles only API requests.

## Why

The app currently runs only in development mode (editable pixi install). To be useful to
conda-forge reviewers it needs to be accessible at a stable URL. The chosen toolchain — rattler-build
+ pixi-pack + Ansible — keeps the deployment self-contained and reproducible without requiring conda
or pixi to be installed on the VPS.

## Goals

- Build the Python package as a `noarch` conda artifact using rattler-build, replacing the editable
  pypi install for production.
- Produce a self-extracting `srdb-install.sh` script via pixi-pack that installs the complete
  runtime environment (Python, PostgreSQL, all dependencies) directly to `/opt/srdb`.
- Ansible playbook provisions a VPS: creates a dedicated service user, runs the installer,
  writes the config (GitHub tokens via Ansible Vault), installs Caddy, and sets up three systemd
  units (srdb-db, srdb-worker, srdb-server).
- Caddy provides automatic HTTPS with Let's Encrypt, serves frontend static files from
  `/var/www/srdb`, and reverse-proxies `/api/*` to the uvicorn server.
- `scripts/update.sh` handles the full release cycle: rebuild artifact, upload installer and
  frontend assets, run migrations, restart services.

## Non-goals

- Multi-server or containerized deployments.
- CI/CD pipeline integration (GitHub Actions etc.) — this is a manual, single-person workflow.
- System PostgreSQL — the bundled PostgreSQL from conda-forge is used throughout.
- Blue/green deployments or zero-downtime rollouts.
- Rollback — the installer overwrites `/opt/srdb/env` in place; no versioned env dirs are kept.

## Constraints

- The Python package source is pure Python so `noarch: python` is valid; platform-specific
  dependencies (postgresql, psycopg2) are resolved at install time by pixi.
- `perceval` is on conda-forge (updated in pixi.toml), so the build script no longer needs a
  separate `pip install perceval` step.
- pixi-pack must target `linux-64` explicitly since the developer machine may be `osx-arm64`.
- `dist/` is gitignored; a fresh build is required before deploying.
- Ansible Vault protects the GitHub token; the vault password is never committed.
- The VPS `/tmp` is a small tmpfs; the installer and its `TMPDIR` are set to `/var/tmp`
  (disk-backed) to avoid running out of space during extraction.
