#!/usr/bin/env bash
# Build the deployment artifact: frontend → rattler-build → pixi-pack
#
# Prerequisites (install once with pixi global install):
#   pixi global install rattler-build pixi-pack
#
# Output: dist/srdb-pack.tar.gz — upload this to the VPS via scripts/update.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Step 1: Build frontend ==="
pixi run -e frontend build-ui

echo "=== Step 2: Build conda package with rattler-build ==="
rattler-build build --recipe recipe/ --output-dir dist/channel/

echo "=== Step 3: Update and install prod environment ==="
# Update the lock file for this package — its hash changes on every rebuild,
# so pixi install would fail with a hash mismatch if we only ran pixi install.
pixi update --environment prod staged-recipe-dashboard

echo "=== Step 4: Pack environment with pixi-pack ==="
pixi-pack -e prod --platform linux-64 --create-executable --output-file dist/srdb-install.sh

echo ""
echo "Build complete: dist/srdb-install.sh"
echo "Run scripts/update.sh to deploy."
