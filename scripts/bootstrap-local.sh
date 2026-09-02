#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_DIR"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -e ".[dev]"
cd apps/workbench
npm ci

echo "Local dependencies installed. Run scripts/dev-workbench.sh to start GIS."
