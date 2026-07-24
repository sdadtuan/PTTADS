#!/usr/bin/env bash
# Wave B14 — smoke: stub warehouse export
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

python3 - <<'PY'
from ptt_meta.warehouse_export import export_meta_facts_to_clickhouse

out = export_meta_facts_to_clickhouse(fact_date="2026-07-20", stub=True)
assert out["ok"] and out["stub"]
print("B14 smoke OK: stub rows=", out.get("rows", 0))
PY
