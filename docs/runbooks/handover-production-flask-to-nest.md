# Bàn giao Production — Flask → Nest (1 trang)

> **Phiên bản:** Wave 8 · Flask HTTP removed · Nest canonical  
> **Ngày cutover:** _______________  
> **Người bàn giao:** _______________ · **Khách hàng nhận:** _______________

---

## 1. URL hệ thống

| Vai trò | URL | Ghi chú |
|---------|-----|---------|
| **Staff console (AM/CSKH/Admin)** | https://ops.pttads.vn | Next.js `:3200` · đăng nhập `/login` |
| **Client portal (viewer/approver)** | https://portal.pttads.vn | Next.js `:3100` · API same-origin `/api/v1/*` |
| **Legacy bookmark rs** | https://rs.pttads.vn | Sau cutover → **302** sang `ops.pttads.vn` |
| **Nest API (nội bộ VPS)** | http://127.0.0.1:3000 | Health: `/health` |
| **Webhooks (public)** | `https://<domain>/api/v1/webhooks/{channel}` | `meta` · `zalo` · `google` · `email` |

**Trang CRM chính (staff):**

| Module | URL |
|--------|-----|
| CRM board | https://ops.pttads.vn/crm |
| Leads | https://ops.pttads.vn/crm/leads |
| Hub campaigns | https://ops.pttads.vn/crm/hub |
| Meta Ads | https://ops.pttads.vn/meta/facebook-ads |
| SEO hub | https://ops.pttads.vn/seo/hub |
| Email hub | https://ops.pttads.vn/email/hub |
| Finance | https://ops.pttads.vn/crm/business-dashboard |

**Portal client:**

| Trang | URL |
|-------|-----|
| Login | https://portal.pttads.vn/login |
| Dashboard | https://portal.pttads.vn/dashboard |
| Meta / Creatives | https://portal.pttads.vn/meta · `/creatives` |
| SEO (pilot) | https://portal.pttads.vn/seo |

---

## 2. Tài khoản pilot

### 2.1 Portal (khách hàng / approver)

Seed prod: `python3 scripts/seed_portal_pilot_users.py --password '<MẬT_KHẨU_CUTOVER>'`  
(Mật khẩu đặt lúc Phase 3 cutover qua biến `PORTAL_PILOT_PASSWORD` — **không lưu trong repo**.)

| Email | Vai trò | Client |
|-------|---------|--------|
| `viewer.pilot1@pttads.vn` | viewer | PILOT1 |
| `approver.pilot1@pttads.vn` | approver | PILOT1 |
| `viewer.pilot2@pttads.vn` | viewer | PILOT2 |
| `approver.pilot2@pttads.vn` | approver | PILOT2 |
| `approver.pilot3@pttads.vn` | approver | PILOT3 |

**Mật khẩu ban đầu:** `<điền tại bàn giao — vault/KV>`  
**Prod:** `PTT_PORTAL_STUB_USERS=` (rỗng) · `PTT_PORTAL_ALLOW_STUB=0`

### 2.2 Staff (nội bộ PTT)

| Môi trường | Cách đăng nhập |
|------------|----------------|
| **Production** | Tài khoản trong bảng PG `staff_users` (do Admin HR tạo) → https://ops.pttads.vn/login |
| **Local/dev only** | Stub env `PTT_STAFF_STUB_USERS=staff@demo.local:demo123:...` — **không dùng prod** |

---

## 3. Cutover (đã / sẽ thực hiện trên VPS)

```bash
cd /var/www/ptt
set -a && source deploy/env.phase5-flask-retire.example && set +a
# Chỉnh DATABASE_URL, JWT, webhook secrets trong .env

sudo -E ./scripts/close_flask_retirement.sh          # dry-run
sudo -E APPLY=1 ./scripts/close_flask_retirement.sh  # thực thi
```

**Kết quả mong đợi:** `PTT_FLASK_MONOLITH_MODE=retired` · `ptt.service` **inactive** · nginx `rs.pttads.vn` → redirect ops-web.

