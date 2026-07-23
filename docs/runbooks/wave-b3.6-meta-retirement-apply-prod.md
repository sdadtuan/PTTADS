# Wave B3.6 — Meta Ads retirement APPLY prod (M1-G12)

> **APPLY thật** trên VPS: ghi `.env`, nginx redirect, restart services. Yêu cầu **B3.5 dry-run PASS** trước.

## Tiên quyết

| Item | Ghi chú |
|------|---------|
| Wave B3.5 | `./scripts/wave_b3_5_deploy.sh` + artifact dry-run OK |
| Gate | M1-G09, M1-G06 (live redirect sau apply) |
| Quyền | `sudo` trên VPS |

## APPLY prod (VPS)

```bash
cd /var/www/ptt && git pull origin main
chmod +x scripts/wave_b3_6_*.sh scripts/close_flask_retirement_meta_ads.sh

# Kiểm tra plan (không đổi gì)
export PTT_ENV_FILE=/var/www/ptt/.env
./scripts/wave_b3_6_deploy.sh

# APPLY
sudo -E APPLY=1 ./scripts/wave_b3_6_deploy.sh
# hoặc trực tiếp:
sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh
```

## Post-apply smoke

```bash
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0
export PTT_RS_BASE_URL=https://rs.pttads.vn
ADMIN_PASSWORD='...' ./scripts/wave_b3_6_smoke.sh
```

Smoke gồm:

- pytest `test_meta_ads_retirement_apply.py`
- `verify_meta_ads_retirement_applied.sh`
- Gates M1-G09 + M1-G12
- `wave_b3_4_smoke` (nginx live redirect + regression)
- API `migration-status` → `gate_m1_g12: true`

## Artifact

`.local-dev/horizon1-meta-ads-retirement-applied.json`

```bash
python3 -m ptt_crm.meta_ads_retirement_apply verify
python3 -m ptt_crm.meta_ads_retirement_apply post
```

## Env flags (APPLY ghi)

| Key | Value |
|-----|-------|
| `PTT_FLASK_META_ADS_ADMIN_RETIRED` | `1` |
| `HORIZON1_EXPECT_META_HUB_RETIRED` | `1` |
| `PTT_WEBHOOKS_NEST_ENABLED` | `1` |
| `PTT_WEBHOOKS_NEST_META` | `1` |
| `PTT_WEBHOOKS_FLASK_FALLBACK` | `0` |
| `CRM_FACEBOOK_BACKGROUND` | `1` |
| `CRM_FACEBOOK_BACKGROUND_IN_GUNICORN` | `0` |
| `HORIZON1_META_NGINX_REDIRECT_VERIFIED` | `1` |
| `HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED` | `1` |
| `HORIZON1_META_RETIREMENT_APPLIED` | `1` |

## Gate M1-G12

```bash
export HORIZON1_EXPECT_META_RETIREMENT_APPLIED=1
export HORIZON1_SKIP_NGINX_REDIRECT_VERIFY=0
python3 -m ptt_crm.horizon1_meta_ads_gates
```

## API migration-status

```json
{
  "gate_m1_g12": true,
  "retirement_applied_ok": true,
  "retirement_env_applied_ok": true,
  "flask_meta_ads_admin_retired": true
}
```

## Partial retire (quan trọng)

- **`ptt.service` vẫn chạy** — CRM legacy khác vẫn Flask
- Chỉ Meta hub `/crm/facebook-ads` redirect → ops-web
- `ptt-fb-autosync.service` restart sau apply

## Rollback

1. `PTT_FLASK_META_ADS_ADMIN_RETIRED=0`, `HORIZON1_META_RETIREMENT_APPLIED=0`
2. Xóa nginx block `/crm/facebook-ads`
3. `systemctl restart ptt-crm-api ptt-ops-web ptt nginx`

## Horizon 1 pack

```bash
./scripts/horizon1_meta_ads_pack.sh b3.6   # APPLY=1 cần sudo
```

## Verify thủ công

```bash
curl -I https://rs.pttads.vn/crm/facebook-ads
# → 302 https://ops.pttads.vn/meta/facebook-ads

curl -I https://rs.pttads.vn/crm/leads
# → vẫn 302 ops (regression)
```

## B3 complete

Sau B3.6 PASS → bookmark Flask Meta hub → 302 ops-web · tiếp soak M1-C / signoff M1-F.
