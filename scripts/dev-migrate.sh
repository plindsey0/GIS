#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

case "${GIS_ENVIRONMENT:-development}" in
  development|local_development) ;;
  *) echo "Refusing development migration outside a local-development environment." >&2; exit 2 ;;
esac

identity="$(.venv/bin/python -c 'import os; from sqlalchemy.engine import make_url; u=make_url(os.environ["DATABASE_URL"]); print(f"{u.host}:{u.port}/{u.database}")')"
database="$(.venv/bin/python -c 'import os; from sqlalchemy.engine import make_url; print(make_url(os.environ["DATABASE_URL"]).database)')"
if [[ "$database" != "gis" ]]; then
  echo "Refusing: this repository workflow expects the local development database named gis, got $database." >&2
  exit 2
fi

backup_dir="${GIS_BACKUP_DIR:-$HOME/.local/share/gis/backups}"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
revision="$(.venv/bin/alembic current 2>/dev/null | tail -1 | awk '{print $1}')"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="$backup_dir/gis-pre-migration-$stamp-${revision:-unknown}.dump"

echo "Creating verified pre-migration backup for $identity"
docker compose exec -T db pg_dump --username="${GIS_DB_USER:-gis}" --dbname="$database" --format=custom > "$backup_path"
test -s "$backup_path"
docker compose exec -T db pg_restore --list < "$backup_path" >/dev/null
chmod 600 "$backup_path"

# Retain the newest 20 verified migration backups. Never remove this run's archive.
ls -1t "$backup_dir"/gis-pre-migration-*.dump 2>/dev/null | awk 'NR > 20' | while IFS= read -r old_backup; do
  [[ "$old_backup" == "$backup_path" ]] || rm -- "$old_backup"
done

echo "Backup verified: $backup_path"
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic check
echo "Development migration complete. Recovery archive: $backup_path"
