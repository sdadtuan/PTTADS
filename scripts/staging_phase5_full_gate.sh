#!/usr/bin/env bash
# Staging full gate — refresh Phase 2/3/4 artifacts → Phase 5 Flask retirement
#
# Usage:
#   ./scripts/staging_phase5_full_gate.sh
#   ./scripts/staging_phase5_full_gate.sh --skip-refresh   # Phase 5 only (prior artifacts must exist)
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export PTT_NEST_LEADS_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
export PHASE5_SKIP_PRIOR_GATES=0

# Local staging overrides (env examples may point at VPS paths)
_local_staging_env() {
  export PTT_SQLITE_PATH="$ROOT/ptt.db"
  export PTT_NEST_LEADS_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
  export PTT_ARTIFACTS_DIR="$ROOT/.local-dev"
}

SKIP_REFRESH=0
EXTRA_PHASE5=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-refresh) SKIP_REFRESH=1 ;;
    --skip-seo-gates) EXTRA_PHASE5+=(--skip-seo-gates) ;;
    -h|--help)
      echo "Usage: staging_phase5_full_gate.sh [--skip-refresh] [--skip-seo-gates]"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
  shift
done

mkdir -p "$PTT_ARTIFACTS_DIR"
SUMMARY="$PTT_ARTIFACTS_DIR/staging-phase5-full-gate-summary.json"

_wait_nest() {
  for _ in $(seq 1 30); do
    if curl -sf "${PTT_NEST_LEADS_URL}/health" >/dev/null 2>&1; then
      echo "OK  Nest → $PTT_NEST_LEADS_URL"
      return 0
    fi
    sleep 2
  done
  echo "FAIL Nest not reachable: $PTT_NEST_LEADS_URL" >&2
  return 1
}

echo "==> Preflight"
_wait_nest
if command -v docker >/dev/null 2>&1; then
  docker compose up -d postgres 2>/dev/null || true
fi

STEPS=()

if [[ "$SKIP_REFRESH" -eq 0 ]]; then
  echo ""
  echo "==> Phase 2 gate pack (refresh artifact)"
  set -a && source "$ROOT/deploy/env.staging-phase2-gates.example" && set +a
  _local_staging_env
  if bash "$ROOT/scripts/staging_phase2_gate_pack.sh" \
    --skip-soak \
    --skip-write-pilot \
    --skip-prod-gates \
    --skip-uat \
    --no-lead-assigned-e2e \
    --report "$PTT_ARTIFACTS_DIR/phase2-ops-gate-report.json"; then
    STEPS+=('phase2:ok')
  else
    STEPS+=('phase2:fail')
    echo "FAIL Phase 2 gate" >&2
    exit 1
  fi

  echo ""
  echo "==> Phase 3 gate pack (refresh artifact)"
  set -a && source "$ROOT/deploy/env.staging-phase3.example" && set +a
  _local_staging_env
  export RUN_PORTAL_E2E="${RUN_PORTAL_E2E:-0}"
  if bash "$ROOT/scripts/staging_phase3_gate_pack.sh" --skip-playwright --skip-build; then
    STEPS+=('phase3:ok')
  else
    STEPS+=('phase3:fail')
    echo "FAIL Phase 3 gate" >&2
    exit 1
  fi

  echo ""
  echo "==> Phase 4 gate pack (refresh artifact)"
  set -a && source "$ROOT/deploy/env.staging-phase4.example" && set +a
  _local_staging_env
  if bash "$ROOT/scripts/staging_phase4_gate_pack.sh"; then
    STEPS+=('phase4:ok')
  else
    STEPS+=('phase4:fail')
    echo "FAIL Phase 4 gate" >&2
    exit 1
  fi
else
  STEPS+=('phase2:skipped' 'phase3:skipped' 'phase4:skipped')
fi

echo ""
echo "==> Phase 5 full gate (prior artifacts required)"
set -a && source "$ROOT/deploy/env.phase5-flask-retire.example" && set +a
_local_staging_env
export PHASE5_SKIP_PRIOR_GATES=0
export PHASE5_SKIP_SOAK=1
export PHASE5_SKIP_PORTAL_SIGNOFF=1
if bash "$ROOT/scripts/staging_phase5_gate_pack.sh" ${EXTRA_PHASE5[@]+"${EXTRA_PHASE5[@]}"}; then
  STEPS+=('phase5:ok')
else
  STEPS+=('phase5:fail')
  echo "FAIL Phase 5 gate" >&2
  exit 1
fi

"$PYTHON" - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("$ROOT")
art = Path("$PTT_ARTIFACTS_DIR")
checks = {}
for name in ("phase2-ops-gate-report.json", "phase3-qa-gate-report.json", "staging-phase4-gate-report.json", "staging-phase5-gate-report.json"):
    p = art / name
    if p.is_file():
        d = json.loads(p.read_text(encoding="utf-8"))
        checks[name] = {"ok": bool(d.get("ok")), "path": str(p)}
    else:
        checks[name] = {"ok": False, "error": "missing"}

summary = {
    "ok": all(v.get("ok") for v in checks.values()),
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "steps": "$(
        IFS=,
        echo "${STEPS[*]}"
    )".split(","),
    "artifacts": checks,
    "notes": "Full staging gate Phase 2→5 with prior artifact validation",
}
out = art / "staging-phase5-full-gate-summary.json"
out.write_text(json.dumps(summary, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
if not summary["ok"]:
    raise SystemExit(1)
PY

echo ""
echo "OK  Full staging gate Phase 2→5 — $SUMMARY"
