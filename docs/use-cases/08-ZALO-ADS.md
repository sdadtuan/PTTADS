# Use Case — Zalo Ads Operating System

> **Prefix:** ZALO · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md) · **Spec:** [`SPEC_ZALO_ADS_OPERATING_SYSTEM.md`](../SPEC_ZALO_ADS_OPERATING_SYSTEM.md)  
> **Nguồn:** Use Case spec Zalo Ads agency quy mô lớn (23 UC) — map vào PTTADS

---

## Tác nhân

| Actor | Vai trò PTTADS |
|-------|----------------|
| Admin | Super Admin, platform config |
| Manager | AM Lead, GDKD |
| Media Buyer | Performance executive |
| Creative | Creative Lead |
| Account Manager | AM |
| Analyst | BI / reporting |
| Client | Portal Viewer / Approver |
| System | Webhook, worker, scheduler |
| CRM | Internal leads API |
| Zalo Ads/OA | External platform |

---

## ZALO-UC-001 — Kết nối tài khoản Zalo Ads / OA

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Tracking/Tech, AM |
| **Map nguồn** | UC-04 |
| **Priority** | P0 |
| **Wave** | Z1 |

**Preconditions:** Agency client tồn tại; Zalo Developer App đã tạo.

**Main flow:**

1. AM mở `/agency/clients/[id]?tab=channels`.
2. Thêm channel account `zalo` + OA id / ad account id.
3. Bấm **Connect Zalo** → OAuth → token lưu vault.
4. Cấu hình webhook Zalo → `POST /webhooks/zalo`.
5. Hệ thống validate credential; hiển thị token status.

**Extensions:**

- **E1 — OAuth fail:** Banner lỗi; giữ stub credential_ref dev.
- **E2 — Pilot client only:** `PTT_ZALO_ADS_PILOT` chặn client ngoài list.

**Postconditions:** `client_channel_accounts` row `channel=zalo` có token hợp lệ.

**Business rules:** BR-ZALO-01 — Một OA có thể gắn nhiều form; lưu trong `meta.form_ids`.

**Traceability:** `POST /clients/:id/channel-accounts`, `/zalo-ads/oauth/*`

---

## ZALO-UC-002 — Hub map campaign Zalo ↔ CRM

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer |
| **Map nguồn** | UC-07 (partial) |
| **Priority** | P0 |
| **Wave** | Z0 ✅ |

**Main flow:**

1. Buyer mở `/agency/clients/[id]?tab=campaigns`.
2. Filter channel **Zalo**.
3. Map external campaign id → hub contract / target CPL.
4. Unmapped campaigns hiển thị vàng trên hub.

**Postconditions:** `hub_campaign_map.channel='zalo'`.

**Traceability:** `HubCampaignMapsPanel`, `POST /hub-campaign-maps`

---

## ZALO-UC-003 — Sync insights Zalo → daily_performance

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System, Media Buyer |
| **Map nguồn** | UC-17 (data layer) |
| **Priority** | P0 |
| **Wave** | Z1 |

**Main flow:**

1. Buyer bấm **Sync Zalo insights** hoặc cron T+1.
2. Job `zalo_insights_sync` chạy qua `ptt_worker`.
3. Adapter lấy metrics campaign-level → normalize.
4. Upsert `daily_performance` (`channel=zalo`).
5. Cập nhật `zalo_insights_sync_state`.

**Extensions:**

- **E1 — Token expired:** Job fail; hub 🔴; alert AM.
- **E2 — Stub mode:** Sinh dữ liệu pilot.

**Postconditions:** Hub CPL tính được spend/leads cùng kỳ.

**Traceability:** `POST /clients/:id/sync/zalo-insights`, job queue

---

## ZALO-UC-004 — Xem hub CPL Zalo (staff)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer, AM, Analyst |
| **Map nguồn** | UC-17 |
| **Priority** | P0 |
| **Wave** | Z1 |

**Main flow:**

1. Mở `/zalo/zalo-ads`.
2. Filter client, date range T-7/T-30.
3. Xem KPI Spend, Leads, CPL, CTR.
4. Drill-down campaign; export CSV.

**Extensions:**

- **E1 — Unmapped spend:** Yellow banner; CPL client exclude unmapped.

**Postconditions:** KPI khớp closed-loop SYS-UC-002 (channel=zalo).

**Traceability:** `GET /zalo-ads/hub`, `/zalo/zalo-ads`

