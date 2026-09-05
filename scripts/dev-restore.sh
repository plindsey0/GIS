#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/dev-restore.sh /absolute/path/to/backup.dump" >&2
  exit 2
fi
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_dir"
backup_path="$1"
[[ "$backup_path" = /* ]] || { echo "Backup path must be absolute." >&2; exit 2; }
[[ -s "$backup_path" ]] || { echo "Backup archive is missing or empty." >&2; exit 2; }

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
case "${GIS_ENVIRONMENT:-development}" in
  development|local_development) ;;
  *) echo "Refusing restore outside a local-development environment." >&2; exit 2 ;;
esac
database="$(.venv/bin/python -c 'import os; from sqlalchemy.engine import make_url; print(make_url(os.environ["DATABASE_URL"]).database)')"
[[ "$database" == "gis" ]] || { echo "Refusing restore to database $database." >&2; exit 2; }
docker compose exec -T db pg_restore --list < "$backup_path" >/dev/null

echo "This will replace the local development database 'gis' from: $backup_path"
read -r -p "Type RESTORE gis to continue: " confirmation
[[ "$confirmation" == "RESTORE gis" ]] || { echo "Restore cancelled."; exit 2; }

# Create and verify a safety archive of the current state before replacement.
backup_dir="${GIS_BACKUP_DIR:-$HOME/.local/share/gis/backups}"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
current_backup="$backup_dir/gis-pre-restore-$stamp.dump"
docker compose exec -T db pg_dump --username="${GIS_DB_USER:-gis}" --dbname=gis --format=custom > "$current_backup"
test -s "$current_backup"
docker compose exec -T db pg_restore --list < "$current_backup" >/dev/null
chmod 600 "$current_backup"

docker compose exec -T db pg_restore --clean --if-exists --no-owner --username="${GIS_DB_USER:-gis}" --dbname=gis < "$backup_path"
.venv/bin/alembic current
.venv/bin/alembic check
echo "Restore complete. Pre-restore safety archive: $current_backup"
