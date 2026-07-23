# Wave B3.2 — Meta hub UAT (filter client, date range, export)

> Staff hub `ops-web` `/meta/facebook-ads` — lọc client, khoảng ngày, export CSV cho UAT Horizon 1 §E1.

## Tiên quyết

| Item | Ghi chú |
|------|---------|
| Wave B3.1 | Webhook Nest (tuỳ chọn cho E2) |
| Wave B2/B2.5 | Agency client + hub map + `daily_performance` |
| Cap | `crm_facebook_ads:view` hoặc `crm_agency:view` |

## API (Nest)

### GET `/api/v1/facebook-ads/hub`

| Query | Mô tả |
|-------|--------|
| `days` | 1–90 (mặc định 7), bỏ qua nếu có `date_from` |
| `date_to` | Ngày kết thúc (YYYY-MM-DD), mặc định hôm qua UTC |
| `date_from` | Ngày bắt đầu (override `days`) |
| `client_id` | UUID — lọc một client |
| `status` | `active`, `onboarding`, `prospect`, … |
| `q` | Tìm theo `code` / `name` (ILIKE) |

Response gồm `date_from`, `date_to`, `window_days`, `summary`, `clients[]`, `alerts[]`.

### GET `/api/v1/facebook-ads/hub/export`

Cùng query filter +:

| Query | Mô tả |
|-------|--------|
| `scope` | `clients` (mặc định) hoặc `campaigns` |

Trả CSV UTF-8 BOM, `Content-Disposition: attachment`.

## UI ops-web

URL: **`/meta/facebook-ads`**

- Preset 7 / 14 / 28 / 90 ngày
- Chọn `date_to`, `date_from` tùy chỉnh
- Dropdown client (active)
- Lọc status + tìm mã/tên
- Export CSV theo client hoặc campaign
- Query string đồng bộ URL (share link UAT)

## UAT checklist (§E1)

| Bước | Pass |
|------|------|
| Login staff → `/meta/facebook-ads` load summary + bảng | ☐ |
| Đổi 28 ngày → spend/leads thay đổi | ☐ |
| Lọc 1 client → chỉ 1 dòng (hoặc empty) | ☐ |
| Export CSV clients → mở Excel, có BOM + header | ☐ |
| Export CSV campaigns → có campaign_id | ☐ |

Ghi vào `docs/evidence/horizon1-meta-ads-signoff.json` → `manual_uat.E1`.

## Deploy VPS

```bash
cd /var/www/ptt
git pull origin main
chmod +x scripts/wave_b3_2_deploy.sh scripts/wave_b3_2_smoke.sh
sudo -u deploy -H bash -lc 'cd /var/www/ptt && export NEXT_PUBLIC_PTT_API_URL=https://rs.pttads.vn && ./scripts/wave_b3_2_deploy.sh'
```

## Smoke

```bash
cd /var/www/ptt
set -a && source .env && set +a
ADMIN_PASSWORD="$ADMIN_PASSWORD" CLIENT_ID=333a8341-a08f-4b7e-9ddf-b7c053935d03 ./scripts/wave_b3_2_smoke.sh
```

## Rollback

Revert commit Wave B3.2 — API cũ `?days=7` vẫn tương thích.
