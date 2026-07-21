# Wave B1 — Deploy & test trên VPS

> Agency core trên Nest + ops-web: checklist, activate, channel, jobs replay, notifications, KPI, hub Meta ID edit.

## 0. Tiên quyết

| Item | Ghi chú |
|------|---------|
| PG + DDL v1/v3 | `clients`, `client_onboarding_items`, `job_queue`, `notification_inbox`, `kpi_definitions`, `hub_campaign_map` |
| `PTT_LEADS_WRITE_ENABLED=1` | Trong `/var/www/ptt/.env` (lead write — P0) |
| Staff login | `admin@pttads.vn` + `ADMIN_PASSWORD` trong `.env` |
| Cap ghi Agency | `crm_agency` → `create` (seed super admin) |

## 1. Đưa code lên VPS

**Trên máy dev (đã push `main`):**

```bash
git push origin main
```

**Trên VPS (`deploy@vultr`):**

```bash
cd /var/www/ptt
git pull origin main
chmod +x scripts/wave_b1_deploy.sh scripts/wave_b1_smoke.sh
```

Nếu chưa push được — `scp` thư mục `services/ptt-crm-api/src/agency`, `services/ops-web/src/app/agency`, `scripts/wave_b1_*.sh`.

## 2. Build & restart

```bash
cd /var/www/ptt
./scripts/wave_b1_deploy.sh
```

Nếu không có quyền `systemctl restart`:

```bash
sudo systemctl restart ptt-crm-api ptt-ops-web
```

## 3. API smoke (localhost)

```bash
cd /var/www/ptt
set -a && source .env && set +a
./scripts/wave_b1_smoke.sh
```

## 4. UI test checklist (staff browser)

Đăng nhập https://ops.pttads.vn/login (hoặc rs.pttads.vn redirect).

| # | URL | Kiểm tra |
|---|-----|----------|
| 1 | `/agency` | Stat cards, link Ingest / Thông báo / KPI |
| 2 | `/agency/clients/:id?tab=checklist` | Tick checklist, nút Kích hoạt |
| 3 | `/agency/clients/:id?tab=channels` | Thêm Meta ad account |
| 4 | `/agency/jobs` | Job `dead` → **Replay** |
| 5 | `/agency/notifications` | Mark read |
| 6 | `/agency/kpi-definitions` | Bảng KPI |
| 7 | `/crm/hub` | Sửa Meta Campaign ID → **Lưu** |

Redirect Spec: `/crm/agency/*` → `/agency/*`.

## 5. Troubleshooting

| Triệu chứng | Xử lý |
|-------------|--------|
| 403 missing_cap | Chạy `python3 scripts/seed_super_admin_full_access.py --sqlite /var/www/ptt/ptt.db --username admin --email admin@pttads.vn --apply-pg` |
| 503 pg_not_ready | Kiểm tra `DATABASE_URL`, `curl http://127.0.0.1:3000/health` |
| UI cũ, API mới | Hard refresh; rebuild ops-web với `NEXT_PUBLIC_PTT_API_URL=https://ops.pttads.vn` |
| Replay 400 | Chỉ job `status=dead` |

Logs:

```bash
journalctl -u ptt-crm-api -n 100 --no-pager
journalctl -u ptt-ops-web -n 50 --no-pager
```
