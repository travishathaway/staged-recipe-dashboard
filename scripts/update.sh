#!/usr/bin/env bash
# Build and deploy staged-recipe-dashboard to the VPS.
#
# Usage:
#   scripts/update.sh                   # full build + deploy
#   scripts/update.sh --tags systemd    # deploy only, skip build (pass --tags to ansible)
#   scripts/update.sh --skip-build      # deploy using existing dist/srdb-pack.tar.gz
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SKIP_BUILD=false
ANSIBLE_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-build) SKIP_BUILD=true; shift ;;
        *) ANSIBLE_ARGS+=("$1"); shift ;;
    esac
done

if [[ "$SKIP_BUILD" == false ]]; then
    echo "=== Building deployment artifact ==="
    bash scripts/build.sh
fi

if [[ ! -f dist/srdb-install.sh ]]; then
    echo "Error: dist/srdb-install.sh not found. Run scripts/build.sh first." >&2
    exit 1
fi

echo "=== Deploying with Ansible ==="
# Run from deploy/ so ansible.cfg is picked up automatically.
# pixi traverses up the directory tree to find pixi.toml.
cd "$REPO_ROOT/deploy"
pixi run -e dev -- ansible-playbook playbook.yml "${ANSIBLE_ARGS[@]+"${ANSIBLE_ARGS[@]}"}"

echo ""
echo "Deployment complete."