**Units phải chạy:**

| Unit | Vai trò |
|------|---------|
| `ptt-crm-api` | Nest API `:3000` |
| `ptt-ops-web` | Staff UI `:3200` |
| `ptt-portal-web` | Client UI `:3100` |
| `ptt-worker` | Job queue (ingest lead, email, …) |
| `ptt-fb-autosync` | Facebook background sync |
| `ptt-temporal-worker` | Workflows (nếu bật Temporal) |
| ~~`ptt.service`~~ | **Retired** (Flask Gunicorn) |

---

## 4. Smoke test sau bàn giao (5 phút)

```bash
curl -sf http://127.0.0.1:3000/health && echo OK
systemctl is-active ptt.service                    # → inactive
systemctl is-active ptt-crm-api ptt-worker ptt-ops-web ptt-portal-web
curl -sfI https://ops.pttads.vn/crm/leads | head -1
curl -sfI https://portal.pttads.vn/login | head -1
curl -sfI https://rs.pttads.vn/crm/leads | head -1   # → 302 ops
```

| # | Kiểm tra | OK |
|---|----------|----|
| 1 | Staff login ops-web → mở `/crm/leads` | [ ] |
| 2 | Portal login pilot → dashboard load | [ ] |
| 3 | Webhook Meta/Zalo test → `job_queue` pending | [ ] |
| 4 | Worker xử lý lead mới vào CRM | [ ] |
| 5 | Email hub / SEO hub mở được | [ ] |

---

## 5. Rollback khẩn cấp

> **Lưu ý:** Repo hiện tại **đã xóa Flask HTTP** (`app.py`). Chỉ bật lại `ptt.service` **không đủ** — cần redeploy bản **pre-Wave-8** hoặc restore backup code trên VPS.

### 5.1 Rollback nginx + env (nhanh, ≤15 phút)

```bash
sudo cp /etc/nginx/sites-available/rs.pttads.vn.pre-phase5.bak \
        /etc/nginx/sites-available/rs.pttads.vn
sudo nginx -t && sudo systemctl reload nginx

# /var/www/ptt/.env
PTT_FLASK_MONOLITH_MODE=readonly
PTT_WEBHOOKS_FLASK_FALLBACK=1    # tạm nếu Nest webhook lỗi

sudo systemctl restart ptt-crm-api ptt-ops-web ptt-portal-web
```

### 5.2 Rollback full Flask (chỉ khi redeploy bản cũ)

```bash
git checkout <tag-pre-wave8>   # hoặc restore tarball backup
sudo systemctl enable --now ptt.service
sudo systemctl restart ptt ptt-crm-api
# Khôi phục nginx agency cũ từ .pre-phase5.bak hoặc deploy/nginx-agency.conf
```

**Liên hệ khẩn:** DevOps _______________ · Tech Lead _______________

---

## 6. Giới hạn đã thống nhất với khách

| Hạng mục | Trạng thái |
|----------|------------|
| CRM staff + API | Nest + ops-web — **production** |
| Webhooks 4 channel | Nest native |
| AI brief / intake summary / proposals | Stub — cần `ANTHROPIC_API_KEY` để bật |
| Temporal workflows | Stub nếu chưa cấu hình `PTT_TEMPORAL_ADDRESS` |
| Google Ads campaign API | Phase 2 — webhook lead OK, API write chưa |
| Public marketing site (`pttads.vn` landing) | Đã gỡ — chỉ web-app |

---

## 7. Sign-off

| Vai trò | Họ tên | Ngày | Chữ ký |
|---------|--------|------|--------|
| PTT Tech Lead | | | |
| PTT DevOps | | | |
| Khách hàng (PO) | | | |

**Artifact gate:** `.local-dev/phase5-flask-retirement-gate-report.json`  
**Runbook chi tiết:** [`phase5-flask-retirement-checklist.md`](./phase5-flask-retirement-checklist.md)  
**Deploy VPS đầy đủ:** [`vps-full-system-deploy.md`](./vps-full-system-deploy.md)
