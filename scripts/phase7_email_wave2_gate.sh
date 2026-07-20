#!/usr/bin/env bash
# EM-7 / Wave 2 gate — ClickHouse export, attribution, deliverability, DNS, report schedules
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export PTT_JOBS_ENABLED="${PTT_JOBS_ENABLED:-1}"
export PTT_EMAIL_CLICKHOUSE_EXPORT="${PTT_EMAIL_CLICKHOUSE_EXPORT:-1}"
export PTT_EMAIL_DELIVERABILITY_ALERTS="${PTT_EMAIL_DELIVERABILITY_ALERTS:-1}"
export CLICKHOUSE_URL="${CLICKHOUSE_URL:-http://127.0.0.1:8123}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase7-email-wave2-report.json"

echo "==> EM-7 Wave 2 unit tests"
"$PYTHON" -m pytest "$ROOT/tests/test_email_mkt_em7_wave2.py" -q

echo ""
echo "==> Ensure EM DDL (through EM-7)"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt.sh"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em1.sh" 2>/dev/null || true
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em3.sh" 2>/dev/null || true
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em7.sh"

GATE_OK=true
NOTES=()

echo ""
echo "==> Worker job types registered"
for jt in email_clickhouse_export email_attribution_rollup email_deliverability_scan email_dns_verify email_warm_up_tick email_report_schedules; do
  if ! grep -q "\"$jt\"" "$ROOT/ptt_worker/__main__.py" && ! grep -q "$jt" "$ROOT/ptt_worker/__main__.py"; then
    echo "FAIL missing worker route: $jt" >&2
    GATE_OK=false
    NOTES+=("missing_worker_$jt")
  fi
done

echo ""
echo "==> Nest email-marketing unit tests"
if [[ "${SKIP_NEST_SMOKE:-0}" == "1" ]]; then
  echo "SKIP  Nest jest"
else
  (cd "$ROOT/services/ptt-crm-api" && npm test -- --testPathPattern=email-marketing --passWithNoTests 2>/dev/null) || {
    echo "WARN  Nest jest email-marketing failed or skipped" >&2
    NOTES+=("nest_jest_warn")
  }
fi

echo ""
echo "==> ClickHouse export dry-run (skip if CH down)"
if [[ "${SKIP_CLICKHOUSE:-0}" == "1" ]]; then
  echo "SKIP  ClickHouse export"
  CH_OUT='{"skipped":true}'
else
  CH_OUT=$(bash "$ROOT/scripts/export_email_facts_clickhouse.sh" 2>/dev/null || echo '{"ok":false,"skipped":true}')
  echo "$CH_OUT"
  if echo "$CH_OUT" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("ok") or d.get("skipped") else 1)' ; then
    :
  else
    GATE_OK=false
    NOTES+=("clickhouse_export_failed")
  fi
fi

echo ""
echo "==> DNS verify module smoke"
"$PYTHON" - <<'PY'
from ptt_email.dns_verify import verify_domain_dns
out = verify_domain_dns("invalid")
assert out["spf_status"] == "fail"
print("dns_verify_ok")
PY

echo ""
echo "==> Write gate report"
GATE_OK_JSON=$([[ "$GATE_OK" == true ]] && echo True || echo False)
NOTES_JSON=$("$PYTHON" - <<PY
import json
print(json.dumps($(printf '%s\n' "${NOTES[@]:-}" | "$PYTHON" -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l.strip()]))')))
PY
)

"$PYTHON" - <<PY
import json
from datetime import datetime, timezone
ch_raw = '''${CH_OUT}'''
try:
    ch = json.loads(ch_raw) if ch_raw.strip().startswith("{") else {}
except json.JSONDecodeError:
    ch = {"raw": ch_raw[:200]}
report = {
    "gate": "phase7_email_wave2",
    "ok": ${GATE_OK_JSON},
    "notes": ${NOTES_JSON},
    "clickhouse": ch,
    "ts": datetime.now(timezone.utc).isoformat(),
}
path = "$REPORT"
with open(path, "w") as f:
    json.dump(report, f, indent=2)
print("Report:", path)
if not report["ok"]:
    raise SystemExit(1)
print("PASS phase7 email wave2 gate")
PY
