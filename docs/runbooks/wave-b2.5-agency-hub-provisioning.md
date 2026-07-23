# Wave B2.5 — Agency Hub campaign map CRUD (PG-native)

> Client Agency mới (TCLT, AAAA…) tạo **hub_campaign_map** trực tiếp trên PostgreSQL — không cần SQLite Hub hay `./scripts/sync_hub_campaign_map.sh`.

## Tiên quyết

| Item | Ghi chú |
|------|---------|
| Wave B1/B2 | Agency core + side effects đã deploy |
| PG DDL v3 | Bảng `hub_campaign_map` |
| `PTT_JOBS_ENABLED=1` | (tuỳ chọn) Sau POST/PATCH map Meta → enqueue `meta_insights_sync` |
| Cap ghi | `crm_agency` → `create` |

## API mới (Nest)

| Method | Route | Mô tả |
|--------|-------|-------|
| POST | `/api/v1/crm/hub-campaign-maps` | Tạo map (body có `client_id`) |
| PATCH | `/api/v1/crm/hub-campaign-maps/:mapId` | Sửa campaign ID, tên, CPL, active |
| DELETE | `/api/v1/crm/hub-campaign-maps/:mapId` | Xóa map |
| POST | `/api/v1/clients/:id/hub-campaign-maps` | Tạo map cho client |
| PATCH | `/api/v1/clients/:id/hub-campaign-maps/:mapId` | Sửa map (scoped) |
| DELETE | `/api/v1/clients/:id/hub-campaign-maps/:mapId` | Xóa map (scoped) |

**Legacy:** `PATCH /api/v1/crm/hub-campaign-maps` (body `hub_campaign_id`) vẫn hoạt động cho row SQLite sync cũ.

**hub_campaign_id:** Nếu không truyền, hệ thống cấp ID dải `9000000001+` (Agency-native, không cần Hub SQLite).

## Luồng sử dụng (AM)

1. **Agency → Client → tab Campaign map** (hoặc `/crm/hub`)
2. Thêm kênh Meta + token ở tab **Kênh ads** (Wave B2)
3. **Thêm campaign map:** dán Meta Campaign ID từ Ads Manager (vd. `120250314265080598`)
4. (Tuỳ chọn) Target CPL VND
5. Lưu → job `meta_insights_sync` (nếu jobs bật) → tab **Tổng quan** có spend/CPL

## Deploy VPS

```bash
cd /var/www/ptt
sudo -u deploy -H bash -lc 'git pull origin main'
chmod +x scripts/wave_b25_deploy.sh scripts/wave_b25_smoke.sh
sudo -u deploy -H bash -lc 'cd /var/www/ptt && export NEXT_PUBLIC_PTT_API_URL=https://rs.pttads.vn && ./scripts/wave_b25_deploy.sh'
sudo systemctl restart ptt-crm-api ptt-ops-web
```

## Smoke

```bash
cd /var/www/ptt
set -a && source .env && set +a
ADMIN_PASSWORD="$ADMIN_PASSWORD" CLIENT_ID=<uuid-tclt> ./scripts/wave_b25_smoke.sh
```

## UI

| URL | Chức năng |
|-----|-----------|
| `/agency/clients/:id?tab=campaigns` | CRUD map theo client |
| `/crm/hub` | Danh sách toàn hệ thống + thêm map (chọn client) |
| `/crm/hub?client_id=:uuid` | Lọc theo client |

## Rollback

Revert commit Wave B2.5; `./scripts/wave_b2_deploy.sh`. Row `hub_campaign_map` đã tạo vẫn an toàn trên PG.
