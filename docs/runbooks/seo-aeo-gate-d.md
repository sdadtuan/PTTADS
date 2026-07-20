# SEO/AEO — Gate D (Enterprise & BI)

## Scope

| # | Deliverable | Path |
|---|-------------|------|
| D1 | Full Grafana dashboard + alert rules | `deploy/grafana/seo-ops-dashboard.json`, `seo-ops-alert-rules.json` |
| D1 | BI facts: `aeo_coverage_pct` | `ptt_seo/bi_clickhouse.py` |
| D2 | CWV PageSpeed ingest | `ptt_seo/cwv.py`, `seo_cwv_snapshots` |
| D3 | Crawl import log + stale reminders | `ptt_seo/crawl_reminder.py`, `seo_crawl_import_log` |
| D4 | Teams webhook | `PTT_SEO_TEAMS_WEBHOOK`, `ptt_seo/teams_notify.py` |
| D5 | AEO scheduled scan + auto draft | `ptt_seo/aeo_schedule.py` |

DDL: `deploy/sql/seo_aeo_gate_d.sql` · Schema helper: `ptt_seo/gate_d_schema.py`

## Env

```bash
# D2 CWV
PTT_CWV_ENABLED=1
PAGESPEED_API_KEY=...          # hoặc GOOGLE_PAGESPEED_API_KEY
PTT_CWV_STUB=1                 # dev/test without API key
PTT_CWV_PER_CLIENT=3
PTT_CWV_MAX_CLIENTS=20

# D3 Crawl reminder
PTT_CRAWL_REMINDER_ENABLED=1
PTT_CRAWL_REMINDER_DAYS=30

# D4 Teams (song song Slack)
PTT_SEO_TEAMS_WEBHOOK=https://outlook.office.com/webhook/...

# D5 AEO schedule
PTT_AEO_SCHEDULE_ENABLED=1
PTT_AEO_AUTO_DRAFT_ENABLED=1   # tạo content brief_ready khi brand_visible=0
PTT_AEO_SCHEDULE_MAX_CLIENTS=10
```

## Cron / systemd

Gate D chạy trong **weekly cron** (`run_weekly_cron`) và có bundle riêng:

```bash
curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://host/api/v1/seo/cron/gate-d

./scripts/seo_aeo_cron_gate_d.sh
```

Timer VPS:

```bash
sudo cp deploy/ptt-seo-gate-d.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now ptt-seo-gate-d.timer
```

## Grafana (D1)

1. Import `deploy/grafana/seo-ops-dashboard.json` — chọn ClickHouse datasource.
2. Variables: `customer_id`, `days` (7/28/90).
3. Panels: GSC clicks/impressions, content published, critical issues, AEO coverage.
4. Import alert rules `deploy/grafana/seo-ops-alert-rules.json` — gán contact point Slack/Teams.

Chi tiết export ClickHouse: [`seo-aeo-clickhouse-bi.md`](seo-aeo-clickhouse-bi.md).

## Pilot checklist

- [ ] ClickHouse export 7 ngày có `aeo_coverage_pct` facts
- [ ] Grafana dashboard hiển thị đúng 1 pilot client
- [ ] CWV stub hoặc PageSpeed key — snapshot trong `seo_cwv_snapshots`
- [ ] Import crawl CSV → log `seo_crawl_import_log`; client stale → alert
- [ ] Teams webhook nhận test alert từ `/api/v1/seo/automations/run`
- [ ] Weekly AEO schedule tạo draft cho query gap (nếu `PTT_AEO_AUTO_DRAFT_ENABLED=1`)

## Staging deploy (timer)

Từ máy có SSH tới staging VPS:

```bash
cd /var/www/ptt   # hoặc repo local

# 1) Dry-run (schema + env merge, chưa bật timer)
PTT_VPS_HOST=<staging-ip-or-host> APPLY=0 ./scripts/staging_seo_gate_d_deploy.sh

# 2) Sync code local nếu chưa push git
LOCAL_SYNC=1 PTT_VPS_HOST=<host> APPLY=0 ./scripts/staging_seo_gate_d_deploy.sh

# 3) Cài timer + smoke one-shot
LOCAL_SYNC=1 PTT_VPS_HOST=<host> APPLY=1 ./scripts/staging_seo_gate_d_deploy.sh
```

Thủ công trên VPS (đã có code):

```bash
cd /var/www/ptt
grep -q PTT_CWV_STUB deploy/env.staging-seo-gate-d.example && \
  bash -c 'while read -r l; do k="${l%%=*}"; grep -q "^${k}=" .env 2>/dev/null || echo "$l" >> .env; done < <(grep -v "^#" deploy/env.staging-seo-gate-d.example | grep "=")'
./scripts/apply_seo_gate_d_schema.sh
sudo ./scripts/install_seo_gate_d_systemd.sh
sudo systemctl enable --now ptt-seo-gate-d.timer
sudo systemctl start ptt-seo-gate-d.service
journalctl -u ptt-seo-gate-d.service -n 30 --no-pager
systemctl list-timers --no-pager 'ptt-seo-gate-d*'
```

Env mẫu staging: `deploy/env.staging-seo-gate-d.example` (`PTT_CWV_STUB=1` cho pilot không cần PageSpeed key).

## Rollback

```bash
sudo systemctl disable --now ptt-seo-gate-d.timer
PTT_CWV_ENABLED=0 PTT_AEO_SCHEDULE_ENABLED=0 PTT_CRAWL_REMINDER_ENABLED=0
```

Không drop bảng Gate D trên PG trừ khi rollback schema có kế hoạch.
