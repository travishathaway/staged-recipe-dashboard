# Tasks: VPS Deployment

## Phase 1 — rattler-build Recipe

- [ ] **1.1** Create `recipe/recipe.yaml` with `noarch: python` build, inline script (pip install +
  frontend asset copy), and all run dependencies including `perceval >=1.4.7`. Entry point:
  `srdb = staged_recipe_dashboard.cli:app`. Match versions from `pixi.toml`.

- [ ] **1.2** Delete `recipe/meta.yaml` and `recipe/build.sh` — superseded by `recipe/recipe.yaml`.

---

## Phase 2 — pixi.toml Production Environment

- [ ] **2.1** Add `./dist/channel` as the first entry in the workspace `channels` list in
  `pixi.toml`.

- [ ] **2.2** Add `[feature.release.dependencies]` with `staged-recipe-dashboard = ">=0.1.0"` and
  add a `prod` environment: `{ features = ["worker", "backend", "db", "release"] }`. The `prod`
  environment intentionally omits the `app` feature (no editable pypi install).

- [ ] **2.3** Add `dist/` to `.gitignore`.

---

## Phase 3 — Build and Update Scripts

- [ ] **3.1** Create `scripts/build.sh`:
  1. `pixi run -e frontend build-ui`
  2. `rattler-build build --recipe recipe/ -o dist/channel/`
  3. `pixi install -e prod`
  4. `pixi-pack pack -e prod --platform linux-64 -o dist/srdb-pack.tar.gz`
  
  Script should be `set -euo pipefail` and print progress headers for each step. Make executable.

- [ ] **3.2** Create `scripts/update.sh` that runs `scripts/build.sh` then
  `ansible-playbook deploy/playbook.yml`. Accept an optional `--tags` passthrough argument.
  Make executable.

---

## Phase 4 — Ansible Playbook and Role

- [ ] **4.1** Create `deploy/ansible.cfg` pointing at `inventory.yml` and setting
  `roles_path = roles` and `vault_password_file` (optional, document the convention).

- [ ] **4.2** Create `deploy/inventory.yml` as a template with a placeholder hostname/IP and
  a comment instructing the operator to fill it in.

- [ ] **4.3** Create `deploy/playbook.yml` that targets the `srdb` host group, becomes root,
  includes `deploy/secrets.yml` as a vars file, and applies the `srdb` role. Include a `rollback`
  tag path.

- [ ] **4.4** Create `deploy/secrets.yml` as an example plaintext file (not yet vault-encrypted)
  containing `github_tokens: ["ghp_YOUR_TOKEN_HERE"]` with a comment instructing the operator to
  encrypt it with `ansible-vault encrypt deploy/secrets.yml`.

- [ ] **4.5** Create `deploy/roles/srdb/defaults/main.yml` with variables:
  `srdb_install_dir`, `srdb_data_dir`, `srdb_service_user`, `srdb_domain`, `srdb_server_port`,
  `srdb_env_name` (date-stamped), `srdb_pack_local`.

- [ ] **4.6** Create `deploy/roles/srdb/tasks/install.yml`:
  - Create service user `srdb` (system user, no login shell, home `/home/srdb`)
  - Create `/opt/srdb/`, `/var/lib/srdb/` owned by `srdb`
  - Upload `dist/srdb-pack.tar.gz` to `/opt/srdb/{{ srdb_env_name }}.tar.gz`
  - Extract into `/opt/srdb/{{ srdb_env_name }}/` using pixi-pack's `conda-unpack` or the
    bundled shell installer in the tarball
  - On first deploy only (no `PG_VERSION` file): run `srdb init` as the `srdb` user to
    initialize PostgreSQL and run Alembic migrations
  - On updates: stop services, rotate symlink (`env-previous` → current, `env` → new),
    run `srdb db start` + `alembic upgrade head`, restart services

- [ ] **4.7** Create `deploy/roles/srdb/tasks/config.yml`:
  - Ensure `~srdb/.config/staged-recipe-dashboard/` exists
  - Template `config.toml.j2` → `/home/srdb/.config/staged-recipe-dashboard/config.toml`
    with mode `0600` (contains secrets)

- [ ] **4.8** Create `deploy/roles/srdb/tasks/systemd.yml`:
  - Template and install `srdb-db.service`, `srdb-worker.service`, `srdb-server.service` to
    `/etc/systemd/system/`
  - Run `systemctl daemon-reload`
  - Enable and start all three units in dependency order (db first)

- [ ] **4.9** Create `deploy/roles/srdb/tasks/caddy.yml`:
  - Install Caddy using the official apt/dnf repository (detect distro via `ansible_os_family`)
  - Template `Caddyfile.j2` → `/etc/caddy/Caddyfile`
  - Enable and start `caddy.service`
  - Notify Caddy reload on Caddyfile change

- [ ] **4.10** Create `deploy/roles/srdb/tasks/main.yml` that imports the four subtask files
  in order: install → config → systemd → caddy.

- [ ] **4.11** Create all templates under `deploy/roles/srdb/templates/`:
  - `config.toml.j2` — database, worker (github_tokens), server, logging sections
  - `Caddyfile.j2` — single reverse_proxy block using `srdb_domain` and `srdb_server_port`
  - `srdb-db.service.j2` — Type=forking, pg_ctl start/stop, PIDFile
  - `srdb-worker.service.j2` — Type=simple, After+Requires srdb-db, srdb worker
  - `srdb-server.service.j2` — Type=simple, After+Requires srdb-db, srdb serve
  
  All service units set `User={{ srdb_service_user }}` and
  `Environment=PATH=/opt/srdb/env/bin:/usr/bin:/bin`.

---

## Phase 5 — Documentation

- [ ] **5.1** Update `README.md` with a "Deployment" section covering:
  - Prerequisites (rattler-build and pixi-pack installed locally, Ansible installed)
  - First-time setup steps (fill in inventory.yml, vault-encrypt secrets.yml, set domain)
  - `scripts/update.sh` for subsequent deploys
  - Rollback instructions
