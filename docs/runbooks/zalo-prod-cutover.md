# Runbook — Zalo production cutover (Prod-S3 / PROD-P0-ZALO)

> **Mục tiêu:** Zalo Ads chạy prod thật — OAuth vault, insights T-1, form poll ≤15 phút, không stub banner.

## Pre-requisites

- [ ] DDL Z1–Z3 + leads applied (`apply_pg_ddl_zalo_*`)
- [ ] `PTT_TOKEN_VAULT_KEY` trên VPS
- [ ] Zalo App OAuth redirect URI khớp Nest callback
- [ ] `ptt-worker` + cron form poll active

## Env prod

```bash
set -a && source deploy/env.zalo-prod.example && set +a
```

| Flag | Prod value |
|------|------------|
| `PTT_ZALO_ADS_STUB` | `0` |
| `PTT_ZALO_ADS_PILOT` | `0` (hoặc scoped allowlist) |
| `PTT_ZALO_INSIGHTS_SYNC` | `1` |
| `PTT_ZALO_FORM_POLL` | `1` |
| `PTT_ZALO_FORM_POLL_SLA` | `1` |
| `PTT_ZALO_TOKEN_REFRESH` | `1` |
| `PTT_ZALO_ALERTS_ENABLED` | `1` |

## Gate

```bash
chmod +x scripts/zalo_prod_cutover_gate.sh
ZALO_PROD_ENV=deploy/env.zalo-prod.example ./scripts/zalo_prod_cutover_gate.sh
```

Acceptance **A3:** hub sync green T-1, **không** stub banner trên ops-web `/zalo/zalo-ads`.

## OAuth connect (AM)

1. Agency Ops → Client → tab **Kênh ads**
2. Thêm channel **Zalo** → **Connect Zalo OAuth**
3. Verify `token_status=valid` và refresh_token lưu vault

## Workers / cron

| Job | Trigger |
|-----|---------|
| `zalo_insights_sync` | Manual Sync + cron T+1 |
| `zalo_form_lead_poll` | `scripts/cron_zalo_form_lead_poll.sh` mỗi 5–15 phút |
| `zalo_form_poll_sla` | `scripts/cron_zalo_form_poll_sla.sh` mỗi 15 phút |
| `zalo_token_refresh` | Daily timer (mirror Meta) |
| `zalo_alerts_eval` | Sau insights sync |

Token refresh thủ công:

```bash
export PTT_ZALO_TOKEN_REFRESH=1
python3 -c "
from ptt_zalo.token_refresh import sync_zalo_token_refresh
import json
print(json.dumps(sync_zalo_token_refresh(), indent=2, default=str))
"
```

## Verify hub

```bash
curl -s "$PTT_API_URL/api/v1/zalo-ads/hub?days=7" -H "Authorization: Bearer $STAFF_TOKEN" | jq '.pilot,.summary'
```

Kỳ vọng: `pilot.stub_mode=false`, `pilot.production_mode=true`, không `warning`.

## Rollback

```bash
export PTT_ZALO_ADS_STUB=1
export PTT_ZALO_ADS_PILOT=1
export PTT_ZALO_ADS_PILOT_CLIENTS=<pilot-uuid>
```

Restart API + worker; hub hiển thị pilot banner stub.

## Related

- [`huong-dan-zalo-ads-ops.md`](../huong-dan-zalo-ads-ops.md)
- [`meta-token-refresh.md`](./meta-token-refresh.md) (pattern tương tự)
- Gate Z2: `./scripts/staging_zalo_wave_z2_gate.sh`
