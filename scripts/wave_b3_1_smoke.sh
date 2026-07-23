#!/usr/bin/env bash
# Wave B3.1 smoke — Meta webhook Nest (challenge + POST lead + page resolution fields).
# Usage:
#   ./scripts/wave_b3_1_smoke.sh
#   BASE=http://127.0.0.1:3000 CLIENT_ID=<uuid> ./scripts/wave_b3_1_smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:3000}"
CLIENT_ID="${CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

VERIFY_TOKEN="${CRM_FACEBOOK_VERIFY_TOKEN:-${FACEBOOK_VERIFY_TOKEN:-test-meta-verify}}"
FB_SECRET="${CRM_FACEBOOK_APP_SECRET:-${FACEBOOK_APP_SECRET:-}}"

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

# Nest verifyFacebookSignature requires X-Hub-Signature-256 when App Secret is set (.env VPS).
meta_sig_curl_args() {
  local payload="$1"
  if [[ -z "$FB_SECRET" ]]; then
    return 0
  fi
  local sig
  sig="$(FB_SECRET="$FB_SECRET" python3 -c "
import hmac, hashlib, os, sys
secret = os.environ['FB_SECRET']
body = sys.argv[1].encode('utf-8')
print('sha256=' + hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest())
" "$payload")"
  printf '%s\n' -H "X-Hub-Signature-256: $sig"
}

echo "== Wave B3.1 smoke BASE=$BASE =="

# channels routing
channels_resp="$(mktemp)"
channels_code="$(curl -s -o "$channels_resp" -w "%{http_code}" "$BASE/api/v1/channels")"
if [[ "$channels_code" == "200" ]]; then
  routing="$(python3 -c "import json; print(json.load(open('$channels_resp')).get('routing',{}).get('meta',''))")"
  if [[ "$routing" == "nest" ]]; then
    ok "GET /api/v1/channels routing.meta=nest"
  else
    bad "routing.meta=$routing (expected nest) — bật PTT_WEBHOOKS_NEST_META=1"
  fi
else
  bad "GET /api/v1/channels (HTTP $channels_code)"
fi
rm -f "$channels_resp"

# hub challenge
ch_body="$(curl -sf "$BASE/api/v1/webhooks/meta?hub.mode=subscribe&hub.verify_token=$VERIFY_TOKEN&hub.challenge=b31-smoke" || true)"
if [[ "$ch_body" == "b31-smoke" ]]; then
  ok "GET meta hub challenge"
else
  bad "hub challenge body='$ch_body' (expected b31-smoke)"
fi

# flat lead POST (legacy/dev payload)
flat_payload='{"full_name":"B3.1 smoke","phone":"0908111222","email":"b31@test.local","meta":{"facebook_leadgen_id":"b31-smoke-flat-001"}}'
flat_resp="$(mktemp)"
flat_sig=()
while IFS= read -r line; do flat_sig+=("$line"); done < <(meta_sig_curl_args "$flat_payload")
flat_code="$(curl -s -o "$flat_resp" -w "%{http_code}" -X POST "$BASE/api/v1/webhooks/meta" \
  -H 'Content-Type: application/json' \
  -H "X-PTT-Client-Id: $CLIENT_ID" \
  "${flat_sig[@]}" \
  -d "$flat_payload")"
if [[ "$flat_code" == "200" ]]; then
  ok "POST meta flat lead (HTTP 200)"
  python3 -c "
import json, sys
b = json.load(open('$flat_resp'))
assert b.get('verified') is True, b
assert b.get('handler') == 'nest', b
assert b.get('accepted') is True, b
print('accepted mode=' + str(b.get('mode')))
"
else
  bad "POST meta flat lead (HTTP $flat_code) $(head -c 200 "$flat_resp" | tr '\n' ' ')"
fi
rm -f "$flat_resp"

# standard leadgen webhook shape (Graph fetch may be pending without token)
leadgen_payload='{"object":"page","entry":[{"id":"123456789012345","changes":[{"field":"leadgen","value":{"leadgen_id":"b31-smoke-lg-001","form_id":"2814926042203269","page_id":"123456789012345"}}]}]}'
lg_resp="$(mktemp)"
lg_sig=()
while IFS= read -r line; do lg_sig+=("$line"); done < <(meta_sig_curl_args "$leadgen_payload")
lg_code="$(curl -s -o "$lg_resp" -w "%{http_code}" -X POST "$BASE/api/v1/webhooks/meta" \
  -H 'Content-Type: application/json' \
  "${lg_sig[@]}" \
  -d "$leadgen_payload")"
if [[ "$lg_code" == "200" ]]; then
  ok "POST meta leadgen payload (HTTP 200)"
  python3 -c "
import json
b = json.load(open('$lg_resp'))
assert b.get('verified') is True, b
assert '123456789012345' in (b.get('page_ids') or []), b
print('page_ids=' + str(b.get('page_ids')))
"
else
  bad "POST meta leadgen (HTTP $lg_code) $(head -c 200 "$lg_resp" | tr '\n' ' ')"
fi
rm -f "$lg_resp"

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B3.1 smoke PASSED"
  echo "Tip: map Page ID trên Agency → Kênh ads → Facebook Page ID để resolve client khi không có X-PTT-Client-Id"
  exit 0
fi
echo "Wave B3.1 smoke FAILED — journalctl -u ptt-crm-api -n 80 --no-pager"
exit 1
