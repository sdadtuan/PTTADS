# Hướng dẫn sử dụng & triển khai phân hệ Email Marketing Ops

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Đối tượng:** Admin VPS, Head CRM/Email, AM, vận hành deliverability, agency ops  
> **Phạm vi:** Setup staging/prod + hướng dẫn màn hình ops-web `/email/*` (canonical — **không Flask**)  
> **URL staff:** `https://ops.pttads.vn/email/*` · `https://rs.pttads.vn/email/*`  
> **Spec:** [`SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md`](SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md) · [`SPEC_UI_UX_EMAIL_MARKETING.md`](SPEC_UI_UX_EMAIL_MARKETING.md) · [`EMAIL_MARKETING_COMPLETION_ROADMAP.md`](EMAIL_MARKETING_COMPLETION_ROADMAP.md)

---

## 1. Tổng quan

Email Marketing Enterprise OS trên PTTADS:

```
Capture → Consent → Segment → Template → Campaign → Preflight → Approve → Send
         → Engagement → Deliverability → Reports → Governance
```

| Lớp | Thành phần |
|-----|------------|
| Staff UI | ops-web `/email/*` (E-01…E-13) |
| Staff API | Nest `ptt-crm-api` `/api/v1/email/*` |
| Workers | `ptt_email/` + `ptt_worker` job queue |
| Data | PostgreSQL `email_mkt.*` |
| ESP | SendGrid / Mailgun (dry-run mặc định dev) |

**Flask `/crm/email/*`:** không tồn tại — nginx redirect → ops-web.

---

## 2. Bật tính năng (env)

| Flag | Mục đích | Giai đoạn |
|------|----------|-----------|
| `PTT_EMAIL_ENABLED=1` | Nest module + ops-web nav | B1 |
| `NEXT_PUBLIC_PTT_EMAIL_ENABLED=1` | Hiện menu Email trên ops-web | B1 |
| `PTT_EMAIL_SEND_ENABLED=1` | Gửi ESP thật | B2 (sau soak) |
| `PTT_EMAIL_PORTAL_ENABLED=1` | Portal client approve | B3 |
| `PTT_EMAIL_JOURNEYS_ENABLED=1` | Journey scan timer | B4 |
| `PTT_EMAIL_DELIVERABILITY_ALERTS=1` | Slack/Teams khi hub load (P1.3) | P1+ |
| `PTT_EMAIL_SLACK_WEBHOOK` / `PTT_EMAIL_TEAMS_WEBHOOK` | Webhook cảnh báo deliverability | P1+ |
| `PTT_EMAIL_GRAFANA_URL` | Embed Grafana trên E-12 | P1+ |
| `CLICKHOUSE_URL` | BI export facts | EM-3 |

Template env: `deploy/env.em5-prod.example`, `deploy/env.em5-prod-send.example`.

---

## 3. Phân quyền RBAC

7 caps `crm_email_mkt_*`: `view`, `write`, `settings`, `deliverability`, `reports`, `compliance`, `approve`.

Seed prod: `scripts/seed_staff_email_mkt_permissions.py`.

---

## 4. Màn hình ops-web (P1 UX parity)

| ID | Route | Chức năng chính |
|----|-------|-----------------|
| E-01 | `/email/hub` | KPI, alerts (→ E-11), send calendar |
| E-02 | `/email/clients` | Danh sách client + workspace |
| E-03 | `/email/clients/:id` | Workspace settings, ESP, caps |
| E-04 | `/email/contacts` | Danh bạ + import CSV |
| E-05 | `/email/consent` | Consent registry |
| E-06 | `/email/suppression` | Suppression master |
| E-07 | `/email/segments` | Segment builder — **Rules / Static / Lifecycle / RFM / Behavior** (P1.2) |
| E-08 | `/email/templates` | Template studio |
| E-09 | `/email/campaigns` | Campaign console + preflight |
| E-10 | `/email/journeys` | Journey automation |
| E-11 | `/email/deliverability` | DNS verify, warm-up, **domain onboarding wizard** (P1.5) |
| E-12 | `/email/reports` | Analytics, ClickHouse export, **Grafana embed** (P1.4) |
| E-13 | `/email/governance` | **CRUD global rules + audit log** (P1.1) |
| — | `/email/gate-a` | Gate A readiness (EM-5) |