---

## ZALO-UC-005 — Portal xem performance Zalo

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Viewer |
| **Map nguồn** | UC-21 |
| **Priority** | P0 |
| **Wave** | Z1 |

**Main flow:**

1. Client login portal.
2. Mở `/zalo`.
3. Xem KPI read-only scoped `client_id`.
4. Không thấy client khác.

**Postconditions:** JWT scope enforced.

**Traceability:** `portal-web/src/app/zalo/page.tsx`, `GET /performance?channel=zalo`

---

## ZALO-UC-006 — Tạo brief chiến dịch Zalo

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Client |
| **Map nguồn** | UC-06 |
| **Priority** | P1 |
| **Wave** | Z3 |

**Main flow:**

1. AM mở lifecycle stage Consult/Proposal.
2. Nhập mục tiêu, ngân sách, audience, form lead type.
3. Upload tài liệu tham khảo.
4. Chuyển sang Buyer lập campaign.

**Traceability:** `/crm/service-delivery/[id]`, consult brief panel

---

## ZALO-UC-007 — Tạo campaign Zalo (draft nội bộ)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer |
| **Map nguồn** | UC-07, UC-08 |
| **Priority** | P1 |
| **Wave** | Z3 |

**Main flow:**

1. Chọn client + Zalo account.
2. Nhập objective, budget, schedule, form lead.
3. Gắn creative assets từ thư viện CRM.
4. Lưu draft `pending_approval`.

**Extensions:**

- **E1 — v1 manual:** Buyer tạo trên Zalo Ads UI; map ID vào hub (ZALO-UC-002).

**Traceability:** `/zalo/campaigns` (future), CRM creatives

---

## ZALO-UC-008 — Gửi duyệt nội dung chiến dịch

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer, Manager, Client Approver |
| **Map nguồn** | UC-09, UC-22 |
| **Priority** | P1 |
| **Wave** | Z3 |

**Main flow:**

1. Buyer submit creative → `pending_client`.
2. Client duyệt trên portal `/creatives`.
3. Manager approve budget nếu vượt ngưỡng.
4. Launch QA pass (shared CRM module).

**Traceability:** SYS-UC-003, SYS-UC-004, `/crm/creatives`

---

## ZALO-UC-009 — Triển khai chiến dịch lên Zalo Ads

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer, System |
| **Map nguồn** | UC-10 |
| **Priority** | P2 |
| **Wave** | Z4 |

**Main flow:**

1. Hệ thống build payload Zalo API.
2. Queue campaign-writes → worker execute.
3. Nhận external campaign id → auto hub map.
4. Audit log + notify AM.

**Extensions:**

- **E1 — API không hỗ trợ write:** Manual launch + map (v1 workaround).

**Traceability:** `campaign-writes`, Temporal (future)

---

## ZALO-UC-010 — Tạm dừng / cập nhật / dừng chiến dịch

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer |
| **Map nguồn** | UC-11 |
| **Priority** | P2 |
| **Wave** | Z4 |

**Main flow:** Pause/resume/update budget qua API hoặc manual + ghi audit.

---

## ZALO-UC-011 — Webhook lead Zalo → CRM

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Actor phụ** | CSKH |
| **Map nguồn** | UC-12 |
| **Priority** | P0 |
| **Wave** | Z0 ✅ |

**Main flow:**

1. Zalo POST webhook payload.
2. Verify HMAC signature.
3. Parse → normalize lead.
4. Dedup → insert `crm_leads` (`channel=zalo`).
5. Return 200.

**Extensions:**

- **E1 — Invalid signature:** 401 + alert.

**Postconditions:** Lead visible `/crm/leads?channel=zalo`.

**Traceability:** `POST /webhooks/zalo`, `zalo-webhook.parser.ts`

---

## ZALO-UC-012 — Poll lead từ form Zalo (API form/get)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Map nguồn** | UC-12 |
| **Priority** | P0 |
| **Wave** | Z2 |

**Main flow:**

1. Worker `zalo_form_lead_poll` đọc cursor.
2. Gọi `openapi.zalo.me/v2.0/oa/form/get`.
3. Normalize + dedup + push CRM.
4. Advance cursor.

**Postconditions:** Lead SLA ≤ 15 phút kể từ submit form.

**Traceability:** `zalo_lead_form_sync_cursor`, `POST /zalo/forms/:id/poll`

---

