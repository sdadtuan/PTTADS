# Zalo Ads Ops — Wave Z3 handover (Z3-9)

> Hướng dẫn vận hành nội bộ cho kênh Zalo Ads sau Wave Z1–Z3.

## Màn hình chính

| Màn hình | Route | Mục đích |
|----------|-------|----------|
| Zalo hub | `/zalo/zalo-ads` | CPL/CPA, alerts, export CSV/PDF |
| Leads + form poll | `/zalo/leads` | Form sync cursor, poll now |
| Combined CPL | `/meta/ads-combined` | So sánh Meta/Google/Zalo |
| Creative Hub | `/crm/creatives` | Gửi duyệt creative tag `channel=zalo` |
| Launch QA | Lifecycle tab **Launch QA** | Auto-check token + form IDs |

## Workflow launch Zalo

1. **Channels** — thêm Zalo OA, OAuth token, cấu hình `form_ids`
2. **Hub map** — map campaign → client (`/crm/hub`)
3. **Sync insights** — job `zalo_insights_sync` (T-1)
4. **Form poll** — cron `zalo_form_lead_poll` ≤15 phút (hoặc Poll now trên `/zalo/leads`)
5. **Creative** — submit với `channel=zalo` → client duyệt portal
6. **Launch QA** — checklist auto: `zalo_oauth_token`, `zalo_form_ids_configured`
7. **Go-live manual** — launch trên Zalo UI, map campaign ID
8. **CRM Won** — cập nhật hub CPA (Z2-B7)

## Alerts (Z3)

Bật: `PTT_ZALO_ALERTS_ENABLED=1` (cần bảng `meta_alerts` v4).

| Rule | alert_type |
|------|------------|
| CPL > target + buffer | `cpl_high` |
| Zero leads 24h (có spend) | `zero_leads_24h` |
| CTR drop vs T-1 | `ctr_drop` |

Slack: `PTT_ZALO_SLACK_WEBHOOK` — link banner `/zalo/zalo-ads`.

Job: `zalo_alerts_eval` (enqueue sau `zalo_insights_sync`).

## Báo cáo KH (Z3-6)

- CSV: `GET /api/v1/zalo-ads/hub/export`
- PDF: `GET /api/v1/zalo-ads/hub/export?format=pdf`

## Portal budget approve (Z3-10)

Reuse flow **Campaign Write / budget brief** trên Launch QA lifecycle:

- AM submit budget trên lifecycle → GDKD duyệt Campaign Write Hub
- Client creative approve: portal `/creatives` (shared, không cần route Zalo riêng)
- Milestone notify: `notification_inbox` category `campaign_milestone` / `creative`

## Env staging

```bash
PTT_ZALO_INSIGHTS_SYNC=1
PTT_ZALO_FORM_POLL=1
PTT_ZALO_ALERTS_ENABLED=1
PTT_ZALO_SLACK_WEBHOOK=   # optional
```

Gate: `./scripts/staging_zalo_wave_z2_gate.sh` (+ Z3 DDL `./scripts/apply_pg_ddl_zalo_z3.sh`).
