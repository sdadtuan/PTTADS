#!/usr/bin/env bash
# Phase 2 cutover — Phase 1 + agency API → Nest + write upstream nest
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=0
RELOAD=0
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; EXTRA_ARGS+=(--dry-run) ;;
    --reload) RELOAD=1; EXTRA_ARGS+=(--reload) ;;
    -h|--help)
      echo "Usage: apply_phase2_cutover.sh [--dry-run] [--reload]"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

echo "==> Phase 2 cutover: agency + Meta closed-loop on ops-web / Nest"
"$ROOT/scripts/apply_phase1_cutover.sh" "${EXTRA_ARGS[@]}"

AGENCY_SNIPPET="${NGINX_AGENCY_SNIPPET:-/etc/nginx/snippets/ptt-agency-v1-routing.conf}"
SRC="$ROOT/deploy/nginx-agency-v1-upstream-nest.conf"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "--- dry-run agency nest snippet ---"
  cat "$SRC"
else
  echo "==> agency API nest → $AGENCY_SNIPPET"
  sudo cp "$SRC" "$AGENCY_SNIPPET"
  if [[ "$RELOAD" -eq 1 ]]; then
    sudo nginx -t
    sudo systemctl reload nginx
    echo "OK  nginx reloaded (agency nest)"
  fi
fi

echo ""
echo "==> Phase 2 ingest rules snapshot (PG — no SQLite reads on worker ingest)"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "  would run: ./scripts/sync_lead_ingest_config.sh"
  echo "  would run: ./scripts/phase2_gate_prereq.sh"
else
  "$ROOT/scripts/apply_pg_ddl_v3_leads_ingest_config.sh" || true
  "$ROOT/scripts/sync_lead_ingest_config.sh"
  "$ROOT/scripts/phase2_gate_prereq.sh" || {
    echo "WARN  phase2_gate_prereq failed — fix before prod traffic" >&2
  }
fi

echo ""
echo "Env (deploy/env.phase2-prod.example):"
echo "  PTT_LEADS_WRITE_SOURCE=pg"
echo "  PTT_LEADS_WRITE_UPSTREAM=nest"
echo "  PTT_LEAD_SHADOW_SYNC=1"
echo "  PTT_LEAD_INGEST_RULES_SOURCE=pg"
echo "  PTT_META_INSIGHTS_SYNC=1"
echo ""
echo "Shadow sync timer: ./scripts/install_phase2_systemd_timers.sh"
echo "Manual shadow: PTT_LEAD_SHADOW_SYNC=1 ./scripts/sync_lead_shadow.sh incremental"
echo ""
echo "Restart: ptt-crm-api ptt-worker ops-web"
echo "Hub map seed: ./scripts/sync_hub_campaign_map.sh"
echo "Meta sync: ./scripts/sync_meta_insights.sh"
