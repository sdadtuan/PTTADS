# Wave B3.4 — nginx redirect verify production (M1-G06)

> Xác minh **production** redirect `https://rs.pttads.vn/crm/facebook-ads` → `https://ops.pttads.vn/meta/facebook-ads`. Gate **M1-G06** gồm config repo + (tuỳ chọn) live HTTP + nginx site trên VPS.

## Tiên quyết

| Item | Ghi chú |
|------|---------|
| Wave B3.3 | `PTT_FLASK_META_ADS_ADMIN_RETIRED=1` (M1-G09) |
| nginx | Snippet hoặc full `deploy/nginx-rs-delivery-admin-retired.conf` |
| DNS/TLS | `rs.pttads.vn` và `ops.pttads.vn` reachable từ VPS |

## Gate M1-G06

```bash
# Local/CI — chỉ kiểm config repo (live skip mặc định)
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=1
python3 -m ptt_crm.horizon1_meta_ads_gates
# → M1-G06 ok: true (deploy conf)

# VPS prod — bật live verify
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0
export PTT_RS_BASE_URL=https://rs.pttads.vn
export PTT_OPS_WEB_URL=https://ops.pttads.vn
./scripts/verify_meta_ads_nginx_redirect.sh
python3 -m ptt_crm.horizon1_meta_ads_gates
```

## Verify thủ công

```bash
curl -I https://rs.pttads.vn/crm/facebook-ads
# HTTP/2 302
# location: https://ops.pttads.vn/meta/facebook-ads

curl -I https://rs.pttads.vn/crm/leads
# vẫn 302 → ops (regression)
```

## Deploy VPS

**Dry-run (verify + gates, không sửa nginx):**

```bash
cd /var/www/ptt && git pull origin main
chmod +x scripts/wave_b3_4_*.sh scripts/verify_meta_ads_nginx_redirect.sh
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0
./scripts/wave_b3_4_deploy.sh
```

**Apply nginx nếu chưa có redirect:**

```bash
sudo -E APPLY=1 ./scripts/wave_b3_4_deploy.sh
# hoặc:
sudo ./scripts/apply_nginx_meta_ads_retired.sh
```

## Smoke

```bash
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0
./scripts/wave_b3_4_smoke.sh
ADMIN_PASSWORD='...' ./scripts/wave_b3_4_smoke.sh
```

Smoke kiểm:

- pytest `test_meta_ads_nginx_redirect.py`
- Python live redirect (3 URL variants)
- curl spot-check `/crm/facebook-ads`, `/crm/facebook-ads/`, query string
- regression `/crm/leads`, `/crm/hub`
- API `GET /api/v1/facebook-ads/migration-status` → `gate_m1_g06: true`

## Python helpers

| Module | Mục đích |
|--------|----------|
| `ptt_crm.meta_ads_nginx_redirect.verify_nginx_redirect_gate()` | Gate M1-G06 |
| `ptt_crm.meta_ads_nginx_redirect.verify_live_redirect()` | HTTP HEAD live |
| `ptt_crm.meta_ads_nginx_redirect.verify_legacy_routes_unbroken()` | Regression CRM redirects |

## API migration-status (mở rộng B3.3)

`GET /api/v1/facebook-ads/migration-status`:

```json
{
  "gate_m1_g09": true,
  "gate_m1_g06": true,
  "gate_m1_g06_config": true,
  "gate_m1_g06_live": true,
  "legacy_rs_path": "/crm/facebook-ads",
  "nginx_deploy_config_ok": true,
  "nginx_live_site_configured": true
}
```

## Rollback

```bash
# Comment/xóa block nginx location ^~ /crm/facebook-ads
sudo nginx -t && sudo systemctl reload nginx
```

## Bước tiếp (B3.5–B3.6)

- **B3.5** dry-run `close_flask_retirement_meta_ads.sh`
- **B3.6** APPLY prod retirement pack