---

## 5. Luồng nghiệp vụ chính

### 5.1 Onboard client mới (AM)

1. CRM: tạo/chọn customer → map client UUID.
2. `/email/clients/:id?tab=settings` — workspace: from/reply, ESP, daily cap.
3. `/email/deliverability` — **Domain wizard** bước 1→3: domain → DNS records → Verify.
4. `/email/contacts` — import hoặc capture API.
5. `/email/consent` — xác nhận opted-in marketing.

### 5.2 Broadcast campaign (Flow F1)

1. `/email/segments` — tạo segment (lifecycle/RFM/behavior), **Compute**.
2. `/email/templates` — HTML + unsubscribe link bắt buộc.
3. `/email/campaigns` — draft → preflight → staff approve → schedule/send.
4. Hub — theo dõi complaint rate, queue lag.

### 5.3 Governance (P1.1)

- `/email/governance` — thêm/sửa/xóa global rules (`frequency_cap_7d`, `quiet_hours`, …).
- Audit log hiển thị 50 bản ghi gần nhất (before/after JSON).

### 5.4 Deliverability alerts (P1.3)

- Hub load gọi `hubWithAlerts` → post Slack/Teams nếu webhook configured.
- Banner hub link → `/email/deliverability`.

---

## 6. Gates & QA

| Gate | Script |
|------|--------|
| EM-0 hub | `./scripts/phase0_email_hub_kickoff_gate.sh` |
| EM-5 Gate A | `./scripts/phase5_email_prod_pilot_gate.sh` |
| §13 handoff | `./scripts/email_handoff_gate.sh` |
| **P1 UX parity** | `./scripts/email_p1_gate.sh` |

Playwright E2E: `services/ops-web/e2e/email-handoff.spec.ts` (hub, segments RFM, deliverability wizard, reports BI, governance audit).

---

## 7. Grafana & BI (P1.4)

1. Import `deploy/grafana/email-ops-dashboard.json`.
2. Set `PTT_EMAIL_GRAFANA_URL=https://grafana.example/d/email-ops`.
3. `/email/reports` — card **BI & Grafana** + iframe (nếu URL set).
4. API: `GET /api/v1/email/reports/bi-status`.

---

## 8. Xử lý sự cố

| Triệu chứng | Hành động |
|-------------|-----------|
| Hub banner schema chưa apply | `./scripts/apply_pg_ddl_email_mkt.sh` |
| Complaint rate cao | E-11 pause domain → E-06 review suppression |
| Preflight fail unsub | Template thiếu `{{unsubscribe_url}}` |
| Send queue lag | Worker `ptt_email/sender.py` + job_queue health |
| Grafana trống | Kiểm tra `PTT_EMAIL_GRAFANA_URL`, ClickHouse export |

Runbook chi tiết: [`runbooks/email-deliverability-incident.md`](runbooks/email-deliverability-incident.md), [`runbooks/email-marketing-prod-pilot-checklist.md`](runbooks/email-marketing-prod-pilot-checklist.md).

---

## 9. Tài liệu in & đào tạo

- Checklist A4 hàng ngày: [`forms/email-marketing-ops-checklist-a4.html`](forms/email-marketing-ops-checklist-a4.html)
- Training PPT: `python3 scripts/generate_email_marketing_training_pptx.py` → `docs/Email_Marketing_Ops_Training.pptx`

---

## 10. Checklist go-live (tóm tắt)

- [ ] DDL `email_mkt.*` applied trên prod PG
- [ ] RBAC caps seeded
- [ ] ≥1 client pilot: domain verified + ESP keys
- [ ] Soak ≥7 ngày (send disabled → enabled staged)
- [ ] Gate A sign-off: `docs/evidence/em5-email-pilot-signoff.json`
- [ ] P1 gate PASS: `./scripts/email_p1_gate.sh`
