#!/usr/bin/env bash
# Apply nginx static alias for ops-web (fixes blank pages when /_next/static 404).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo $0"
  exit 1
fi

"$ROOT/scripts/patch_nginx_rs_static.sh"

STATIC="$ROOT/services/ops-web/.next/standalone/.next/static/css"
if [[ -d "$STATIC" ]]; then
  css="$(basename "$(ls "$STATIC"/*.css | head -1)")"
  echo "Probe: curl -sI https://rs.pttads.vn/_next/static/css/$css"
else
  echo "WARN  static not built yet — run ./scripts/wave_b1_rebuild_ops_web.sh as deploy first"
fi
