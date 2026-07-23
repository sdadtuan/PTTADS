# Wave B3.5 — Meta Ads retirement dry-run (M1-G11)

> Dry-run đầy đủ **`close_flask_retirement_meta_ads.sh`** trước khi APPLY prod (B3.6). Không sửa `.env`, nginx hay restart service — chỉ preflight + artifact.

## Tiên quyết

| Item | Ghi chú |
|------|---------|
| Wave B3.3 | `PTT_FLASK_META_ADS_ADMIN_RETIRED=1` (M1-G09) |
| Wave B3.4 | nginx redirect verify (M1-G06) |
| Gates | `./scripts/horizon1_meta_ads_pack.sh preflight` PASS |

## Dry-run commands

```bash
# Preflight Python (artifact JSON)
python3 -m ptt_crm.meta_ads_retirement_preflight run

# Full retirement script — DRY-RUN (default)
sudo -E ./scripts/close_flask_retirement_meta_ads.sh
# hoặc không cần sudo trên dev:
APPLY=0 ./scripts/close_flask_retirement_meta_ads.sh

# Wave B3.5 pack
./scripts/wave_b3_5_deploy.sh
./scripts/wave_b3_5_smoke.sh
```

## Artifact

`.local-dev/horizon1-meta-ads-retirement-dry-run.json`

Gồm:

- `env_diff` — so sánh `.env` hiện tại vs planned flags
- `nginx_plan` — deploy conf + live site status
- `systemd` — unit files (skip local: `HORIZON1_SKIP_SYSTEMD=1`)
- `horizon1_gates` — gate report PASS
- `apply_plan` — env/nginx/restart/rollback

Verify artifact:

```bash
python3 -m ptt_crm.meta_ads_retirement_preflight verify
```

## Gate M1-G11

```bash
export HORIZON1_EXPECT_META_RETIREMENT_DRY_RUN=1
python3 -m ptt_crm.horizon1_meta_ads_gates
# → M1-G11 ok: true (requires dry-run artifact)
```

## Planned env (APPLY sẽ ghi)

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

## VPS dry-run (systemd probe)

```bash
cd /var/www/ptt && git pull origin main
chmod +x scripts/wave_b3_5_*.sh scripts/close_flask_retirement_meta_ads.sh
export HORIZON1_SKIP_SYSTEMD=0
export PTT_ENV_FILE=/var/www/ptt/.env
sudo -E ./scripts/wave_b3_5_deploy.sh
sudo -E HORIZON1_SKIP_SYSTEMD=0 ./scripts/wave_b3_5_smoke.sh
```

## Rollback (documented in artifact)

1. `PTT_FLASK_META_ADS_ADMIN_RETIRED=0` trong `.env`
2. Xóa/comment nginx `location ^~ /crm/facebook-ads`
3. `systemctl restart ptt-crm-api ptt-ops-web ptt`

## Bước tiếp (B3.6)

```bash
sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh
ADMIN_PASSWORD='...' ./scripts/wave_b3_4_smoke.sh
```
