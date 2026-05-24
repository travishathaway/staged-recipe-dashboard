# Design: VPS Deployment

## Repository Layout

```
recipe/
  recipe.yaml              ← rattler-build recipe (replaces meta.yaml + build.sh)

scripts/
  build.sh                 ← local: frontend → rattler-build → pixi-pack
  update.sh                ← local: build + ansible deploy

deploy/
  ansible.cfg
  inventory.yml            ← VPS hostname/IP (user fills in)
  playbook.yml             ← top-level play, imports role
  secrets.yml              ← ansible-vault encrypted (github_tokens)
  roles/
    srdb/
      defaults/main.yml    ← install_dir, service_user, domain, port, env_name
      tasks/
        main.yml           ← imports subtask files in order
        install.yml        ← upload + extract pixi-pack tarball, symlink swap
        config.yml         ← write config.toml from vault secret
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
- `.gitignore` — add `dist/`

Removed files:
- `recipe/meta.yaml`
- `recipe/build.sh`

---

## rattler-build Recipe (`recipe/recipe.yaml`)

The package is `noarch: python` because the app is pure Python. Platform-specific dependencies
(postgresql, psycopg2) are resolved at environment install time, not at package build time.

```yaml
context:
  version: "0.1.0"

package:
  name: staged-recipe-dashboard
  version: ${{ version }}

source:
  path: ../

build:
  number: 0
  noarch: python
  python:
    entry_points:
      - srdb = staged_recipe_dashboard.cli:app
  script:
    - $PYTHON -m pip install . --no-deps --no-build-isolation -vv
    - mkdir -p $SP_DIR/staged_recipe_dashboard/static
    - "[ -d frontend/dist ] && cp -r frontend/dist/. $SP_DIR/staged_recipe_dashboard/static/ || true"

requirements:
  host:
    - python >=3.11
    - pip
    - hatchling
  run:
    - python >=3.11
    - postgresql >=16
    - psycopg2 >=2.9
    - fastapi >=0.110
    - uvicorn >=0.29
    - sqlalchemy >=2.0
    - alembic >=1.13
    - httpx >=0.27
    - apscheduler >=3.10
    - typer >=0.12
    - platformdirs >=4.2
    - perceval >=1.4.7

about:
  homepage: https://github.com/conda-forge/staged-recipe-dashboard
  license: MIT
  summary: Dashboard for conda-forge staged-recipe PR reviewers
```

---

## pixi.toml Changes

Add `./dist/channel` as the first channel (local channel, gitignored). Add a `release` feature
and `prod` environment that installs `staged-recipe-dashboard` from the conda artifact instead of
the editable pypi path:

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

3. pixi install -e prod
   → Resolves environment from dist/channel + conda-forge

4. pixi-pack pack -e prod --platform linux-64 -o dist/srdb-pack.tar.gz
   → Produces the deployment artifact
```

---

## Update Pipeline (`scripts/update.sh`)

```
1. Run scripts/build.sh

2. ansible-playbook deploy/playbook.yml
   (Ansible role handles stopping services, uploading, swapping, migrating, restarting)
```

---

## VPS Directory Structure

```
/opt/srdb/
  env -> env-20260524/     ← symlink to current environment
  env-20260524/            ← extracted pixi-pack (bin/srdb, bin/pg_ctl, …)
  env-previous/            ← previous environment (kept for rollback)

/var/lib/srdb/
  pgdata/                  ← PostgreSQL data directory (persists across deploys)

/home/srdb/                ← service user home
  .config/staged-recipe-dashboard/
    config.toml            ← GitHub tokens (written by Ansible from vault secret)

/etc/caddy/
  Caddyfile                ← reverse proxy config

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
srdb_data_dir: /var/lib/srdb
srdb_service_user: srdb
srdb_domain: "example.com"          # operator fills in
srdb_server_port: 8000
srdb_env_name: "env-{{ ansible_date_time.date | replace('-', '') }}"
srdb_pack_local: "{{ playbook_dir }}/../dist/srdb-pack.tar.gz"
```

### `tasks/install.yml` — environment swap

```
1. Create service user (srdb, system, no login shell)
2. Create /opt/srdb/, /var/lib/srdb/ owned by srdb
3. Upload dist/srdb-pack.tar.gz → /opt/srdb/{{ srdb_env_name }}.tar.gz
4. Extract into /opt/srdb/{{ srdb_env_name }}/
   (pixi-pack unpack or conda-unpack inside the archive)
5. Stop services (if running): srdb-server, srdb-worker, srdb-db
6. Rotate symlink: env-previous → current env, env → new env
7. Restart services
```

### `tasks/config.yml` — configuration

Write `/home/srdb/.config/staged-recipe-dashboard/config.toml` from `config.toml.j2`,
templated with vault-decrypted `github_tokens`.

### `tasks/systemd.yml` — service units

Three units, all running as `User=srdb`, with `Environment=PATH=/opt/srdb/env/bin:…`:

**`srdb-db.service`** — `Type=forking`, runs `pg_ctl start`:
```ini
[Unit]
Description=srdb bundled PostgreSQL
After=network.target

[Service]
Type=forking
User=srdb
Environment=PATH=/opt/srdb/env/bin:/usr/bin:/bin
ExecStart=/opt/srdb/env/bin/pg_ctl start -D /var/lib/srdb/pgdata -l /var/lib/srdb/postgres.log
ExecStop=/opt/srdb/env/bin/pg_ctl stop -D /var/lib/srdb/pgdata
PIDFile=/var/lib/srdb/pgdata/postmaster.pid
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**`srdb-worker.service`** — `Type=simple`, depends on srdb-db:
```ini
[Unit]
Description=srdb background sync worker
After=srdb-db.service
Requires=srdb-db.service

[Service]
Type=simple
User=srdb
Environment=PATH=/opt/srdb/env/bin:/usr/bin:/bin
ExecStart=/opt/srdb/env/bin/srdb worker
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**`srdb-server.service`** — `Type=simple`, depends on srdb-db:
```ini
[Unit]
Description=srdb FastAPI server
After=srdb-db.service
Requires=srdb-db.service

[Service]
Type=simple
User=srdb
Environment=PATH=/opt/srdb/env/bin:/usr/bin:/bin
ExecStart=/opt/srdb/env/bin/srdb serve
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### `tasks/caddy.yml` — reverse proxy

Install Caddy from the official apt/dnf repository (or direct binary download as fallback),
then write `/etc/caddy/Caddyfile` and enable the `caddy.service` systemd unit.

**`Caddyfile.j2`:**
```
{{ srdb_domain }} {
    reverse_proxy localhost:{{ srdb_server_port }}
}
```

Caddy automatically: obtains a TLS cert from Let's Encrypt on first request, renews it, and
redirects HTTP → HTTPS. Ports 80 and 443 must be open on the VPS firewall.

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

## `srdb init` on First Deploy

The `install.yml` tasks run `srdb init` (postgres initdb + alembic migrations) on first deploy only,
guarded by checking whether `/var/lib/srdb/pgdata/PG_VERSION` exists. On updates, only
`alembic upgrade head` is run.

---

## Rollback

To roll back to the previous environment:
```bash
ansible-playbook deploy/playbook.yml --tags rollback
# or manually on the VPS:
sudo systemctl stop srdb-server srdb-worker srdb-db
sudo ln -sfn /opt/srdb/env-previous /opt/srdb/env
sudo systemctl start srdb-db srdb-worker srdb-server
```
