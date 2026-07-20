# SEO/AEO Ops — VPS cron runbook (P3c)

## Env

```bash
# Bắt buộc trên VPS (chọn một trong các secret CRM hoặc riêng)
PTT_SEO_CRON_SECRET=your-strong-secret

# Tùy chọn — gọi HTTP thay vì Python trực tiếp
PTT_SEO_CRON_BASE_URL=https://crm.example.com

PTT_GSC_SYNC_ENABLED=1
PTT_GA4_SYNC_ENABLED=1
PTT_FRESHNESS_SCAN_ENABLED=1
PTT_SERP_SCHEDULE_ENABLED=1
PTT_SERP_SCHEDULE_PER_CLIENT=5
SMTP_HOST=...   # cho scheduled report email
```

## Crontab mẫu

```cron
# GSC + GA4 + report schedules — 06:15 hàng ngày
15 6 * * * cd /opt/pttads && ./scripts/seo_aeo_cron_daily.sh >> /var/log/seo_aeo_cron_daily.log 2>&1

# Freshness scan — Chủ nhật 03:00
0 3 * * 0 cd /opt/pttads && ./scripts/seo_aeo_cron_weekly.sh >> /var/log/seo_aeo_cron_weekly.log 2>&1

# SERP capture (optional standalone) — Chủ nhật 05:00
0 5 * * 0 cd /opt/pttads && ./scripts/sync_seo_serp_weekly.sh >> /var/log/seo_serp_capture.log 2>&1
```

## API (Bearer hoặc localhost)

```bash
curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://host/api/v1/seo/cron/daily?days=28

curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://host/api/v1/seo/cron/weekly

curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://host/api/v1/seo/cron/serp
```

## Scripts riêng lẻ (legacy, vẫn dùng được)

| Script | Tần suất |
|--------|----------|
| `scripts/sync_seo_gsc_daily.sh` | Daily GSC only |
| `scripts/sync_seo_ga4_daily.sh` | Daily GA4 only |
| `scripts/sync_seo_freshness_weekly.sh` | Weekly freshness only |
| `scripts/sync_seo_serp_weekly.sh` | Weekly SERP capture only (Gate B) |
| `scripts/seo_aeo_cron_daily.sh` | **All daily jobs** |
| `scripts/seo_aeo_cron_weekly.sh` | **Weekly freshness + SERP** |

## Worker jobs

`ptt-worker` xử lý job queue: `seo_gsc_sync`, `seo_ga4_sync`, `seo_freshness_scan`, `seo_report_schedules`.
Cron script gọi trực tiếp Python khi không set `PTT_SEO_CRON_BASE_URL`.
