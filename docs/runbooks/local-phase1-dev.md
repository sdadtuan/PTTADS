# Runbook — Local Phase 1 trước VPS

> **Nguyên tắc:** Hoàn thiện + UAT **100% trên local/staging** → mới deploy production VPS (`/var/www/qlptt`).

---

## 1. Đề xuất chiến lược (Ban / team)

| Giai đoạn | Môi trường | Mục tiêu |
|-----------|------------|----------|
| **A. Local dev** | Mac + Docker Desktop | Feature Phase 1, unit/smoke test |
| **B. Local full** | Docker PG + worker | Queue idempotent, DLQ replay |
| **C. Staging VPS** | Subdomain `staging.pttads.vn` hoặc port riêng | UAT AM/CSKH, Meta webhook test |
| **D. Production** | `pttads.vn` / `qlptt` | Cutover có rollback |

**Không nên:** Deploy thẳng Phase 1 lên VPS production đang chạy CRM — rủi ro mất lead.

**Nên:** Giữ Flask production; staging chạy song song branch `agency-phase1` cho đến sign-off PRD §7.

---

## 2. Ba chế độ local

| Mode | Yêu cầu | Queue | Worker |
|------|---------|-------|--------|
| **docker** (khuyến nghị) | Docker Desktop | PostgreSQL | ✅ |
| **brew** | `brew install postgresql@15` | PostgreSQL | ✅ |
| **lite** | Chỉ Python | Sync fallback | ❌ |

Script tự chọn: `./scripts/local_phase1_up.sh`

---

## 3. Cài đặt lần đầu (Mac)

```bash
cd PTTADS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Điền CRM_FACEBOOK_* nếu test webhook Meta thật
```

### Option A — Docker (khuyến nghị)

1. Cài [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
2. `docker compose up -d`
3. `./scripts/local_phase1_up.sh docker`

### Option B — Homebrew PostgreSQL

```bash
brew install postgresql@15
brew services start postgresql@15
createuser -s ptt 2>/dev/null || true
createdb -O ptt ptt_agency 2>/dev/null || true
psql postgresql://ptt@127.0.0.1:5432/ptt_agency -f docs/specs/2026-07-17-postgresql-ddl-v1.sql
export DATABASE_URL=postgresql://ptt@127.0.0.1:5432/ptt_agency
./scripts/local_phase1_up.sh brew
```

### Option C — Lite (không PG)

```bash
./scripts/local_phase1_up.sh lite
# Webhook vẫn ingest CRM qua sync — đủ dev UI/CRM
```

---

## 4. Lệnh hằng ngày

```bash
./scripts/local_phase1_up.sh      # start
./scripts/local_phase1_smoke.sh   # verify
./scripts/local_phase1_down.sh    # stop
```

Logs: `.local-dev/flask.log`, `.local-dev/worker.log`

### Leads read cutover (Bước 8)

```bash
./scripts/local_leads_cutover_drill.sh
./scripts/apply_leads_read_upstream.sh --dry-run
```

Runbook: [`cutover-leads-read-b8.md`](cutover-leads-read-b8.md)

---

## 5. Checklist trước khi lên VPS

- [ ] PRD Phase 1 DoD §7 (100% webhook queue idempotent trên staging)
- [ ] Regression L01–L26 + TC-FLOW
- [ ] Agency Ops UI (khi xong)
- [ ] Runbook rollback: `PTT_WEBHOOK_V1_ENQUEUE=0`, legacy route
- [ ] Backup `data/` + PG dump staging
- [ ] Meta webhook URL staging test OK → đổi production

---

## 6. Deploy VPS (sau local xong)

```bash
# Staging trước
rsync -avz --exclude .venv --exclude .git PTTADS/ user@vps:/var/www/qlptt-staging/
# Trên VPS: docker compose, systemd ptt-worker, gunicorn
```

Production cutover chỉ khi staging UAT pass 1 tuần.

---

## 7. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|--------|------------|
| Mất lead khi cutover | Legacy webhook song song; feature flag |
| PG mới trên VPS | Docker compose PG trên VPS; backup daily |
| Worker không chạy | systemd `ptt-worker.service` + alert queue depth |
| SQLite vs PG lệch | Phase 1 dual DB theo migration matrix |
