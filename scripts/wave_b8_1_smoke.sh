#!/usr/bin/env bash
# Wave B8.1 — smoke (Nest RBAC util + ops-web build)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PTT_META_INSIGHTS_BREAKDOWN=1
export NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN=1

echo "== B8.1 Nest unit (meta-rbac + breakdown service compile) =="
cd services/ptt-crm-api
npm test -- --testPathPattern="meta-rbac|meta-intelligence" --passWithNoTests

echo "== B8.1 ops-web build =="
cd ../ops-web
npm run build

echo "B8.1 smoke OK"
