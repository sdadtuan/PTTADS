# SEO/AEO — ClickHouse BI export (Phase 5D)

## Mục tiêu

Xuất **SEO daily facts** từ PG (`seo_aeo`) sang ClickHouse bảng `ptt.seo_daily_facts` để Grafana/BI query.

## Thành phần

| Thành phần | Path |
|------------|------|
| Export script | `scripts/export_seo_facts_clickhouse.sh` |
| DDL ClickHouse | `deploy/clickhouse/init-seo-daily-facts.sql` |
| systemd oneshot | `deploy/ptt-seo-clickhouse-export.service` |
| systemd timer | `deploy/ptt-seo-clickhouse-export.timer` (04:00 VN hàng ngày) |
| Grafana panel mẫu | `deploy/grafana/seo-gsc-clicks-panel.json` | ✅ legacy single panel |
| **Full Grafana dashboard** | `deploy/grafana/seo-ops-dashboard.json` | ✅ Gate D |
| **Alert rules mẫu** | `deploy/grafana/seo-ops-alert-rules.json` | ✅ Gate D |

## Cài trên VPS

```bash
sudo cp deploy/ptt-seo-clickhouse-export.service deploy/ptt-seo-clickhouse-export.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ptt-seo-clickhouse-export.timer
```

`.env` cần:

- `CLICKHOUSE_URL`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`
- `SEO_AEO_DB=pg` (prod)
- `DATABASE_URL` (PG seo_aeo)

Chạy thủ công:

```bash
sudo systemctl start ptt-seo-clickhouse-export.service
journalctl -u ptt-seo-clickhouse-export.service -n 50 --no-pager
```

## Grafana

1. Import **`deploy/grafana/seo-ops-dashboard.json`** (Gate D — full dashboard với `customer_id` + `days`).
2. Hoặc panel đơn **`seo-gsc-clicks-panel.json`** nếu chỉ cần 1 chart.
3. Gán datasource ClickHouse (plugin `grafana-clickhouse-datasource`).
4. Import alert rules **`deploy/grafana/seo-ops-alert-rules.json`** — gán contact point Slack/Teams.
5. Metrics trong facts: `gsc_clicks`, `gsc_impressions`, `content_published`, `critical_issues_open`, `aeo_coverage_pct`.

Runbook Gate D: [`seo-aeo-gate-d.md`](seo-aeo-gate-d.md).

## Kiểm tra nhanh

```bash
curl -s "http://127.0.0.1:8123/?query=SELECT%20count()%20FROM%20ptt.seo_daily_facts"
```

## Rollback

```bash
sudo systemctl disable --now ptt-seo-clickhouse-export.timer
```

Không xóa bảng ClickHouse trừ khi BI team yêu cầu — dữ liệu lịch sử có thể tái export bằng `FACT_DATE=YYYY-MM-DD`.
