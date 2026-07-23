#!/usr/bin/env bash
# Verify production nginx redirect: /crm/facebook-ads → ops-web (Horizon 1 B3.4 / M1-G06).
#
# Usage:
#   ./scripts/verify_meta_ads_nginx_redirect.sh
#   HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0 ./scripts/verify_meta_ads_nginx_redirect.sh
#   PTT_RS_BASE_URL=https://rs.pttads.vn ./scripts/verify_meta_ads_nginx_redirect.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

RS="${PTT_RS_BASE_URL:-https://rs.pttads.vn}"
OPS="${PTT_OPS_WEB_URL:-https://ops.pttads.vn}"
SKIP_LIVE="${HORIZON1_SKIP_NGINX_REDIRECT_VERIFY:-1}"

echo "== Meta Ads nginx redirect verify (M1-G06) =="
echo "RS=$RS OPS=$OPS SKIP_LIVE=$SKIP_LIVE"

"$PYTHON" - <<'PY'
import json
import os
import sys
from ptt_crm.meta_ads_nginx_redirect import (
    nginx_redirect_status,
    verify_legacy_routes_unbroken,
    verify_nginx_redirect_gate,
)

status = nginx_redirect_status(include_live=os.environ.get("HORIZON1_SKIP_NGINX_REDIRECT_VERIFY", "1") != "1")
gate = verify_nginx_redirect_gate()
print(json.dumps({"gate": gate, "status": status}, indent=2))
if os.environ.get("HORIZON1_SKIP_NGINX_REDIRECT_VERIFY", "1") != "1":
    legacy = verify_legacy_routes_unbroken()
    print(json.dumps({"legacy_routes": legacy}, indent=2))
    if not legacy.get("ok"):
        sys.exit(1)
sys.exit(0 if gate.get("ok") else 1)
PY

if [[ "$SKIP_LIVE" == "0" ]]; then
  echo ""
  echo "-- curl spot-check --"
  for path in /crm/facebook-ads /crm/facebook-ads/; do
    code="$(curl -sfI "${RS}${path}" -o /tmp/meta-redir.headers -w '%{http_code}' || true)"
    loc="$(grep -i '^location:' /tmp/meta-redir.headers 2>/dev/null | tr -d '\r' | cut -d' ' -f2- || true)"
    if [[ "$code" =~ ^30[1278]$ ]] && [[ "$loc" == *"${OPS}/meta/facebook-ads"* ]]; then
      echo "OK  ${path} → $code $loc"
    else
      echo "FAIL ${path} → HTTP $code location=${loc:-<none>}" >&2
      exit 1
    fi
  done
  rm -f /tmp/meta-redir.headers
fi

echo ""
echo "M1-G06 nginx redirect verify PASSED"
