#!/usr/bin/env bash
# Wave B5 sign-off — automated gate + pytest parity → evidence JSON
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ART="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
mkdir -p "$ART"
EVIDENCE="$ART/wave-b5-signoff-evidence.json"
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

gate_ok=0
pytest_ok=0

echo "== Wave B5 sign-off =="

if bash "$ROOT/scripts/wave_b5_gate.sh"; then
  gate_ok=1
  echo "OK  wave_b5_gate"
else
  echo "FAIL wave_b5_gate" >&2
fi

if bash "$ROOT/scripts/wave_b5_pytest_parity.sh"; then
  pytest_ok=1
  echo "OK  wave_b5_pytest_parity"
else
  echo "FAIL wave_b5_pytest_parity" >&2
fi

python3 - <<PY
import json
from pathlib import Path

out = Path("$EVIDENCE")
payload = {
    "wave": "b5",
    "generated_at": "$TS",
    "gate_ok": bool($gate_ok),
    "pytest_parity_ok": bool($pytest_ok),
    "ok": bool($gate_ok) and bool($pytest_ok),
    "artifacts": {
        "gate_report": str(Path("$ART") / "wave-b5-gate-report.json"),
    },
    "manual_uat": "docs/runbooks/wave-b5-po-signoff-checklist.md",
}
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"evidence": str(out), "ok": payload["ok"]}, ensure_ascii=False))
PY

if [[ "$gate_ok" -eq 1 && "$pytest_ok" -eq 1 ]]; then
  echo "Wave B5 sign-off automation PASSED → $EVIDENCE"
  exit 0
fi
echo "Wave B5 sign-off automation FAILED → $EVIDENCE"
exit 1
