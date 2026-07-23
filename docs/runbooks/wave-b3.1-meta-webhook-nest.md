# Wave B3.1 — Meta webhook Nest-only (Horizon 1 M1-B1)

> Meta Lead Ads webhook → **Nest** (`ptt-crm-api`) → `job_queue` (`ingest_lead`) → worker → `crm_leads`. Flask fallback tắt cho kênh Meta.

## Tiên quyết

| Item | Ghi chú |
|------|---------|
| Wave B2 | Agency client + channel account + token vault |
| Wave B2.5 | (tuỳ chọn) Hub campaign map cho CPL |
| PG + worker | `PTT_JOBS_ENABLED=1`, job worker chạy |
| Meta App | App Secret + Verify Token trong `.env` |

## Biến môi trường

```bash
PTT_WEBHOOKS_NEST_ENABLED=1
PTT_WEBHOOKS_NEST_META=1
PTT_WEBHOOKS_FLASK_FALLBACK=0
PTT_JOBS_ENABLED=1
PTT_WEBHOOK_V1_ENQUEUE=1

CRM_FACEBOOK_VERIFY_TOKEN=...      # hub.mode=subscribe
CRM_FACEBOOK_APP_SECRET=...        # X-Hub-Signature-256
CRM_FACEBOOK_PAGE_ACCESS_TOKEN=... # fallback Graph fetch leadgen

PTT_TOKEN_VAULT_KEY=...            # per-client page token (ưu tiên)
PTT_META_WEBHOOK_DEFAULT_CLIENT_ID=...  # single-tenant fallback (tuỳ chọn)
```

## Luồng xử lý

1. Meta POST `/api/v1/webhooks/meta` (nginx → Nest `:3000`)
2. Verify `X-Hub-Signature-256` (nếu có App Secret)
3. Trích `page_id` / `form_id` từ payload leadgen
4. **Resolve `agency_client_id`:**
   - Header `X-PTT-Client-Id` (UUID)
   - Hoặc lookup `client_channel_accounts.meta.facebook_page_id`
   - Hoặc lookup `meta.facebook_form_id`
   - Hoặc `PTT_META_WEBHOOK_DEFAULT_CLIENT_ID`
5. Lấy Page Access Token: vault client → global env
6. Graph API fetch lead field_data (nếu leadgen payload)
7. Enqueue `ingest_lead` → worker ghi `crm_leads`

## Cấu hình Agency (multi-client)

Tab **Agency → Client → Kênh ads**:

1. Thêm Meta ad account (`act_…`)
2. Nhập **Facebook Page ID** (Page nhận leadgen webhook)
3. Lưu **Page Access Token** vào vault

Meta webhook **không** gửi client UUID — Page ID mapping là bắt buộc cho Agency đa khách.

## Deploy VPS

```bash
cd /var/www/ptt
sudo -u deploy -H bash -lc 'git pull origin main'
chmod +x scripts/wave_b3_1_deploy.sh scripts/wave_b3_1_smoke.sh scripts/apply_webhooks_upstream.sh

# Đảm bảo .env có flags ở trên
sudo -u deploy -H bash -lc 'cd /var/www/ptt && ./scripts/wave_b3_1_deploy.sh'
sudo systemctl restart ptt-crm-api
```

## Smoke

```bash
cd /var/www/ptt
set -a && source .env && set +a
./scripts/wave_b3_1_smoke.sh
# Hoặc với client thật:
CLIENT_ID=333a8341-a08f-4b7e-9ddf-b7c053935d03 ./scripts/wave_b3_1_smoke.sh
```

> **Lưu ý:** Khi `CRM_FACEBOOK_APP_SECRET` có trong `.env`, smoke tự thêm `X-Hub-Signature-256` (HMAC body). Nếu vẫn 401 → secret không khớp App trên Meta Developer Console; chạy `python3 scripts/ptt_fb_webhook_probe.py` mục **POST chữ ký**.

## Meta Developer Console

| Field | Giá trị |
|-------|---------|
| Callback URL | `https://rs.pttads.vn/api/v1/webhooks/meta` |
| Verify Token | `CRM_FACEBOOK_VERIFY_TOKEN` |
| Subscriptions | `leadgen` trên Page |

Sau subscribe: **Test** → kiểm tra `job_queue` (`job_type` like `ingest%`) và lead trên tab Agency.

## Rollback

```bash
sudo ./scripts/apply_webhooks_upstream.sh flask
# .env: PTT_WEBHOOKS_FLASK_FALLBACK=1, PTT_WEBHOOKS_NEST_META=0
sudo systemctl restart ptt-crm-api ptt
```

## API response (POST thành công)

```json
{
  "verified": true,
  "channel": "meta",
  "handler": "nest",
  "resolved_client_id": "uuid-or-null",
  "page_ids": ["123456789012345"],
  "form_ids": ["2814926042203269"],
  "accepted": true,
  "mode": "queue",
  "job_ids": ["..."]
}
```
