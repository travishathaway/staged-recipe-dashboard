# Design: VPS Deployment

## Repository Layout

```
recipe/
  recipe.yaml              ← rattler-build recipe (noarch:python, pip install only)

scripts/
  build.sh                 ← local: frontend → rattler-build → pixi-pack (self-extracting .sh)
  update.sh                ← local: build + ansible deploy

deploy/
  ansible.cfg
  inventory.yml            ← VPS hostname/IP
  playbook.yml             ← top-level play, imports role
  secrets.yml              ← ansible-vault encrypted (github_tokens)
  roles/
    srdb/
      defaults/main.yml    ← install_dir, env_dir, html_dir, service_user, domain, port
      tasks/
        main.yml           ← imports: install → config → db → systemd → caddy
        install.yml        ← user/dirs, upload .sh installer, run installer, upload frontend assets
        config.yml         ← write config.toml from vault secret
        db.yml             ← create /run/srdb, run srdb init (idempotent), stop postgres
        systemd.yml        ← install + enable 3 service units
        caddy.yml          ← install caddy, write Caddyfile, enable service
      templates/
        config.toml.j2
        Caddyfile.j2
        srdb-db.service.j2
        srdb-worker.service.j2
        srdb-server.service.j2
```

Modified files:
- `pixi.toml` — add `./dist/channel` channel, add `prod` environment, add `release` feature
- `src/.../backend/app.py` — remove static file serving; FastAPI is now API-only

---

## rattler-build Recipe (`recipe/recipe.yaml`)

The package is `noarch: python` because the app is pure Python. Platform-specific dependencies
(postgresql, psycopg2) are resolved at environment install time. Frontend assets are **not**
bundled in the conda package — they are uploaded separately by Ansible.

```yaml
build:
  noarch: python
  python:
    entry_points:
      - srdb = staged_recipe_dashboard.cli:app
  script:
    - $PYTHON -m pip install . --no-deps --no-build-isolation -vv
```

---

## Frontend Asset Serving

Frontend assets are built locally and uploaded directly to `/var/www/srdb` on the server.
Caddy serves them as static files; FastAPI handles only `/api/*` routes.

### Build and deploy flow

```
scripts/build.sh
  │
  └─ 1. pixi run -e frontend build-ui
         npm run build → frontend/dist/
                           assets/index-*.js
                           assets/index-*.css
                           index.html

scripts/update.sh → ansible-playbook
  │
  └─ Ansible task: copy frontend/dist/ → /var/www/srdb/ on VPS
```

### Runtime serving

```
Caddy ({{ srdb_domain }})
  │
  ├─ /api/*  → reverse_proxy localhost:8000   (uvicorn / FastAPI)
  │
  └─ /*      → file_server /var/www/srdb      (Svelte SPA, try_files → index.html)
```

**`Caddyfile.j2`:**
```
{{ srdb_domain }} {
    handle /api/* {
        reverse_proxy localhost:{{ srdb_server_port }}
    }

    handle {
        root * {{ srdb_html_dir }}
        try_files {path} /index.html
        file_server
    }
}
```

`try_files {path} /index.html` ensures Svelte client-side routes (e.g. `/team/python`) fall back
to `index.html` rather than returning 404.

### What this means for deploys

- A frontend change requires running `scripts/update.sh` (or `scripts/build.sh` + deploy). The
  Ansible `copy` task syncs `frontend/dist/` to `/var/www/srdb/` on every run.
- `/var/www/srdb` is world-readable (mode `0755`) so Caddy can traverse it without being added
  to the `srdb` group. `/var/lib/srdb` (mode `0750`) is not used for web-served content.
- FastAPI no longer mounts `StaticFiles` or has a SPA catch-all route.

---

## pixi.toml Changes

Add `./dist/channel` as the first channel (local channel, gitignored). Add a `release` feature
and `prod` environment that installs `staged-recipe-dashboard` from the conda artifact:

```toml
[workspace]
channels = ["./dist/channel", "conda-forge"]

[feature.release.dependencies]
staged-recipe-dashboard = ">=0.1.0"

[environments]
prod = { features = ["worker", "backend", "db", "release"] }
# no "app" feature — editable pypi install is development-only
```

---

## Build Pipeline (`scripts/build.sh`)

```
1. pixi run -e frontend build-ui
   → Builds Svelte SPA into frontend/dist/

2. rattler-build build --recipe recipe/ -o dist/channel/
   → Produces dist/channel/noarch/staged-recipe-dashboard-0.1.0-*.conda

3. pixi update --environment prod staged-recipe-dashboard
   → Updates lock file (hash changes on every rebuild)

4. pixi-pack -e prod --platform linux-64 --create-executable -o dist/srdb-install.sh
   → Produces the self-extracting installer
```

---

## Update Pipeline (`scripts/update.sh`)

```
1. Run scripts/build.sh (produces dist/srdb-install.sh and frontend/dist/)

2. ansible-playbook deploy/playbook.yml
   (Ansible role handles stopping services, uploading installer, installing env,
    uploading frontend assets, writing config, running migrations, starting services)
```

Supports `--skip-build` flag and passes additional args through to ansible-playbook.

---

## VPS Directory Structure

