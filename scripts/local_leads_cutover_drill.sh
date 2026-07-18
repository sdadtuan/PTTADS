#!/usr/bin/env bash
# Rollback drill — toggle PTT_LEADS_READ_UPSTREAM nest ↔ flask (Phase 1b Bước 8)
#
# Requires: Flask (:5050 or :8002), Nest (:3000), synced PG replica
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

FLASK_URL="${FLASK_URL:-http://127.0.0.1:5050}"
NEST_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_NEST_LEADS_URL="$NEST_URL"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Cutover drill flask=$FLASK_URL nest=$NEST_URL"

check_url() {
  local name="$1" url="$2"
  if curl -sf "$url/health" >/dev/null 2>&1 || curl -sf "$url/healthz" >/dev/null 2>&1; then
    echo "OK  $name reachable"
    return 0
  fi
  echo "FAIL $name not reachable at $url" >&2
  return 1
}

check_url "Nest" "$NEST_URL"
check_url "Flask" "$FLASK_URL"

echo "==> Dual-run (Flask SQLite vs Nest PG)"
"$ROOT/scripts/local_dual_run_check.sh" 10

echo "==> Nest direct GET /api/v1/leads?limit=1"
curl -sf "$NEST_URL/api/v1/leads?limit=1" | head -c 200
echo "..."

echo ""
echo "==> Rollback drill (app-level proxy flag)"
echo "    Set PTT_LEADS_READ_UPSTREAM=nest on Flask → proxy to Nest after session auth"
echo "    Set PTT_LEADS_READ_UPSTREAM=flask → local SQLite read (rollback)"

for mode in nest flask; do
  echo "--- simulate upstream=$mode ---"
  PTT_LEADS_READ_UPSTREAM="$mode" "$PYTHON" -c "
from ptt_crm.config import leads_read_upstream
assert leads_read_upstream() == '$mode', leads_read_upstream()
print('OK  config leads_read_upstream=$mode')
"
done

echo ""
echo "==> Nginx snippet dry-run"
"$ROOT/scripts/apply_leads_read_upstream.sh" --dry-run --dest /tmp/ptt-leads-v1-routing.conf | head -20

echo ""
echo "OK  cutover drill complete"
echo "Prod cutover: see docs/runbooks/cutover-leads-read-b8.md"
