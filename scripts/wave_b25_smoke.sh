#!/usr/bin/env bash
# Wave B2.5 smoke — hub_campaign_map CRUD (POST/PATCH/DELETE + client-scoped routes).
# Usage:
#   ADMIN_PASSWORD='...' CLIENT_ID=<uuid> ./scripts/wave_b25_smoke.sh
#   BASE=http://127.0.0.1:3000 CLIENT_ID=... ADMIN_PASSWORD='...' ./scripts/wave_b25_smoke.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
CLIENT_ID="${CLIENT_ID:-}"
TEST_CAMPAIGN_ID="${TEST_CAMPAIGN_ID:-99988877766}"

if [[ -z "$PASS" ]]; then
  echo "Set ADMIN_PASSWORD (from /var/www/ptt/.env)" >&2
  exit 1
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B2.5 smoke BASE=$BASE =="

TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
)"
if [[ -z "$TOKEN" ]]; then
  echo "FAIL login" >&2
  exit 1
fi
ok "staff login"

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

if [[ -z "$CLIENT_ID" ]]; then
  CLIENT_ID="$(
    curl -sf "$BASE/api/v1/clients?limit=1" "${AUTH[@]}" \
    | python3 -c "import sys,json; cs=json.load(sys.stdin).get('clients') or []; print(cs[0]['id'] if cs else '')"
  )"
fi

if [[ -z "$CLIENT_ID" ]]; then
  echo "FAIL no CLIENT_ID — tạo client trước hoặc set CLIENT_ID=" >&2
  exit 1
fi
ok "client id=$CLIENT_ID"

# Cleanup prior smoke row if any
maps_json="$(curl -sf "$BASE/api/v1/clients/$CLIENT_ID/hub-campaign-maps?include_inactive=1" "${AUTH[@]}")"
old_map_id="$(
  echo "$maps_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('maps') or []:
    if str(m.get('external_campaign_id') or '') == '$TEST_CAMPAIGN_ID':
        print(m.get('map_id') or '')
        break
"
)"
if [[ -n "$old_map_id" ]]; then
  curl -sf -X DELETE "$BASE/api/v1/clients/$CLIENT_ID/hub-campaign-maps/$old_map_id" "${AUTH[@]}" >/dev/null || true
  ok "cleaned prior smoke map"
fi

# POST (client-scoped)
create_body="$(python3 -c "import json; print(json.dumps({'channel':'meta','external_campaign_id':'$TEST_CAMPAIGN_ID','external_campaign_name':'Wave B2.5 smoke','target_cpl_vnd':150000}))")"
create_resp="$(mktemp)"
create_code="$(curl -s -o "$create_resp" -w "%{http_code}" -X POST \
  "$BASE/api/v1/clients/$CLIENT_ID/hub-campaign-maps" "${AUTH[@]}" -d "$create_body")"
if [[ "$create_code" =~ ^2 ]]; then
  ok "POST client hub-campaign-maps (HTTP $create_code)"
  MAP_ID="$(python3 -c "import json; print(json.load(open('$create_resp')).get('map',{}).get('map_id',''))")"
  HUB_ID="$(python3 -c "import json; print(json.load(open('$create_resp')).get('map',{}).get('hub_campaign_id',''))")"
  [[ -n "$MAP_ID" ]] && ok "map_id=$MAP_ID hub_campaign_id=$HUB_ID" || bad "POST missing map_id"
else
  bad "POST client hub-campaign-maps (HTTP $create_code) $(head -c 200 "$create_resp" | tr '\n' ' ')"
  MAP_ID=""
fi
rm -f "$create_resp"

# GET list
list_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/clients/$CLIENT_ID/hub-campaign-maps" "${AUTH[@]}")"
[[ "$list_code" =~ ^2 ]] && ok "GET client hub-campaign-maps (HTTP $list_code)" || bad "GET client hub-campaign-maps (HTTP $list_code)"

# GET global filter
glob_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/crm/hub-campaign-maps?client_id=$CLIENT_ID" "${AUTH[@]}")"
[[ "$glob_code" =~ ^2 ]] && ok "GET global hub-campaign-maps?client_id= (HTTP $glob_code)" || bad "GET global (HTTP $glob_code)"

if [[ -n "${MAP_ID:-}" ]]; then
  patch_code="$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
    "$BASE/api/v1/clients/$CLIENT_ID/hub-campaign-maps/$MAP_ID" "${AUTH[@]}" \
    -d '{"external_campaign_name":"Smoke updated","target_cpl_vnd":160000}')"
  [[ "$patch_code" =~ ^2 ]] && ok "PATCH client hub-campaign-maps/:mapId (HTTP $patch_code)" || bad "PATCH (HTTP $patch_code)"

  del_code="$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
    "$BASE/api/v1/clients/$CLIENT_ID/hub-campaign-maps/$MAP_ID" "${AUTH[@]}" -d '{}')"
  [[ "$del_code" =~ ^2 ]] && ok "DELETE client hub-campaign-maps/:mapId (HTTP $del_code)" || bad "DELETE (HTTP $del_code)"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B2.5 smoke PASSED"
  exit 0
fi
echo "Wave B2.5 smoke FAILED — journalctl -u ptt-crm-api -n 80 --no-pager"
exit 1
