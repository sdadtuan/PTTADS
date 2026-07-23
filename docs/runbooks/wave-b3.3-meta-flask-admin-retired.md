# Wave B3.3 — Flask Meta Ads admin retired (M1-G09)

> Bật `PTT_FLASK_META_ADS_ADMIN_RETIRED=1` — hub Meta canonical trên **ops-web** `/meta/facebook-ads`. Flask `/crm/facebook-ads` redirect qua nginx; `ptt.service` vẫn chạy cho CRM legacy khác.

## Tiên quyết

| Item | Ghi chú |
|------|---------|
| Wave B3.1 | Webhook Nest Meta |
| Wave B3.2 | ops-web Meta hub UAT (filter + export) |
| ops-web + Nest | Hub + API deploy |

## Biến môi trường (VPS `.env`)

```bash
PTT_FLASK_META_ADS_ADMIN_RETIRED=1
HORIZON1_EXPECT_META_HUB_RETIRED=1
PTT_WEBHOOKS_NEST_ENABLED=1
PTT_WEBHOOKS_NEST_META=1
PTT_WEBHOOKS_FLASK_FALLBACK=0
PTT_OPS_WEB_URL=https://ops.pttads.vn
```

## Gate M1-G09

```bash
export PTT_FLASK_META_ADS_ADMIN_RETIRED=1
export HORIZON1_EXPECT_META_HUB_RETIRED=1
python3 -m ptt_crm.horizon1_meta_ads_gates
# → checks M1-G09 ok: true
```

## API migration status

`GET /api/v1/facebook-ads/migration-status` (staff JWT):

```json
{
  "ok": true,
  "flask_meta_ads_admin_retired": true,
  "ops_web_hub_url": "https://ops.pttads.vn/meta/facebook-ads",
  "canonical_upstream": "ops-web",
  "gate_m1_g09": true
}
```

## nginx redirect

```bash
sudo ./scripts/apply_nginx_meta_ads_retired.sh
# Verify:
curl -I https://rs.pttads.vn/crm/facebook-ads
# → 302 Location: https://ops.pttads.vn/meta/facebook-ads
```

Snippet: `deploy/nginx-meta-ads-retired-snippet.conf`

## Deploy VPS

**Dry-run (gates only):**

```bash
cd /var/www/ptt && git pull origin main
chmod +x scripts/wave_b3_3_*.sh scripts/apply_nginx_meta_ads_retired.sh
./scripts/wave_b3_3_deploy.sh
```

**Apply prod:**

```bash
sudo -E APPLY=1 ./scripts/wave_b3_3_deploy.sh
# Hoặc full pack (env + nginx + restart):
sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh
```

## Smoke

```bash
set -a && source .env && set +a
ADMIN_PASSWORD='...' ./scripts/wave_b3_3_smoke.sh
```

## Python helpers

| Module | Mục đích |
|--------|----------|
| `ptt_crm.config.meta_ads_admin_retired()` | Đọc env flag |
| `ptt_crm.meta_ads_admin_retirement.migration_status()` | JSON status |
| `ptt_crm.flask_guard.deny_flask_meta_ads_admin()` | Flask route guard (302) |

## Rollback

```bash
# .env
PTT_FLASK_META_ADS_ADMIN_RETIRED=0
HORIZON1_EXPECT_META_HUB_RETIRED=0
sudo systemctl restart ptt ptt-crm-api
# Xóa / comment nginx location /crm/facebook-ads redirect
```

## Bước tiếp (B3.4–B3.6)

- **B3.4** nginx redirect verify production (M1-G06) — [`wave-b3.4-meta-nginx-redirect-verify.md`](./wave-b3.4-meta-nginx-redirect-verify.md)
- **B3.5** dry-run `close_flask_retirement_meta_ads.sh`
- **B3.6** APPLY prod retirement script
