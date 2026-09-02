#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_DIR"

if [ ! -f .env ]; then
  echo "Missing $REPO_DIR/.env. Copy .env.example and configure it first." >&2
  exit 1
fi

set -a
. ./.env
set +a

PYTHON="$REPO_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Missing .venv. Run scripts/bootstrap-local.sh first." >&2
  exit 1
fi

GIS_IMPORT=$($PYTHON -c 'from pathlib import Path; import gis; print(Path(gis.__file__).resolve())')
case "$GIS_IMPORT" in
  "$REPO_DIR"/src/gis/*) ;;
  *) echo "GIS imports from $GIS_IMPORT instead of this repository. Run scripts/bootstrap-local.sh." >&2; exit 1 ;;
esac

export GIS_API_BASE_URL=http://127.0.0.1:8001
export PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

cleanup() {
  if [ -n "${API_PID:-}" ]; then kill "$API_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

"$PYTHON" -m uvicorn gis.api.app:create_app --factory --host 127.0.0.1 --port 8001 &
API_PID=$!
sleep 1
if ! kill -0 "$API_PID" 2>/dev/null; then
  echo "GIS API failed to start. Confirm that port 8001 is available." >&2
  exit 1
fi

cd apps/workbench
npm run dev -- --hostname 127.0.0.1 --port 3001