## ZALO-UC-013 — Chống trùng và chuẩn hóa lead

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Map nguồn** | UC-13 |
| **Priority** | P0 |
| **Wave** | Z0/Z2 |

**Main flow:** Phone/email normalize; fingerprint dedup; flag `is_duplicate`; log `zalo_lead_events`.

**Business rules:** BR-ZALO-02 — Cùng phone + client + 24h → duplicate.

---

## ZALO-UC-014 — Đẩy lead sang CRM pipeline

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System, CSKH |
| **Map nguồn** | UC-14, UC-15 |
| **Priority** | P0 |
| **Wave** | Z0 ✅ |

**Main flow:** Lead auto-assign owner; CSKH xử lý trên `/crm/leads/[id]`; timeline update.

---

## ZALO-UC-015 — Đồng bộ trạng thái CRM ngược về Zalo hub

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Map nguồn** | UC-16 |
| **Priority** | P1 |
| **Wave** | Z2 |

**Main flow:** CRM Won/Lost → cập nhật conversion metrics trên hub CPL/CPA.

---

## ZALO-UC-016 — Xuất báo cáo khách hàng

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Analyst |
| **Map nguồn** | UC-18 |
| **Priority** | P1 |
| **Wave** | Z2 |

**Main flow:** Export CSV/PDF từ hub; email client (shared SYS-UC-005 pattern).

---

## ZALO-UC-017 — Cảnh báo chiến dịch bất thường

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System, Manager, Buyer |
| **Map nguồn** | UC-19 |
| **Priority** | P1 |
| **Wave** | Z3 |

**Main flow:**

1. Rule: CPL > target_cpl_vnd, CTR drop 30%, zero leads 24h.
2. Notification Slack/email.
3. Hub banner link client.

**Traceability:** Alert module (P1 Slack/Teams)

---

## ZALO-UC-018 — Phân tích đa chiều (client/creative)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Analyst |
| **Map nguồn** | UC-20 |
| **Priority** | P2 |
| **Wave** | Z4 |

**Main flow:** Drill hub + export; future DWH/Grafana.

---

## ZALO-UC-019 — Client duyệt ngân sách & nội dung

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Approver |
| **Map nguồn** | UC-22 |
| **Priority** | P1 |
| **Wave** | Z3 |

**Traceability:** PORTAL creatives approval (shared)

---

## ZALO-UC-020 — Thông báo tiến độ chiến dịch

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System, AM, Client |
| **Map nguồn** | UC-23 |
| **Priority** | P1 |
| **Wave** | Z3 |

**Main flow:** Notify on approve, launch, error, KPI milestone.

---

## ZALO-UC-021 — Onboard Zalo trong orchestrator

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM |
| **Priority** | P1 |
| **Wave** | Z2 |

**Main flow:**

1. Tab onboard orchestrator hiển thị steps Zalo.
2. Auto-detect: account, token, form, sync green, first lead.
3. Deep-link từng bước.

**Traceability:** `onboarding-orchestrator` extension, SYS-UC-001

---

## Ma trận MVP (Z0 + Z1 + Z2)

| UC | Tên | Priority |
|----|-----|----------|
| ZALO-UC-001 | Kết nối Zalo Ads/OA | P0 |
| ZALO-UC-002 | Hub map campaign | P0 |
| ZALO-UC-003 | Sync insights | P0 |
| ZALO-UC-004 | Hub CPL staff | P0 |
| ZALO-UC-005 | Portal performance | P0 |
| ZALO-UC-011 | Webhook lead | P0 |
| ZALO-UC-012 | Form poll | P0 |
| ZALO-UC-013 | Dedup lead | P0 |
| ZALO-UC-014 | CRM pipeline | P0 |
| ZALO-UC-017 | Alerts | P1 |
| ZALO-UC-021 | Onboard orchestrator | P1 |

---

## Traceability cross-module

| SYS UC | Liên kết Zalo |
|--------|---------------|
| SYS-UC-001 Onboard E2E | Thêm bước Zalo trong orchestrator |
| SYS-UC-002 Closed-loop | CPL Zalo trên hub + portal |
| SYS-UC-003 Launch governance | Creative + Launch QA trước Zalo push |
| SYS-UC-004 Client approval | Portal approve Zalo creative |
| SYS-UC-005 Báo cáo định kỳ | Export hub Zalo |

**Chi tiết thao tác:** [`actions/08-ZALO-ACTIONS.md`](actions/08-ZALO-ACTIONS.md)