```
/opt/srdb/
  env/                     ← conda environment extracted by self-extracting installer
    bin/srdb               ← CLI entry point
    bin/pg_ctl             ← bundled PostgreSQL
    bin/uvicorn
    lib/python3.12/...

/var/lib/srdb/
  pgdata/                  ← PostgreSQL data directory (persists across deploys)
  app.log                  ← application log

/var/www/srdb/             ← Caddy-served frontend assets (world-readable)
  index.html
  assets/

/home/srdb/                ← service user home
  .config/staged-recipe-dashboard/
    config.toml            ← GitHub tokens (written by Ansible from vault secret)

/run/srdb/                 ← runtime dir (tmpfs; created by systemd RuntimeDirectory=srdb)

/etc/caddy/
  Caddyfile                ← split routing: static files + API proxy

/etc/systemd/system/
  srdb-db.service
  srdb-worker.service
  srdb-server.service
```

---

## Ansible Role

### `defaults/main.yml`

```yaml
srdb_install_dir: /opt/srdb
srdb_env_dir: "{{ srdb_install_dir }}/env"   # bin/ is at srdb_env_dir/bin/
srdb_data_dir: /var/lib/srdb
srdb_html_dir: /var/www/srdb
srdb_service_user: srdb
srdb_service_group: srdb
srdb_domain: "srdb.thath.net"
srdb_server_port: 8000
srdb_pack_local: "{{ playbook_dir }}/../dist/srdb-install.sh"
```

### `tasks/install.yml` — environment install

```
1. Create srdb group and service user (system, no login shell)
2. Create /opt/srdb/ and /var/lib/srdb/ owned by srdb (mode 0755/0750)
3. Create /var/www/srdb/ (mode 0755, world-readable for Caddy)
4. Stop services (if running): srdb-server, srdb-worker, srdb-db
5. Upload dist/srdb-install.sh → /var/tmp/srdb-install.sh
6. Run: TMPDIR=/var/tmp bash /var/tmp/srdb-install.sh --output-directory /opt/srdb
   (/var/tmp used for both upload and TMPDIR to avoid small /tmp tmpfs)
7. Remove /var/tmp/srdb-install.sh
8. Fix ownership of /opt/srdb recursively (srdb:srdb)
9. Upload frontend/dist/ → /var/www/srdb/
```

### `tasks/db.yml` — database initialisation

`srdb init` is fully idempotent and used for both first deploy and updates:
- First deploy: runs `initdb`, starts postgres, creates the app database, runs alembic migrations
- Updates: starts postgres (skips initdb, pgdata exists), runs any new migrations

```
1. Create /run/srdb (mode 0750, owned by srdb) — needed before srdb init
   (systemd RuntimeDirectory recreates this on reboot; this task handles first deploy)
2. Run: srdb init (as srdb user, with XDG_RUNTIME_DIR=/run/srdb)
3. Run: srdb db stop (failed_when: false — postgres is stopped so systemd takes ownership)
```

### `tasks/systemd.yml` — service units

Three units, all `User=srdb`, `XDG_RUNTIME_DIR=/run/srdb`, `PATH={{ srdb_env_dir }}/bin:…`.

**`srdb-db.service`** — `Type=forking`, `RuntimeDirectory=srdb`:
```ini
[Service]
Type=forking
RuntimeDirectory=srdb
Environment=PATH={{ srdb_env_dir }}/bin:/usr/bin:/bin
Environment=XDG_RUNTIME_DIR=/run/srdb
ExecStart={{ srdb_env_dir }}/bin/pg_ctl start -D /var/lib/srdb/pgdata ...
PIDFile=/var/lib/srdb/pgdata/postmaster.pid
```

`RuntimeDirectory=srdb` tells systemd to create `/run/srdb` owned by `srdb` before each start,
ensuring it survives across reboots (since `/run` is tmpfs).

**`srdb-worker.service`** and **`srdb-server.service`** — `Type=simple`, `Requires=srdb-db.service`.

### `tasks/caddy.yml` — reverse proxy

Install Caddy, write `/etc/caddy/Caddyfile` from `Caddyfile.j2`, reload/enable the service.

### `secrets.yml` (Ansible Vault)

```yaml
github_tokens:
  - "ghp_YOUR_TOKEN_HERE"
```

Encrypted with: `ansible-vault encrypt deploy/secrets.yml`

---

## `config.toml.j2`

```toml
[database]
data_dir = "/var/lib/srdb/pgdata"
socket_dir = "/var/lib/srdb"

[worker]
github_tokens = {{ github_tokens | tojson }}

[server]
host = "0.0.0.0"
port = {{ srdb_server_port }}

[logging]
file = "/var/lib/srdb/app.log"
level = "INFO"
```

---

## `srdb init` — idempotent for both first deploy and updates

`srdb init` calls `db_start()` (which starts postgres, creating the cluster if `pgdata` doesn't
exist) then runs alembic migrations via the Python API. It is safe to call on every deploy.
The `db.yml` task stops postgres afterward so systemd takes exclusive ownership on service start.

The alembic migration uses the Python API (`alembic.command.upgrade`) rather than a subprocess
call to avoid a CWD dependency on `alembic.ini`, which is not present in the installed package.
