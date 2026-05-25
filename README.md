# staged-recipe-dashboard

## Deployment

The app deploys to a Linux VPS as a self-contained environment built with
[rattler-build](https://github.com/prefix-dev/rattler-build) and
[pixi-pack](https://github.com/prefix-dev/pixi-pack), then provisioned with Ansible and
fronted by Caddy (automatic HTTPS via Let's Encrypt).

### Prerequisites

Install once on your local machine:

```bash
pixi global install rattler-build pixi-pack
pip install ansible   # or: brew install ansible
```

### First-time setup

1. **Configure the inventory** — edit `deploy/inventory.yml` with your VPS IP and SSH user.

2. **Configure the domain** — edit `deploy/roles/srdb/defaults/main.yml` and set `srdb_domain`
   to the domain pointing at your VPS.

3. **Set your GitHub token** — edit `deploy/secrets.yml`, add your token(s), then encrypt:
   ```bash
   ansible-vault encrypt deploy/secrets.yml
   ```

4. **Deploy:**
   ```bash
   scripts/update.sh --ask-vault-pass
   ```
   This builds the frontend, packages the environment, and runs the Ansible playbook.
   On first deploy Ansible will initialize PostgreSQL, create the database, and run migrations.

### Subsequent deploys

```bash
scripts/update.sh --ask-vault-pass
```

The playbook stops services, swaps in the new environment via symlink, runs any new migrations,
and restarts. To roll back:

```bash
# On the VPS:
sudo systemctl stop srdb-server srdb-worker srdb-db
sudo ln -sfn /opt/srdb/env-previous /opt/srdb/env
sudo systemctl start srdb-db srdb-worker srdb-server
```

### Deploy without rebuilding

If you only changed Ansible config (e.g., updated the domain or Caddyfile):

```bash
scripts/update.sh --skip-build --ask-vault-pass
```
