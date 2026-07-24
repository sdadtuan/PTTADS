#!/usr/bin/env bash
# B9 pilot preflight — verify env + PG before enabling CAPI on 1–2 clients
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }
warn() { echo "WARN $*"; }

echo "== B9 tracking pilot preflight =="

[[ -n "${DATABASE_URL:-}" ]] && ok "DATABASE_URL set" || bad "DATABASE_URL missing"

if [[ "${PTT_META_TRACKING_ENABLED:-0}" == "1" ]]; then
  ok "PTT_META_TRACKING_ENABLED=1"
else
  bad "PTT_META_TRACKING_ENABLED must be 1 for pilot"
fi

if [[ "${PTT_CAPI_ENABLED:-0}" == "1" || "${PTT_CAPI_STUB:-0}" == "1" ]]; then
  ok "CAPI dispatch enabled (real or stub)"
else
  bad "Set PTT_CAPI_ENABLED=1 (prod pilot) or PTT_CAPI_STUB=1 (staging)"
fi

pilots="${PTT_CAPI_PILOT_CLIENTS:-}"
if [[ -n "$pilots" ]]; then
  count="$(python3 -c "print(len([p for p in '''$pilots'''.split(',') if p.strip()]))")"
  if [[ "$count" -ge 1 && "$count" -le 2 ]]; then
    ok "PTT_CAPI_PILOT_CLIENTS has $count client(s)"
  elif [[ "$count" -gt 2 ]]; then
    warn "PTT_CAPI_PILOT_CLIENTS has $count clients — plan recommends 1–2 for initial pilot"
    ok "pilot allowlist present"
  else
    bad "PTT_CAPI_PILOT_CLIENTS empty — set 1–2 UUIDs for pilot"
  fi
else
  bad "PTT_CAPI_PILOT_CLIENTS empty — set 1–2 UUIDs for pilot"
fi

ddl_ok="$("$PYTHON" -c "
from ptt_crm.pg_schema import pg_meta_conversion_rules_ready
import os
ok = pg_meta_conversion_rules_ready()
db = (os.environ.get('DATABASE_URL') or '').strip()
if ok and db:
    import psycopg2
    conn = psycopg2.connect(db)
    cur = conn.cursor()
    cur.execute(\"SELECT 1 FROM information_schema.tables WHERE table_name='capi_event_log' LIMIT 1\")
    ok = cur.fetchone() is not None
    cur.close()
    conn.close()
print('1' if ok else '0')
" 2>/dev/null || echo 0)"
if [[ "$ddl_ok" == "1" ]]; then
  ok "PG v5 conversion + capi_event_log ready"
else
  bad "Apply DDL: ./scripts/apply_pg_ddl_v5_meta_conversion.sh (+ v3 performance)"
fi

echo ""
echo "-- Wave B9 gate (fast) --"
WAVE_B9_SKIP_BUILD=1 WAVE_B9_SKIP_JEST=1 WAVE_B9_SKIP_E2E=1 WAVE_B9_SKIP_SOAK=1 WAVE_B9_SKIP_B8_GATE=1 \
  "$PYTHON" -m ptt_crm.wave_b9_gates >/dev/null && ok "wave_b9_gates (unit checks)" || bad "wave_b9_gates"

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "B9 pilot preflight PASSED"
  echo "Next: ./scripts/wave_b9_smoke.sh with B9_SMOKE_CLIENT_ID=<pilot-uuid>"
  echo "Daily soak: ./scripts/b9_tracking_soak_record.sh (30d)"
  exit 0
fi
echo "B9 pilot preflight FAILED"
exit 1
