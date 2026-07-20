# SEO/AEO — P3 backlog defer policy

## Quy tắc

Các hạng mục **P3 backlog** (ngoài P3a–f đã ship) **không triển khai** cho đến khi:

- P2 Enterprise depth đã **soak production ≥ 7 ngày** liên tục
- Không có incident P1/P2 mở liên quan SEO/AEO Ops
- AM/MKT sign-off UAT P2 trên prod

## P2 đã ship (baseline soak)

- Slack alerts: `critical_issues`, `report_schedule_failed`, `sync_failed`, `freshness_urgent`
- RBAC §9: section keys riêng (`crm_seo_aeo_*`)
- Reports S-12: sparkline + bar charts
- Research depth: SERP stub, clusters, pages sync GSC
- 5D BI: systemd timer + Grafana panel mẫu

## P3 backlog (Gate C — shipped code, prod pilot TBD)

- ✅ SerpAPI / DataForSEO (`PTT_SERP_PROVIDER`) — [`runbooks/seo-aeo-p3-gate-c.md`](seo-aeo-p3-gate-c.md)
- ✅ Advanced entity graph UI (filter, link form, node detail)
- ✅ Multi-tenant report white-label (`brand_guidelines`)
- ✅ Portal SEO widgets API (`/internal/portal/widgets`)
- ✅ Temporal `SeoContentApprovalWorkflow` (`PTT_SEO_CONTENT_TEMPORAL=1`)

Prod enable sau checklist Gate C runbook.

## Gate checklist (AM + DevOps)

- [ ] Ngày cutover P2 prod ghi nhận: ___________
- [ ] Ngày soak đủ 7 ngày: ___________
- [ ] Cron GSC/GA4/freshness OK 7 ngày (`journalctl` / runbook cron)
- [ ] Slack webhook test alert OK
- [ ] ClickHouse export timer OK ≥ 3 lần liên tiếp
- [ ] Sign-off: ___________

Sau khi gate pass → tạo ticket P3 sprint riêng, không gộp hotfix P2.
