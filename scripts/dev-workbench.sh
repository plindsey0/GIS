#!/bin/sh
set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_DIR"

if [ ! -f .env ]; then
  echo "Missing $REPO_DIR/.env. Copy .env.example and configure it first." >&2
  exit 1
fi

PAID_EXECUTION_HOLD=${GIS_PAID_EXECUTION_DISABLED:-}
set -a
. ./.env
set +a
if [ "$PAID_EXECUTION_HOLD" = "1" ]; then
  export GIS_PAID_EXECUTION_DISABLED=1
fi

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
export PATH="$REPO_DIR/.venv/bin:$PATH"

CURRENT_REV=$($REPO_DIR/.venv/bin/alembic current 2>/dev/null | awk 'NF {print $1; exit}')
HEAD_REV=$($REPO_DIR/.venv/bin/alembic heads 2>/dev/null | awk 'NF {print $1; exit}')
if [ "$CURRENT_REV" != "$HEAD_REV" ]; then
  echo "GIS database migration is $CURRENT_REV; application head is $HEAD_REV." >&2
  echo "Run: .venv/bin/alembic upgrade head" >&2
  exit 1
fi

cleanup() {
  for pid in ${WORKBENCH_PID:-} ${WORKER_PID:-} ${API_PID:-}; do
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT INT TERM

"$PYTHON" -m gis.provider_control.runtime

"$PYTHON" -m uvicorn gis.api.app:create_app --factory --host 127.0.0.1 --port 8001 &
API_PID=$!
sleep 1
if ! kill -0 "$API_PID" 2>/dev/null; then
  echo "GIS API failed to start. Confirm that port 8001 is available." >&2
  exit 1
fi

"$REPO_DIR/.venv/bin/gis-orchestrator" worker --sleep-seconds 15 --worker-id "local-dev" &
WORKER_PID=$!
sleep 1
if ! kill -0 "$WORKER_PID" 2>/dev/null; then
  echo "GIS orchestration worker failed to start." >&2
  exit 1
fi

cd apps/workbench
npm run dev -- --hostname 127.0.0.1 --port 3001 &
WORKBENCH_PID=$!

echo "GIS local runtime started: API :8001, Workbench :3001, scheduler/worker active."
while kill -0 "$API_PID" 2>/dev/null && kill -0 "$WORKER_PID" 2>/dev/null && kill -0 "$WORKBENCH_PID" 2>/dev/null; do
  sleep 1
done
echo "A GIS local runtime child exited; stopping sibling processes." >&2
exit 1
