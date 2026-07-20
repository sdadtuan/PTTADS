#!/usr/bin/env bash
# EM-8b / Wave 3b gate — segment builder, template studio, toast, portal approval modal
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase8b-email-wave3b-report.json"

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

echo "==> Wave 3b components"
for f in \
  services/ops-web/src/lib/toast.tsx \
  services/ops-web/src/components/email/SegmentBuilder.tsx \
  services/ops-web/src/components/email/TemplateBlockLibrary.tsx \
  services/portal-web/src/lib/toast.tsx \
  services/portal-web/src/lib/email-a11y.ts \
  services/portal-web/src/components/email/EmailApprovalCard.tsx \
  services/ops-web/src/app/providers.tsx \
  services/portal-web/src/app/providers.tsx
do
  check_file "$f" "missing_$f"
done

echo ""
echo "==> Nest PATCH segment API"
if grep -q "patchSegment" "$ROOT/services/ptt-crm-api/src/email-marketing/email-marketing.controller.ts"; then
  echo "OK  PATCH segments/:id"
else
  echo "FAIL PATCH segment endpoint" >&2
  GATE_OK=false
  NOTES+=("patch_segment_api")
fi

echo ""
echo "==> CSS wave 3b"
if grep -q '.email-toast-stack' "$ROOT/services/ops-web/src/app/globals.css"; then
  echo "OK  toast CSS ops-web"
else
  GATE_OK=false
  NOTES+=("toast_css_ops")
fi

if grep -q '.email-segment-builder' "$ROOT/services/ops-web/src/app/globals.css"; then
  echo "OK  segment builder CSS"
else
  GATE_OK=false
  NOTES+=("segment_builder_css")
fi

echo ""
echo "==> Layout providers"
if grep -q 'Providers' "$ROOT/services/ops-web/src/app/layout.tsx"; then
  echo "OK  ops-web ToastProvider"
else
  GATE_OK=false
  NOTES+=("ops_providers")
fi

if grep -q 'Providers' "$ROOT/services/portal-web/src/app/layout.tsx"; then
  echo "OK  portal-web ToastProvider"
else
  GATE_OK=false
  NOTES+=("portal_providers")
fi

echo ""
echo "==> Frontend build"
if [[ "${SKIP_OPS_WEB_BUILD:-0}" == "1" ]]; then
  echo "SKIP  ops-web build"
else
  (cd "$ROOT/services/ops-web" && npm run build 2>/dev/null) || {
    echo "FAIL ops-web build" >&2
    GATE_OK=false
    NOTES+=("ops_web_build_fail")
  }
fi

if [[ "${SKIP_PORTAL_WEB_BUILD:-0}" == "1" ]]; then
  echo "SKIP  portal-web build"
else
  (cd "$ROOT/services/portal-web" && npm run build 2>/dev/null) || {
    echo "FAIL portal-web build" >&2
    GATE_OK=false
    NOTES+=("portal_web_build_fail")
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
    "gate": "phase8b_email_wave3b",
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
print("PASS phase8b email wave3b gate")
PY
