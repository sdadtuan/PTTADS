#!/usr/bin/env bash
# Local Phase 5 stack — Nest + ops-web + portal (Flask optional / retired simulation)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_FLASK_MONOLITH_MODE="${PTT_FLASK_MONOLITH_MODE:-retired}"
export PTT_WEBHOOKS_FLASK_FALLBACK=0
export PTT_PORTAL_SEO_ENABLED=1
export PTT_LEADS_WRITE_SOURCE=pg
export PTT_LEAD_INGEST_RULES_SOURCE=pg

MODE="${1:-gate}"

case "$MODE" in
  gate)
    set -a && source "$ROOT/deploy/env.phase5-flask-retire.example" && set +a
    export PHASE5_SKIP_PRIOR_GATES=1
    export PHASE5_SKIP_SOAK=1
    export PHASE5_SKIP_PORTAL_SIGNOFF=1
    "$ROOT/scripts/staging_phase5_gate_pack.sh" --skip-seo-gates
    ;;
  nest)
    exec "$ROOT/scripts/local_crm_api_up.sh"
    ;;
  ops)
    exec "$ROOT/scripts/local_ops_up.sh"
    ;;
  *)
    echo "Usage: staging_phase5_up.sh [gate|nest|ops]"
    exit 1
    ;;
esac
