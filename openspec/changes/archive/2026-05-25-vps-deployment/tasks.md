# Tasks: VPS Deployment

## Phase 1 — rattler-build Recipe

- [x] **1.1** Create `recipe/recipe.yaml` with `noarch: python` build, pip install script, and all
  run dependencies including `perceval >=1.4.7`. Entry point: `srdb = staged_recipe_dashboard.cli:app`.
  Frontend assets are **not** bundled in the conda package (uploaded separately by Ansible).

- [x] **1.2** Delete `recipe/meta.yaml` and `recipe/build.sh` — superseded by `recipe/recipe.yaml`.

---

## Phase 2 — pixi.toml Production Environment

- [x] **2.1** Add `./dist/channel` as the first entry in the workspace `channels` list in
  `pixi.toml`.

- [x] **2.2** Add `[feature.release.dependencies]` with `staged-recipe-dashboard = ">=0.1.0"` and
  add a `prod` environment: `{ features = ["worker", "backend", "db", "release"] }`. The `prod`
  environment intentionally omits the `app` feature (no editable pypi install).
  Also added `rattler-build`, `pixi-pack`, and `ansible` to `[feature.dev.dependencies]`.

- [x] **2.3** `dist/` is gitignored via the pre-existing Python packaging template entry.

---

## Phase 3 — Build and Update Scripts

- [x] **3.1** Create `scripts/build.sh`:
  1. `pixi run -e frontend build-ui`
  2. `rattler-build build --recipe recipe/ -o dist/channel/`
  3. `pixi update --environment prod staged-recipe-dashboard` (update, not install — hash changes
     on every rebuild)
  4. `pixi-pack -e prod --platform linux-64 --create-executable -o dist/srdb-install.sh`

  Script is `set -euo pipefail` with progress headers. Made executable.

- [x] **3.2** Create `scripts/update.sh` that runs `scripts/build.sh` then
  `ansible-playbook deploy/playbook.yml` (from `deploy/` directory so `ansible.cfg` is found).
  Supports `--skip-build` and passthrough of additional args to ansible-playbook.

---

## Phase 4 — Ansible Playbook and Role

- [x] **4.1** Create `deploy/ansible.cfg`.

- [x] **4.2** Create `deploy/inventory.yml` with VPS hostname.

- [x] **4.3** Create `deploy/playbook.yml`.

- [x] **4.4** Create `deploy/secrets.yml` (template; encrypt with `ansible-vault encrypt deploy/secrets.yml`).

- [x] **4.5** Create `deploy/roles/srdb/defaults/main.yml` with variables:
  - `srdb_install_dir: /opt/srdb`
  - `srdb_env_dir: "{{ srdb_install_dir }}/env"` (all binaries at `srdb_env_dir/bin/`)
  - `srdb_data_dir: /var/lib/srdb`
  - `srdb_html_dir: /var/www/srdb` (Caddy-served frontend assets; world-readable)
  - `srdb_service_user/group: srdb`
  - `srdb_domain`, `srdb_server_port`
  - `srdb_pack_local: "{{ playbook_dir }}/../dist/srdb-install.sh"`

- [x] **4.6** Create `deploy/roles/srdb/tasks/install.yml`:
  - Create srdb group and service user
  - Create `/opt/srdb/` (0755) and `/var/lib/srdb/` (0750)
  - Create `/var/www/srdb/` (0755, world-readable for Caddy)
  - Stop services (failed_when: false for first deploy)
  - Upload `dist/srdb-install.sh` to `/var/tmp/srdb-install.sh` (avoids small /tmp tmpfs)
  - Run `TMPDIR=/var/tmp bash /var/tmp/srdb-install.sh --output-directory /opt/srdb`
  - Remove installer script
  - Fix ownership of `/opt/srdb` recursively
  - Upload `frontend/dist/` → `/var/www/srdb/`

- [x] **4.7** Create `deploy/roles/srdb/tasks/config.yml`.

- [x] **4.8** Create `deploy/roles/srdb/tasks/systemd.yml`: install units, enable and start
  services. `srdb-db.service` uses `RuntimeDirectory=srdb` so systemd creates `/run/srdb`
  owned by `srdb` before each start (survives reboots since `/run` is tmpfs).
  Also created `handlers/main.yml` for systemd daemon-reload and Caddy reload handlers.

- [x] **4.9** Create `deploy/roles/srdb/tasks/caddy.yml`.

- [x] **4.10** Create `deploy/roles/srdb/tasks/main.yml`. Import order:
  `install → config → db → systemd → caddy`. The `db.yml` file is separate because
  `config.toml` must exist before `srdb init` runs.

- [x] **4.11** Create all templates under `deploy/roles/srdb/templates/`:
  - `config.toml.j2`
  - `Caddyfile.j2` — split routing: `/api/*` → reverse proxy, `/*` → Caddy file_server with
    SPA `try_files` fallback; `root *` points to `{{ srdb_html_dir }}`
  - `srdb-db.service.j2`, `srdb-worker.service.j2`, `srdb-server.service.j2` — all use
    `{{ srdb_env_dir }}/bin/` for `ExecStart` and `PATH`; `srdb-db` adds `RuntimeDirectory=srdb`

---

## Phase 5 — Frontend Serving (replaces original bundled approach)

- [x] **5.1** Remove static file serving from `backend/app.py`: remove `StaticFiles`, `FileResponse`,
  `STATIC_DIR`, and the SPA catch-all route. FastAPI now handles only `/api/*`.

- [x] **5.2** Remove frontend asset copy from `recipe/recipe.yaml` build script. The conda package
  is now purely the Python application.

- [x] **5.3** Caddy `Caddyfile.j2` updated to serve `/var/www/srdb` as the document root with
  `try_files {path} /index.html` for SPA routing, and reverse-proxy only `/api/*` to uvicorn.

---

## Phase 6 — Documentation

- [x] **6.1** Updated `README.md` with a "Deployment" section: prerequisites, first-time setup
  steps (inventory, domain, vault-encrypt secrets), `scripts/update.sh`.

---

## Post-apply fixes

- [x] Fixed `cli.py:init()` to use alembic's Python API instead of
  `subprocess.run(["alembic", "upgrade", "head"])`. The subprocess form requires `alembic.ini`
  in CWD, which is not present in the installed package. Also added `srdb migrate` command.

- [x] Fixed `db.yml` to use `srdb init` for both first deploy and updates (previously called
  `srdb migrate` on update, which failed because postgres was not running at deploy time).

- [x] Added task in `db.yml` to create `/run/srdb` before running `srdb init` (first deploy runs
  before systemd has ever started `srdb-db.service`, so `RuntimeDirectory` hasn't fired yet).

- [x] Switched pixi-pack output from `.tar.gz` archive to self-extracting `.sh` installer
  (`--create-executable`) to avoid needing `pixi-unpack` on the VPS.

- [x] Changed installer upload destination from `/tmp` to `/var/tmp`, and set `TMPDIR=/var/tmp`
  when running the installer, to avoid running out of space on the small tmpfs at `/tmp`.
