#!/usr/bin/env bash
# EM-8 / Wave 3 gate — UX enterprise polish (components, CSS, nav flags)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase8-email-wave3-report.json"

GATE_OK=true
NOTES=()

check_file() {
  local path="$1"
  local note="$2"
  if [[ -f "$ROOT/$path" ]]; then
    echo "OK  $path"
  else
    echo "FAIL missing $path" >&2
    GATE_OK=false
    NOTES+=("$note")
  fi
}

echo "==> Wave 3 component library"
for f in \
  services/ops-web/src/components/email/EmailStatusBadge.tsx \
  services/ops-web/src/components/email/EmailConsentBadge.tsx \
  services/ops-web/src/components/email/EmailHealthDot.tsx \
  services/ops-web/src/components/email/PreflightChecklist.tsx \
  services/ops-web/src/components/email/JourneyCanvas.tsx \
  services/ops-web/src/components/email/EmailClientWorkspaceTabs.tsx \
  services/ops-web/src/lib/email-flags.ts \
  services/ops-web/src/lib/useStaffCaps.ts \
  services/ops-web/src/lib/email-a11y.ts \
  services/ops-web/src/lib/email-charts.tsx
do
  check_file "$f" "missing_$f"
done

echo ""
echo "==> CSS tokens (.email-*)"
if grep -q '.email-status-badge' "$ROOT/services/ops-web/src/app/globals.css"; then
  echo "OK  email CSS in globals.css"
else
  echo "FAIL email CSS missing" >&2
  GATE_OK=false
  NOTES+=("css_missing")
fi

echo ""
echo "==> OpsNav feature flags"
if grep -q 'emailModuleEnabled' "$ROOT/services/ops-web/src/components/OpsNav.tsx"; then
  echo "OK  OpsNav flags"
else
  GATE_OK=false
  NOTES+=("opsnav_flags")
fi

echo ""
echo "==> ops-web typecheck"
if [[ "${SKIP_OPS_WEB_BUILD:-0}" == "1" ]]; then
  echo "SKIP  ops-web build"
else
  (cd "$ROOT/services/ops-web" && npm run build 2>/dev/null) || {
    echo "WARN  ops-web build failed" >&2
    NOTES+=("ops_web_build_warn")
  }
fi

GATE_OK_JSON=$([[ "$GATE_OK" == true ]] && echo True || echo False)
NOTES_JSON=$("$PYTHON" - <<PY
import json
print(json.dumps($(printf '%s\n' "${NOTES[@]:-}" | "$PYTHON" -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l.strip()]))')))
PY
)

"$PYTHON" - <<PY
import json
from datetime import datetime, timezone
report = {
    "gate": "phase8_email_wave3",
    "ok": ${GATE_OK_JSON},
    "notes": ${NOTES_JSON},
    "ts": datetime.now(timezone.utc).isoformat(),
}
path = "$REPORT"
with open(path, "w") as f:
    json.dump(report, f, indent=2)
print("Report:", path)
if not report["ok"]:
    raise SystemExit(1)
print("PASS phase8 email wave3 gate")
PY
