#!/usr/bin/env bash
# Wave B11 — smoke (Nest build + ops-web build with B11 flags on)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PTT_META_ANOMALY_STAT_ENABLED=1
export PTT_META_FORECAST_ENABLED=1
export PTT_META_PIXELS_ENABLED=1
export PTT_META_INTEL_SNAPSHOT_ENABLED=1
export NEXT_PUBLIC_PTT_META_ANOMALY_STAT_ENABLED=1
export NEXT_PUBLIC_PTT_META_FORECAST_ENABLED=1
export NEXT_PUBLIC_PTT_META_PIXELS_ENABLED=1

echo "== B11 Nest unit (meta-intelligence util) =="
cd services/ptt-crm-api
npm test -- --testPathPattern=meta-intelligence.util --passWithNoTests

echo "== B11 ops-web build =="
cd ../ops-web
npm run build

echo "B11 smoke OK"
