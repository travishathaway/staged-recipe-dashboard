#!/usr/bin/env bash
# Build script for the conda package.
#
# Prerequisites:
#   Run `srdb build-ui` (or `pixi run -e frontend build-ui`) before `conda build`
#   to ensure frontend/dist/ exists.
set -euxo pipefail

# Install the Python package.
$PYTHON -m pip install . -vv --no-deps --no-build-isolation

# Install perceval from PyPI (not available on conda-forge).
$PYTHON -m pip install perceval

# Copy pre-built frontend assets into the installed package's static/ directory.
STATIC_DIR="$SP_DIR/staged_recipe_dashboard/static"
mkdir -p "$STATIC_DIR"

if [ -d "frontend/dist" ]; then
    cp -r frontend/dist/. "$STATIC_DIR/"
    echo "Frontend assets copied to $STATIC_DIR"
else
    echo "WARNING: frontend/dist not found."
    echo "Run 'srdb build-ui' before 'conda build' to include the frontend."
fi
