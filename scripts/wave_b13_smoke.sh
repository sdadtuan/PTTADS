#!/usr/bin/env bash
# Wave B13 — smoke: parse fixture + stub process (no PG)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

python3 - <<'PY'
import json
from pathlib import Path

from ptt_meta.ops_webhooks import parse_ops_webhook_changes, process_ops_webhook_event

fixture = Path("tests/fixtures/channels/meta/webhook_account_disabled.json")
payload = json.loads(fixture.read_text(encoding="utf-8"))
events = parse_ops_webhook_changes(payload)
assert len(events) == 1, events
out = process_ops_webhook_event(events[0], client_id="00000000-0000-4000-8000-000000000001", stub=True)
assert out["ok"] and out["stub"]
print("B13 smoke OK:", out["alert_type"], out["message"][:60])
PY
