#!/usr/bin/env bash
# SEO/AEO PostgreSQL cutover + GSC/GA4 OAuth enable (production)
#
# Usage (on VPS as deploy, from /var/www/ptt):
#   APPLY=0 ./scripts/seo_aeo_prod_cutover.sh          # dry-run
#   APPLY=1 ./scripts/seo_aeo_prod_cutover.sh          # execute cutover
#
# Requires: DATABASE_URL, .env with OAuth vars, sudo for systemctl restart
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPLY="${APPLY:-0}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "==> SEO/AEO PG cutover (APPLY=$APPLY)"
echo "    Root: $ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "FAIL: DATABASE_URL not set"
  exit 1
fi

echo ""
echo "==> Step 1: Verify PG + env"
"$PYTHON" "$ROOT/scripts/verify_seo_aeo_oauth_uat.py" --skip-oauth || {
  echo "WARN: verification failed — fix before APPLY=1"
  [[ "$APPLY" == "1" ]] && exit 1
}

echo ""
echo "==> Step 2: Apply PG schema (idempotent)"
"$PYTHON" -c "
from ptt_jobs.db import pg_connection
from ptt_seo.pg_schema import ensure_pg_schema, pg_seo_ready
with pg_connection() as pg:
    ensure_pg_schema(pg)
    assert pg_seo_ready(pg), 'schema not ready'
print('OK  PG schema applied')
"

echo ""
echo "==> Step 3: Backfill SQLite seo_* → PG"
if [[ "$APPLY" == "1" ]]; then
  "$PYTHON" "$ROOT/scripts/migrate_sqlite_seo_aeo_to_pg.py"
  "$PYTHON" "$ROOT/scripts/migrate_crm_aeo_to_pg.py" 2>/dev/null || echo "WARN: crm_aeo backfill skipped (no scans)"
else
  "$PYTHON" "$ROOT/scripts/migrate_sqlite_seo_aeo_to_pg.py" --dry-run
  echo "DRY-RUN: skip migrate_crm_aeo_to_pg.py"
fi

echo ""
echo "==> Step 4: Verify row counts"
"$PYTHON" "$ROOT/scripts/migrate_sqlite_seo_aeo_to_pg.py" --verify-only

if [[ "$APPLY" != "1" ]]; then
  echo ""
  echo "DRY-RUN complete. To cutover:"
  echo "  1. Add/update /var/www/ptt/.env:"
  echo "       SEO_AEO_DB=pg"
  echo "       PTT_GSC_SYNC_ENABLED=1"
  echo "       PTT_GA4_SYNC_ENABLED=1"
  echo "       PTT_GSC_OAUTH_* / PTT_GA4_OAUTH_* / PTT_TOKEN_VAULT_KEY"
  echo "  2. Run: APPLY=1 ./scripts/seo_aeo_prod_cutover.sh"
  echo "  3. Follow UAT: docs/runbooks/seo-aeo-pg-oauth-uat-cutover.md"
  exit 0
fi

echo ""
echo "==> Step 5: Enable SEO_AEO_DB=pg in .env"
ENV_FILE="${PTT_ENV_FILE:-$ROOT/.env}"
if grep -q '^SEO_AEO_DB=' "$ENV_FILE" 2>/dev/null; then
  sed -i.bak 's/^SEO_AEO_DB=.*/SEO_AEO_DB=pg/' "$ENV_FILE"
else
  echo 'SEO_AEO_DB=pg' >> "$ENV_FILE"
fi
grep -q '^PTT_GSC_SYNC_ENABLED=' "$ENV_FILE" 2>/dev/null || echo 'PTT_GSC_SYNC_ENABLED=1' >> "$ENV_FILE"
grep -q '^PTT_GA4_SYNC_ENABLED=' "$ENV_FILE" 2>/dev/null || echo 'PTT_GA4_SYNC_ENABLED=1' >> "$ENV_FILE"
echo "OK  .env updated (backup: ${ENV_FILE}.bak)"

echo ""
echo "==> Step 6: Install systemd timers (if not yet)"
if [[ -x "$ROOT/scripts/install_phase3_systemd.sh" ]] && [[ "$(id -u)" -eq 0 ]]; then
  "$ROOT/scripts/install_phase3_systemd.sh"
else
  echo "SKIP: run manually: sudo ./scripts/install_phase3_systemd.sh"
fi

echo ""
echo "==> Step 7: Restart services"
if [[ "$(id -u)" -eq 0 ]]; then
  systemctl restart ptt.service ptt-temporal-worker.service 2>/dev/null || systemctl restart ptt.service
  systemctl start ptt-seo-gsc-sync.timer ptt-seo-ga4-sync.timer ptt-seo-freshness-scan.timer 2>/dev/null || true
  echo "OK  services restarted"
else
  echo "Run as root:"
  echo "  sudo systemctl restart ptt ptt-temporal-worker"
  echo "  sudo systemctl start ptt-seo-gsc-sync.timer ptt-seo-ga4-sync.timer"
fi

echo ""
echo "==> Step 8: Post-cutover verify (PG + counts; OAuth = manual browser UAT)"
export SEO_AEO_DB=pg
"$PYTHON" "$ROOT/scripts/verify_seo_aeo_oauth_uat.py" \
  --customer-id "${PILOT_CUSTOMER_ID:-1}" \
  --skip-oauth

echo ""
echo "DONE — Complete manual UAT per docs/runbooks/seo-aeo-pg-oauth-uat-cutover.md"
