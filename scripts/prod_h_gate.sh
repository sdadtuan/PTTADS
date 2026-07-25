#!/usr/bin/env bash
# PROD-H-GATE — production hardening gate pack (Prod-S4)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== PROD-H production hardening gate =="
python3 -m ptt_crm.prod_h_gates "$@"
