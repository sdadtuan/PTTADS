# Chi tiết hành động — Zalo Ads (ZALO)

> **UC gốc:** [`../08-ZALO-ADS.md`](../08-ZALO-ADS.md)  
> **Spec:** [`../../SPEC_ZALO_ADS_OPERATING_SYSTEM.md`](../../SPEC_ZALO_ADS_OPERATING_SYSTEM.md)

---

## ZALO-UC-001 — Kết nối tài khoản Zalo Ads / OA

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Tracking | `/login` | Đăng nhập ops-web | email, password | JWT + cap | ✓ `crm_agency` |
| 2 | Tracking | `/agency/clients/[id]?tab=channels` | **+ Thêm channel** → chọn **Zalo** | external_account_id, display_name | Row channel | ✓ |
| 3 | Tracking | Same | Nhập **OA ID** (meta) | oa_id digits | Lưu meta JSON | ✓ |
| 4 | Tracking | Same | **Connect Zalo** OAuth | redirect Zalo | Token vault | ✓ token valid |
| 5 | Tracking | Zalo Developer Console | Cấu hình webhook URL | `https://api…/webhooks/zalo` | Verify OK | ✓ |
| 6 | Tracking | Same tab | **Sync Zalo insights** (smoke test) | — | Job queued | ✓ job success |
| 7 | AM | `/agency/clients/[id]?tab=onboard` | Kiểm tra orchestrator step **Zalo account** | — | Auto ✓ hoặc pending | ✓ |

#### Nhánh E1 — Pilot only
Bước 4: Client không trong `PTT_ZALO_ADS_PILOT_CLIENTS` → banner stub; AM ghi chú manual.

#### Tiêu chí nghiệm thu
- [ ] Channel row `zalo` tồn tại
- [ ] Token status **valid** trên UI
- [ ] Webhook test lead → CRM (ZALO-UC-011)

---

## ZALO-UC-002 — Hub map campaign Zalo

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/agency/clients/[id]?tab=campaigns` | Filter channel **Zalo** | — | List maps | ✓ |
| 2 | Buyer | Same | **+ Map campaign** | external_campaign_id, hub_campaign | Row created | ✓ |
| 3 | Buyer | `/zalo/zalo-ads` | Verify campaign **green** (mapped) | filter client | CPL row | ✓ unmapped=0 |

---

## ZALO-UC-003 — Sync insights Zalo

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/agency/clients/[id]?tab=channels` | **Sync Zalo insights** | — | Toast job enqueued | ✓ cap write |
| 2 | System | worker | Job `zalo_insights_sync` | client_id, T-1 | daily_performance rows | ✓ |
| 3 | Buyer | `/zalo/zalo-ads` | Refresh hub | T-7 | Spend/leads updated | ✓ sync 🟢 |

#### Nhánh E1 — Token expired
Bước 2 fail → hub 🔴 → Tracking re-OAuth bước 4 UC-001.

---

## ZALO-UC-004 — Xem hub CPL Zalo (staff)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/zalo/zalo-ads` | Mở hub | — | KPI cards load | ✓ `crm_zalo_ads` |
| 2 | Buyer | Same | Chọn **client** filter | client_id | Table scoped | ✓ |
| 3 | Buyer | Same | Chọn **T-7 / T-30** | date range | CPL recalc | ✓ |
| 4 | Buyer | Same | **Export CSV** | — | File download | ✓ export cap |
| 5 | AM | Same | Drill campaign unmapped | click row | Link → map tab | ✓ |

---

## ZALO-UC-005 — Portal performance Zalo

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Client | portal `/login` | Đăng nhập | credentials | JWT scoped | ✓ |
| 2 | Client | `/zalo` | Xem KPI cards | T-7/T-30 | Spend, Leads, CPL | ✓ read-only |
| 3 | Client | Same | Không thấy menu client khác | — | Nav scoped | ✓ tenant |

---

## ZALO-UC-011 — Webhook lead Zalo → CRM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | `POST /webhooks/zalo` | Nhận payload | Zalo JSON + HMAC | 200 OK | ✓ signature |
| 2 | System | — | Parse + dedup | phone, form_id | crm_leads row | ✓ |
| 3 | CSKH | `/crm/leads` | Filter source=zalo | — | Lead mới | ✓ |
| 4 | CSKH | `/crm/leads/[id]` | Log call, đổi status | note | Timeline | ✓ |

