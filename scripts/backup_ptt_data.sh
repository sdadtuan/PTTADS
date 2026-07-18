#!/usr/bin/env bash
# Backup SQLite ptt.db + PostgreSQL pg_dump (Phase 2 X-UAT-04)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${PTT_BACKUP_DIR:-/var/backups/ptt}"
RETENTION_DAYS="${PTT_BACKUP_RETENTION_DAYS:-14}"
TS="$(date +%Y%m%d-%H%M)"
mkdir -p "$BACKUP_DIR"

DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
SQLITE_SRC="${PTT_SQLITE_PATH:-${PTT_APP_DIR:-$ROOT}/ptt.db}"

PG_OUT="$BACKUP_DIR/ptt_agency-${TS}.dump"
SQLITE_OUT="$BACKUP_DIR/ptt-${TS}.db"

echo "==> pg_dump → $PG_OUT"
if command -v pg_dump >/dev/null 2>&1; then
  pg_dump "$DATABASE_URL" -Fc -f "$PG_OUT"
elif docker ps --format '{{.Names}}' 2>/dev/null | grep -qx ptt-postgres; then
  docker exec ptt-postgres pg_dump -U ptt -d ptt_agency -Fc > "$PG_OUT"
else
  echo "FAIL: pg_dump not found and ptt-postgres container not running" >&2
  exit 1
fi
test -s "$PG_OUT"

echo "==> sqlite copy → $SQLITE_OUT"
if [[ -f "$SQLITE_SRC" ]]; then
  cp -a "$SQLITE_SRC" "$SQLITE_OUT"
  test -s "$SQLITE_OUT"
else
  echo "WARN: sqlite not found at $SQLITE_SRC — pg_dump only" >&2
fi

if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && [[ "$RETENTION_DAYS" -gt 0 ]]; then
  find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'ptt_agency-*.dump' -o -name 'ptt-*.db' \) -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
fi

echo "OK backup complete: $PG_OUT ${SQLITE_OUT:+ $SQLITE_OUT}"
