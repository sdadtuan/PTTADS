# Runbook — Migration Sprint 0 (Prod stability + PG lead write)

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-20  
> **Parent:** [`SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md`](SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md) §4  
> **Mục tiêu:** Cầm máu prod trong 7 ngày **trước** khi cut ops-web  

---

## 1. Tiền đề

- SSH VPS production (`docs/runbooks/vps-production-operations.md`)
- Backup `ptt.db` và PG trước mọi thay đổi
- Thông báo team: **freeze Flask features** từ ngày chạy runbook

---

## 2. Backup (bắt buộc)

```bash
cd /var/www/ptt
cp ptt.db "ptt.db.bak-$(date +%Y%m%d-%H%M)"
sudo -u postgres pg_dump ptt_agency | gzip > "/var/backups/pg_pre_sprint0-$(date +%Y%m%d).sql.gz"
```

---

## 3. Bật queue-only webhook (S0-2)

Chỉnh `/var/www/ptt/.env`:

```bash
PTT_JOBS_ENABLED=1
PTT_WEBHOOK_V1_ENQUEUE=1
PTT_JOBS_SYNC_FALLBACK=0
```

```bash
sudo systemctl restart ptt-worker
sudo systemctl restart ptt
```

**Verify:**

```bash
# Gửi test webhook staging — log phải mode=queue, không sync
journalctl -u ptt -n 50 | rg "mode=queue"
```

**Rollback:** `PTT_JOBS_SYNC_FALLBACK=1` + restart (chỉ khi worker down > 15 phút).

---

## 4. Tách Facebook autosync khỏi Gunicorn (S0-3)

1. Comment/remove `start_facebook_autosync_worker` trong `gunicorn.conf.py` post_fork  
2. Tạo `deploy/ptt-fb-autosync.service` chạy script riêng (1 process)  
3. `sudo systemctl enable --now ptt-fb-autosync`  
4. Restart `ptt.service`  

**Verify:** Chỉ 1 autosync process (`ps aux | rg facebook_autosync`).

---

## 5. Tăng Gunicorn workers (S0-4)

`/etc/systemd/system/ptt.service` — tạm thời trong khi Flask còn:

```
ExecStart=.../gunicorn -c gunicorn.conf.py -w 9 -b 127.0.0.1:8002 --timeout 120 app:app
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ptt
```

Monitor RAM — không vượt 70% VPS.

---

## 6. PostgreSQL lead backfill (S0-8–S0-10)

```bash
cd /var/www/ptt
./scripts/apply_pg_ddl_v3_leads_oltp.sh   # nếu chưa
./scripts/sync_leads_backfill.sh
python3 scripts/reconcile_sqlite_pg_leads.py --sample 200
```

Staging first:

```bash
export PTT_LEADS_WRITE_SOURCE=pg
export PTT_LEADS_READ_SOURCE=pg
# soak 48h staging → prod
```

---

## 7. Grafana alerts (S0-6)

- `job_queue_pending > 1000` → Slack  
- Gunicorn worker timeout spike  
- PG connection errors  

---

## 8. Sign-off Sprint 0

| Check | Pass |
|-------|------|
| Webhook 100% queue mode 24h | ☐ |
| Worker running, queue depth stable | ☐ |
| Autosync single process | ☐ |
| Backfill reconcile pass | ☐ |
| No P0 incidents 48h after changes | ☐ |

**Signed:** _______________ **Date:** _______________

---

## 9. Bước tiếp theo

→ [`SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md`](SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md) Phase 0: scaffold `ops-web` + Nest `staff-auth`.