---

## ZALO-UC-012 — Poll lead form Zalo

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Admin | `/zalo/leads` | Tab **Form sync** | — | List forms + cursor | ✓ |
| 2 | System | worker | Cron poll `form/get` | oa_id, form_id | New leads | ✓ ≤15m SLA |
| 3 | Buyer | Same | **Poll now** (manual) | form_id | Job queued | ✓ write |
| 4 | CSKH | `/crm/leads` | Verify lead mới | filter zalo | Row | ✓ |

---

## ZALO-UC-008 — Gửi duyệt nội dung (cross-module)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Creative | `/crm/creatives` | Submit creative Zalo | files, copy | pending | ✓ |
| 2 | Creative Lead | Same | Internal approve | comment | approved internal | ✓ |
| 3 | Creative | Same | **Submit client approval** | — | pending_client | ✓ |
| 4 | Client | portal `/creatives` | **Approve** | note optional | approved | ✓ approver |
| 5 | Buyer | `/crm/launch-qa` | Pass Launch QA | checklist | passed | ✓ |
| 6 | Buyer | Manual / future wizard | Launch on Zalo + map ID | campaign id | hub green | ✓ |

---

## ZALO-UC-021 — Onboard Zalo (orchestrator)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]?tab=onboard` | Xem orchestrator compact | — | Zalo steps list | ✓ |
| 2 | AM | Link **Mở →** từng step | Deep-link channels/hub/zalo | — | Đúng màn hình | ✓ |
| 3 | AM | `/agency/clients/[id]?tab=onboard` | **Auto-sync checklist** | — | Items ticked | ✓ |
| 4 | AM | Same | **Activate client** khi đủ | confirm | status active | ✓ |

**Steps orchestrator (target Z2):**

| Step key | Label | Deep-link |
|----------|-------|-----------|
| `zalo_account` | Zalo ad account / OA | `?tab=channels` |
| `zalo_token` | Zalo OAuth token | `?tab=channels` |
| `zalo_form` | Lead form configured | `/zalo/leads` |
| `zalo_sync` | Insights sync green | `/zalo/zalo-ads` |
| `zalo_first_lead` | First lead in CRM | `?tab=leads` |

---

## Luồng end-to-end (tóm tắt 15 bước AM)

| # | Actor | Màn hình | Mục tiêu |
|---|-------|----------|-----------|
| 1 | AM | `/agency/clients/new` | Tạo client |
| 2 | AM | `/crm/service-delivery` | Lifecycle Onboard |
| 3 | Tracking | `?tab=channels` | Zalo account + OAuth |
| 4 | Tracking | Zalo Developer | Webhook URL |
| 5 | Buyer | `?tab=campaigns` | Hub map |
| 6 | Buyer | `/zalo/zalo-ads` | Sync + verify CPL |
| 7 | Creative | `/crm/creatives` | Submit creative |
| 8 | Client | portal `/creatives` | Approve |
| 9 | Buyer | Launch QA + Zalo UI | Go live |
| 10 | System | webhook/poll | Leads → CRM |
| 11 | CSKH | `/crm/leads` | Qualify → Won |
| 12 | AM | `/zalo/zalo-ads` | Báo cáo client |
| 13 | Client | portal `/zalo` | Xem KPI |
| 14 | AM | `?tab=onboard` | Activate client |
| 15 | AM | Handover A4 | Credential portal |

**Liên kết SYS:** [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md) — mở rộng nhánh Zalo song song Meta (bước 7–9).

---

## Gap vs PTTADS hiện tại

| Step | Trạng thái | Wave |
|------|------------|------|
| Channel zalo CRUD | ✅ Shipped | Z0 |
| Hub map zalo | ✅ Shipped | Z0 |
| Webhook lead | ✅ Shipped | Z0 |
| Hub `/zalo/zalo-ads` | ❌ | Z1 |
| Sync job | ❌ | Z1 |
| Portal `/zalo` | ❌ | Z1 |
| Form poll | ❌ | Z2 |
| Orchestrator zalo steps | ❌ | Z2 |
| Campaign write API | ❌ | Z4 |

Cập nhật gap: [`ACTION-GAP-ANALYSIS.md`](../ACTION-GAP-ANALYSIS.md) khi bắt đầu Wave Z1.
