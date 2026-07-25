# Chi tiết hành động — Zalo Ads (ZALO)

> **UC gốc:** [`../08-ZALO-ADS.md`](../08-ZALO-ADS.md)  
> **Spec:** [`../../SPEC_ZALO_ADS_OPERATING_SYSTEM.md`](../../SPEC_ZALO_ADS_OPERATING_SYSTEM.md)  
> **Ops handover:** [`../../huong-dan-zalo-ads-ops.md`](../../huong-dan-zalo-ads-ops.md)

---

## ZALO-UC-001 — Kết nối tài khoản Zalo Ads / OA

**Mục tiêu khách hàng:** *"Tài khoản Zalo Ads/OA được kết nối an toàn, sẵn sàng nhận lead và sync số liệu."*

**Actors:** Tracking/Tech, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Tracking | `/login` | Đăng nhập ops-web | email, password | JWT + cap | ✓ `crm_agency` |
| 2 | Tracking | `/agency/clients/[id]?tab=channels` | **+ Thêm channel** → chọn **Zalo** | external_account_id, display_name | Row channel | ✓ |
| 3 | Tracking | Same | Nhập **OA ID** (meta) | oa_id digits | Lưu meta JSON | ✓ |
| 4 | Tracking | Same | **Connect Zalo** OAuth | redirect Zalo | Token vault | ✓ token valid |
| 5 | Tracking | Zalo Developer Console | Cấu hình webhook URL | `https://api…/webhooks/zalo` | Verify OK | ✓ |
| 6 | Tracking | Same tab | **Sync Zalo insights** (smoke test) | — | Job queued | ✓ job success |
| 7 | AM | `/agency/clients/[id]?tab=onboard` | Kiểm tra orchestrator step **Zalo account** | — | Auto ✓ hoặc pending | ✓ |
| 8 | Tracking | `/zalo/leads` tab **Form sync** | Smoke: thêm form ID test | form_id | Cursor row | ✓ |

#### Nhánh E1 — Pilot only
Bước 4: Client không trong `PTT_ZALO_ADS_PILOT_CLIENTS` → banner stub; AM ghi chú manual.

#### Nhánh E2 — Token expired
Bước 6 fail → hub 🔴 → Tracking re-OAuth bước 4.

#### Tiêu chí nghiệm thu
- [ ] Channel row `zalo` tồn tại
- [ ] Token status **valid** trên UI
- [ ] Webhook test lead → CRM ([ZALO-UC-011](#zalo-uc-011--webhook-lead-zalo--crm))

---

## ZALO-UC-002 — Hub map campaign Zalo

**Mục tiêu khách hàng:** *"Mọi chi tiêu Zalo gắn đúng client để CPL/CPA chính xác."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/agency/clients/[id]?tab=campaigns` | Filter channel **Zalo** | — | List maps | ✓ |
| 2 | Buyer | Same | **+ Map campaign** | external_campaign_id, hub_campaign | Row created | ✓ |
| 3 | Buyer | `/zalo/zalo-ads` | Verify campaign **green** (mapped) | filter client | CPL row | ✓ unmapped=0 |
| 4 | Buyer | `/meta/ads-combined` | Tab **Zalo** — xác nhận client spend | T-7 | Row hiển thị | ✓ |
| 5 | AM | `/zalo/zalo-ads` | Drill unmapped → link map tab | click yellow row | Deep-link campaigns | ✓ |

#### Nhánh E1 — Campaign mới trên Zalo UI
Buyer tạo campaign trên Zalo Ads UI → quay bước 2 map ID thủ công (v1).

#### Tiêu chí nghiệm thu
- [ ] Unmapped spend = 0 trước báo cáo client
- [ ] Hub CPL khớp spend/leads cùng kỳ

---

## ZALO-UC-003 — Sync insights Zalo

**Mục tiêu khách hàng:** *"Số liệu chi tiêu và lead Zalo cập nhật T-1 trên hub."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/agency/clients/[id]?tab=channels` | **Sync Zalo insights** | — | Toast job enqueued | ✓ cap write |
| 2 | System | worker | Job `zalo_insights_sync` | client_id, T-1 | daily_performance rows | ✓ |
| 3 | System | worker | Enqueue `zalo_alerts_eval` (nếu flag bật) | — | Alert rows | ○ Z3 |
| 4 | Buyer | `/zalo/zalo-ads` | Refresh hub | T-7 | Spend/leads updated | ✓ sync 🟢 |
| 5 | Buyer | `/meta/ads-combined` | So sánh Zalo vs Meta cùng client | T-7 | Combined table | ✓ |

#### Nhánh E1 — Token expired
Bước 2 fail → hub 🔴 → Tracking re-OAuth [ZALO-UC-001](#zalo-uc-001--kết-nối-tài-khoản-zalo-ads--oa) bước 4.

#### Tiêu chí nghiệm thu
- [ ] `daily_performance.channel=zalo` có row T-1
- [ ] Hub badge sync **green** trong 24h

---

## ZALO-UC-004 — Xem hub CPL Zalo (staff)

**Mục tiêu khách hàng:** *"Buyer/AM biết CPL, CPA, Won conversion theo client và campaign."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/zalo/zalo-ads` | Mở hub | — | KPI cards load | ✓ `crm_zalo_ads` |
| 2 | Buyer | Same | Chọn **client** filter | client_id | Table scoped | ✓ |
| 3 | Buyer | Same | Chọn **T-7 / T-30** | date range | CPL recalc | ✓ |
| 4 | Buyer | Same | Xem cột **Won / CPA** | — | Conversion metrics | ✓ Z2-B7 |
| 5 | Buyer | Same | **Export CSV** | — | File download | ✓ export cap |
| 6 | Buyer | Same | **Export PDF** (`?format=pdf`) | period | PDF blob | ✓ Z3-6 |
| 7 | Buyer | Same | Xem **alert banners** (nếu có) | — | cpl_high / zero_leads | ✓ Z3 |
| 8 | AM | Same | Drill campaign unmapped | click row | Link → map tab | ✓ |

#### Tiêu chí nghiệm thu
- [ ] CPL = spend/leads ± rounding
- [ ] Won cập nhật sau CRM status change ([ZALO-UC-015](#zalo-uc-015--đồng-bộ-trạng-thái-crm-ngược-về-zalo-hub))

---

## ZALO-UC-005 — Portal performance Zalo

**Mục tiêu khách hàng:** *"Khách tự xem chi tiêu, lead, CPL Zalo trên portal — không cần AM gửi file."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Client | portal `/login` | Đăng nhập | credentials | JWT scoped | ✓ |
| 2 | Client | `/dashboard` | Widget Zalo (nếu enabled) | T-7 | KPI cards | ✓ |
| 3 | Client | `/zalo` | Xem KPI chi tiết | T-7/T-30 | Spend, Leads, CPL | ✓ read-only |
| 4 | Client | Same | **Export CSV/PDF** | period | File download | ✓ Z3-6 |
| 5 | Client | Nav | Không thấy menu client khác | — | Nav scoped | ✓ tenant |

#### Tiêu chí nghiệm thu
- [ ] JWT `client_id` enforce — không leak client khác
- [ ] KPI portal khớp hub staff ± rounding

**Liên kết PORTAL:** [`06-PORTAL-ACTIONS.md`](06-PORTAL-ACTIONS.md#portal-uc-013--zalo-performance-view--export)

---

## ZALO-UC-006 — Tạo brief chiến dịch Zalo

**Mục tiêu khách hàng:** *"Brief rõ mục tiêu, ngân sách, audience trước khi Buyer lập campaign."*

**Actors:** AM, Client (optional review)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]` | Mở lifecycle stage **Consult/Proposal** | — | Tab load | ✓ |
| 2 | AM | Same tab **Brief** | Nhập mục tiêu chiến dịch | objective, KPI target | Saved | ✓ |
| 3 | AM | Same | Nhập ngân sách + thời gian | budget_vnd, date range | Saved | ✓ |
| 4 | AM | Same | Chọn audience + form lead type | demographics, form_id | Saved | ✓ |
| 5 | AM | Same | Upload tài liệu tham khảo | PDF/images | Attachment | ○ |
| 6 | AM | Same | Ghi chú channel **Zalo** | channel=zalo tag | Visible Buyer | ✓ |
| 7 | Buyer | Same lifecycle | Nhận handoff → chuyển Deliver | — | Stage advance | ✓ |
| 8 | AM | `/crm/marketing-plan/[id]` | Link TMMT nếu có | plan version | Cross-ref | ○ |

#### Nhánh E1 — Brief thiếu ngân sách
AM không advance Deliver cho đến khi budget_vnd có số.

#### Tiêu chí nghiệm thu
- [ ] Brief có objective + budget + form type
- [ ] Buyer xác nhận đã đọc trước [ZALO-UC-007](#zalo-uc-007--tạo-campaign-zalo-draft-nội-bộ)

---

## ZALO-UC-007 — Tạo campaign Zalo (draft nội bộ)

**Mục tiêu khách hàng:** *"Campaign Zalo được lập kế hoạch nội bộ trước go-live — gắn creative và form lead."*

**Actors:** Media Buyer

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/agency/clients/[id]?tab=campaigns` | Chọn client + filter Zalo | client_id | Channel context | ✓ |
| 2 | Buyer | `/crm/creatives` | Gắn creative tag **channel=zalo** | asset ids | Library link | ✓ Z3-1 |
| 3 | Buyer | Lifecycle / notes | Nhập objective, budget, schedule | fields from brief | Draft record | ✓ |
| 4 | Buyer | Same | Chọn form lead (form_id) | form_id list | Validated | ✓ form configured |
| 5 | Buyer | `/crm/creatives` | Submit creative → pending | files, copy | status pending | ✓ |
| 6 | Buyer | `/crm/launch-qa` | Tạo Launch QA run (pre-check) | checklist | draft QA | ○ |
| 7 | Buyer | Notes / CRM | Lưu trạng thái **pending_approval** | — | Audit log | ✓ |

#### Nhánh E1 — v1 manual (API write chưa có)
Buyer bỏ qua bước 3–7 nội bộ → tạo trực tiếp trên Zalo Ads UI → map ID ([ZALO-UC-002](#zalo-uc-002--hub-map-campaign-zalo)).

#### Tiêu chí nghiệm thu
- [ ] Creative `channel=zalo` tồn tại
- [ ] Form ID khớp [ZALO-UC-012](#zalo-uc-012--poll-lead-form-zalo) config

---

## ZALO-UC-008 — Gửi duyệt nội dung chiến dịch

**Mục tiêu khách hàng:** *"Khách duyệt creative Zalo trước khi tiêu ngân sách."*

**Actors:** Creative, Creative Lead, Client Approver, Buyer

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Creative | `/crm/creatives` | Submit creative **channel=zalo** | files, copy | pending | ✓ |
| 2 | Creative Lead | Same | Internal review → approve internal | comment | approved internal | ✓ |
| 3 | Creative | Same | **Submit client approval** | — | pending_client | ✓ |
| 4 | Client | portal `/creatives` | **Approve** hoặc **Reject** | note / comment | approved / rejected | ✓ approver |
| 5 | Manager | `/crm/campaign-writes` | Approve budget nếu > threshold | approve/reject | approved | ✓ nếu vượt ngưỡng |
| 6 | Buyer | `/crm/launch-qa` | Pass **Launch QA** | checklist Zalo auto | status passed | ✓ Z3-2 |
| 7 | Buyer | Zalo Ads UI / future API | Go live + map campaign ID | external id | hub green | ✓ |
| 8 | System | notification_inbox | Milestone notify approve | — | AM + Client inbox | ✓ Z3-8 |

#### Nhánh E1 — Client reject
Bước 4 reject → Creative sửa → resubmit bước 3.

#### Tiêu chí nghiệm thu
- [ ] Launch QA checklist `zalo_oauth_token` + `zalo_form_ids_configured` pass
- [ ] Không go-live khi creative pending_client

**Liên kết SYS:** [SYS-UC-003](00-SYSTEM-ACTIONS.md#sys-uc-003--launch-campaign-đa-kênh-có-governance) nhánh Z1.

---

## ZALO-UC-009 — Triển khai chiến dịch lên Zalo Ads

**Mục tiêu khách hàng:** *"Campaign Zalo live trên nền tảng và được map vào hub tự động."*

**Actors:** Media Buyer, System, GDKD (nếu budget gate)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/crm/launch-qa` | Xác nhận Launch QA **passed** | run id | Gate open | ✓ |
| 2 | Buyer | `/crm/campaign-writes` | Submit campaign write (future) | payload JSON | queued | ⚠ GAP-Z4-01 |
| 3 | System | worker / Temporal | Execute Zalo create API | — | external_campaign_id | ⚠ GAP-Z4-01 |
| 4 | System | — | Auto hub map campaign | campaign id | Row green | ⚠ GAP-Z4-01 |
| 5 | Buyer | `/zalo/zalo-ads` | Verify spend > 0 ngày T+1 | filter | KPI update | ✓ |
| 6 | System | — | Audit log + notify AM | — | notification_inbox | ✓ Z3-8 |

#### Nhánh E1 — v1 manual (hiện tại)
| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| M1 | Buyer | Zalo Ads Manager UI | Tạo campaign thủ công theo brief | ✓ |
| M2 | Buyer | `/agency/clients/[id]?tab=campaigns` | **Map campaign ID** | ✓ [ZALO-UC-002](#zalo-uc-002--hub-map-campaign-zalo) |
| M3 | Buyer | `/zalo/zalo-ads` | Sync insights + verify | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Campaign mapped + spend visible T+1
- [ ] Audit: creative approved + Launch QA passed

---

## ZALO-UC-010 — Tạm dừng / cập nhật / dừng chiến dịch

**Mục tiêu khách hàng:** *"Buyer kiểm soát chi tiêu Zalo — pause/resume/stop có audit."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/zalo/zalo-ads` | Xác định campaign cần action | filter client | Row target | ✓ |
| 2 | Buyer | Zalo Ads UI | **Pause** campaign | — | Status paused | ✓ v1 manual |
| 3 | Buyer | `/crm/campaign-writes` | Submit pause write (future) | campaign id | queued | ⚠ GAP-Z4-01 |
| 4 | Buyer | Zalo Ads UI | **Resume** hoặc **Stop** | — | Status update | ✓ |
| 5 | Buyer | `/zalo/zalo-ads` | Verify spend dừng tăng | T+1 | Spend flat | ✓ |
| 6 | AM | Email/Slack | Thông báo client nếu emergency pause | reason | Comms log | ○ |
| 7 | System | audit | Ghi campaign write / note | actor, action | Timeline | ✓ |

#### Nhánh E1 — Emergency zero leads + high spend
Alert [ZALO-UC-017](#zalo-uc-017--cảnh-báo-chiến-dịch-bất-thường) → Buyer pause trong 30 phút.

#### Tiêu chí nghiệm thu
- [ ] Pause reflected trong insights sync kỳ tiếp theo
- [ ] Audit note có actor + timestamp

---

## ZALO-UC-011 — Webhook lead Zalo → CRM

**Mục tiêu khách hàng:** *"Lead từ Zalo vào CRM trong vài giây — CSKH gọi ngay."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | `POST /webhooks/zalo` | Nhận payload | Zalo JSON + HMAC | 200 OK | ✓ signature |
| 2 | System | — | Parse + normalize phone | phone, form_id | normalized | ✓ |
| 3 | System | — | Dedup fingerprint | phone+client+24h | insert or flag dup | ✓ [UC-013](#zalo-uc-013--chống-trùng-và-chuẩn-hóa-lead) |
| 4 | System | — | Insert `crm_leads` channel=zalo | — | lead id | ✓ |
| 5 | CSKH | `/crm/leads` | Filter **source=zalo** | — | Lead mới | ✓ |
| 6 | CSKH | `/crm/leads/[id]` | Log call, đổi status | note, status | Timeline | ✓ |
| 7 | AM | `/agency/clients/[id]?tab=onboard` | Orchestrator **zalo_first_lead** auto ✓ | — | Step complete | ✓ |

#### Nhánh E1 — Invalid signature
Bước 1 → 401 + alert DevOps; không insert lead.

#### Tiêu chí nghiệm thu
- [ ] Lead visible ≤ 1 phút từ webhook
- [ ] Dedup không tạo row trùng 24h

---

## ZALO-UC-012 — Poll lead form Zalo

**Mục tiêu khách hàng:** *"Lead form Zalo được thu thập ≤15 phút kể cả khi webhook miss."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Tracking | `/zalo/leads` | Tab **Form sync** | — | List forms + cursor | ✓ |
| 2 | Tracking | Same | **+ Thêm form ID** | form_id, oa_id | Row configured | ✓ |
| 3 | System | worker | Cron `zalo_form_lead_poll` | oa_id, form_id | New leads | ✓ ≤15m SLA |
| 4 | Buyer | Same | **Poll now** (manual) | form_id | Job queued | ✓ write |
| 5 | CSKH | `/crm/leads` | Verify lead mới | filter zalo | Row | ✓ |
| 6 | Buyer | `/crm/launch-qa` | Checklist **zalo_form_ids_configured** | — | Auto pass | ✓ Z3-2 |

#### Nhánh E1 — Cursor stuck
Bước 4 manual poll → verify cursor advance → check worker logs.

#### Tiêu chí nghiệm thu
- [ ] Env `PTT_ZALO_FORM_POLL=1`
- [ ] SLA poll ≤ 15 phút (staging gate)

---

## ZALO-UC-013 — Chống trùng và chuẩn hóa lead

**Mục tiêu khách hàng:** *"Không gọi trùng lead — số điện thoại chuẩn hóa đúng."*

**Actors:** System (auto), CSKH (review dup)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | ingest pipeline | Normalize phone E.164 / VN | raw phone | normalized | ✓ |
| 2 | System | — | Normalize email lowercase | email | normalized | ✓ |
| 3 | System | — | Compute fingerprint | phone+client_id | hash | ✓ |
| 4 | System | — | Check duplicate window 24h | fingerprint | is_duplicate flag | ✓ BR-ZALO-02 |
| 5 | System | — | Log `zalo_lead_events` | event type | audit row | ✓ |
| 6 | CSKH | `/crm/leads` | Filter **is_duplicate=true** | — | Dup list | ✓ |
| 7 | CSKH | `/crm/leads/[id]` | Merge hoặc close dup | note | Single active lead | ✓ |
| 8 | QA | `/agency/ingest` | Verify ingest job success | job id | 200 OK | ✓ |

#### Nhánh E1 — Duplicate legitimate re-submit
CSKH bước 7: ghi note "re-inquiry" — giữ lead mới nếu business rule cho phép.

#### Tiêu chí nghiệm thu
- [ ] Cùng phone+client+24h → 1 active lead
- [ ] Event log có dedup decision

---

## ZALO-UC-014 — Đẩy lead sang CRM pipeline

**Mục tiêu khách hàng:** *"Lead Zalo có owner, pipeline stage — CSKH xử lý chuẩn."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | — | Auto-assign owner theo rule | client_id | owner_id set | ✓ |
| 2 | System | — | Set source=zalo, campaign attribution | campaign_id | metadata | ✓ mapped |
| 3 | CSKH | `/crm/leads` | Nhận lead mới (notification/list) | — | Row New | ✓ |
| 4 | CSKH | `/crm/leads/[id]` | **Log call** lần 1 | note, duration | Timeline | ✓ SLA |
| 5 | CSKH | Same | Đổi status → **Qualified** | status | Pipeline advance | ✓ |
| 6 | Sales | `/crm/pipeline` hoặc lead detail | Kéo → **Won** + deal_value_vnd | revenue | Won record | ✓ |
| 7 | Buyer | `/zalo/zalo-ads` | Verify CPA/Won cột refresh | T+0 | Hub update | ✓ [UC-015](#zalo-uc-015--đồng-bộ-trạng-thái-crm-ngược-về-zalo-hub) |
| 8 | CSKH | Same lead | Hoặc **Lost** + lý do | lost_reason | No Won count | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Lead có owner trong 5 phút
- [ ] Won trigger hub CPA refresh

---

## ZALO-UC-015 — Đồng bộ trạng thái CRM ngược về Zalo hub

**Mục tiêu khách hàng:** *"Hub Zalo phản ánh đúng conversion Won/Lost từ CRM."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | CSKH | `/crm/leads/[id]` | Đổi status → **Won** | deal_value_vnd | CRM saved | ✓ |
| 2 | System | — | Refresh `daily_performance.conversions` | lead channel=zalo | metrics update | ✓ Z2-B7 |
| 3 | System | — | Update `conversion_value` aggregate | deal_value_vnd | CPA recalc | ✓ |
| 4 | Buyer | `/zalo/zalo-ads` | Refresh hub — verify Won column | T-7 | Numbers match | ✓ |
| 5 | Buyer | `/meta/ads-combined` | Tab Zalo — verify CPA | same period | Combined OK | ✓ |
| 6 | CSKH | `/crm/leads/[id]` | **Lost** — verify Won không tính | lost_reason | conversion revert | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Won → hub CPA cập nhật trong cùng request cycle
- [ ] Lost không inflate conversion count

---

## ZALO-UC-016 — Xuất báo cáo khách hàng

**Mục tiêu khách hàng:** *"Khách nhận báo cáo Zalo định kỳ — CSV/PDF đẹp, số liệu T-1."*

**Actors:** AM, Analyst, Client

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/zalo/zalo-ads` | Verify sync green + unmapped=0 | T-7 | Hub sane | ✓ |
| 2 | AM | Same | **Export CSV** | period | File download | ✓ |
| 3 | AM | Same | **Export PDF** | `?format=pdf` | PDF blob | ✓ Z3-6 |
| 4 | AM | Email / handover | Gửi file cho client (nếu không portal) | attachment | Delivery log | ○ |
| 5 | Client | portal `/zalo` | Self-serve **Export CSV/PDF** | period | File download | ✓ |
| 6 | System | Scheduler (future) | Weekly job per [SYS-UC-005](00-SYSTEM-ACTIONS.md#sys-uc-005--báo-cáo-định-kỳ-cho-khách-hàng) | client list | Email link | ○ |

#### Tiêu chí nghiệm thu
- [ ] PDF có logo client + period + CPL
- [ ] Portal export khớp staff export

---

## ZALO-UC-017 — Cảnh báo chiến dịch bất thường

**Mục tiêu khách hàng:** *"Buyer biết ngay khi CPL cao, CTR tụt, hoặc zero lead — xử lý trước khi lãng phí budget."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | worker `zalo_alerts_eval` | Eval rules post sync | daily_performance | alert rows | ✓ Z3 |
| 2 | System | — | Rule **cpl_high** | CPL > target+buffer | meta_alerts | ✓ |
| 3 | System | — | Rule **zero_leads_24h** | spend>0, leads=0 | meta_alerts | ✓ |
| 4 | System | — | Rule **ctr_drop** | vs T-1 -30% | meta_alerts | ✓ |
| 5 | System | Slack | Post `PTT_ZALO_SLACK_WEBHOOK` | alert payload | Message sent | ○ |
| 6 | Buyer | `/zalo/zalo-ads` | Xem **alert banner** | — | Link client row | ✓ |
| 7 | Buyer | Same | Drill client → diagnose | campaign | Action plan | ✓ |
| 8 | Buyer | Zalo UI / [UC-010](#zalo-uc-010--tạm-dừng--cập-nhật--dừng-chiến-dịch) | Pause nếu emergency | — | Spend stop | ○ |

#### Nhánh E1 — Alerts disabled
Env `PTT_ZALO_ALERTS_ENABLED=0` → bước 1–5 skip; Buyer manual review hub daily.

#### Tiêu chí nghiệm thu
- [ ] Env `PTT_ZALO_ALERTS_ENABLED=1`
- [ ] Alert visible on hub within 1 sync cycle

---

## ZALO-UC-018 — Phân tích đa chiều (client/creative)

**Mục tiêu khách hàng:** *"Analyst so sánh performance Zalo theo client/campaign — và cross-channel."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Analyst | `/meta/ads-combined` | Tab **Zalo** hoặc **All** | T-30 | Combined table | ✓ Z3-7 |
| 2 | Analyst | Same | Filter by client | client_id | Scoped rows | ✓ |
| 3 | Analyst | `/zalo/zalo-ads` | Drill client KPI | T-30 | Campaign breakdown | ✓ |
| 4 | Analyst | `/crm/creatives` | Filter channel=zalo | — | Creative list | ✓ Z3-1 |
| 5 | Analyst | Same | Cross-ref creative ↔ campaign | map id | Attribution | ○ manual |
| 6 | Analyst | `/zalo/zalo-ads` | **Export CSV/PDF** | period | File | ✓ |
| 7 | Analyst | Future DWH/Grafana | Deep BI export | — | — | ⚠ GAP-P2-01 |

#### Tiêu chí nghiệm thu
- [ ] Combined view có Zalo spend + CPL
- [ ] Export reproducible cùng số hub

---

## ZALO-UC-019 — Client duyệt ngân sách & nội dung

**Mục tiêu khách hàng:** *"Khách kiểm soát creative và ngân sách Zalo trước go-live."*

**Actors:** Client Approver, AM, GDKD

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]` | Submit budget brief lifecycle | budget_vnd | pending approval | ✓ |
| 2 | GDKD | `/crm/campaign-writes` | Approve budget nếu > threshold | approve/reject | approved | ✓ |
| 3 | Creative | `/crm/creatives` | Submit creative channel=zalo | assets | pending_client | ✓ |
| 4 | Client | portal `/creatives` | Preview creative Zalo | — | Full preview | ✓ |
| 5 | Client | Same | **Approve** creative | optional note | approved | ✓ |
| 6 | Client | Same | Hoặc **Reject** + comment | comment ≥ min | rejected | ✓ [PORTAL-UC-009](06-PORTAL-ACTIONS.md#portal-uc-009--reject-with-comment) |
| 7 | Buyer | `/crm/launch-qa` | Launch QA pass sau approve | checklist | passed | ✓ |
| 8 | System | notification_inbox | Notify milestone budget approved | — | Client + AM | ✓ Z3-8 |

#### Nhánh E1 — Chỉ duyệt creative, budget đã OK trong HĐ
Bỏ qua bước 1–2; Client duyệt creative bước 4–6.

#### Tiêu chí nghiệm thu
- [ ] Không Launch QA pass khi creative pending_client
- [ ] Reject có comment bắt buộc

**Liên kết PORTAL:** [`06-PORTAL-ACTIONS.md`](06-PORTAL-ACTIONS.md#portal-uc-014--zalo-creative--budget-approval)

---

## ZALO-UC-020 — Thông báo tiến độ chiến dịch

**Mục tiêu khách hàng:** *"AM và khách được thông báo khi duyệt creative, launch, alert, milestone KPI."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | — | Trigger on creative **approved** | creative id | notification_inbox | ✓ Z3-8 |
| 2 | System | — | Trigger on Launch QA **passed** | run id | notification | ✓ |
| 3 | System | — | Trigger on campaign **go-live** (manual note) | campaign id | milestone | ○ |
| 4 | System | — | Trigger on alert fired | alert_type | Slack + inbox | ✓ Z3 |
| 5 | AM | ops notification inbox | Đọc + acknowledge | — | Read status | ✓ |
| 6 | Client | portal `/dashboard` | Widget pending + milestones | — | Visible | ⚠ GAP-P1-02 |
| 7 | AM | Email manual | Fallback notify client | — | Comms log | ○ nếu GAP-P1-02 |

#### Nhánh E1 — Client không dùng portal
AM bước 7 email manual thay bước 6.

#### Tiêu chí nghiệm thu
- [ ] Staff inbox có event creative approve Zalo
- [ ] Alert → Slack within 5 min (nếu webhook configured)

---

## ZALO-UC-021 — Onboard Zalo (orchestrator)

**Mục tiêu khách hàng:** *"AM thấy một checklist Zalo thống nhất — không nhớ 6 URL riêng lẻ."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]?tab=onboard` | Xem orchestrator compact | — | Zalo steps list | ✓ |
| 2 | AM | Link **Mở →** từng step | Deep-link channels/hub/zalo | — | Đúng màn hình | ✓ |
| 3 | AM | `/agency/clients/[id]?tab=onboard` | **Auto-sync checklist** | — | Items ticked | ✓ |
| 4 | AM | Same | **Activate client** khi đủ | confirm | status active | ✓ |
| 5 | AM | Orchestrator | Verify 5 steps Zalo ✓ | — | 100% required | ✓ |
| 6 | AM | [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md#sys-uc-001--onboard-client-mới-end-to-end) | Cross-check SYS-001 nhánh Z1 | — | Full onboard | ✓ |

**Steps orchestrator (Z2 shipped):**

| Step key | Label | Deep-link |
|----------|-------|-----------|
| `zalo_account` | Zalo ad account / OA | `?tab=channels` |
| `zalo_token` | Zalo OAuth token | `?tab=channels` |
| `zalo_form` | Lead form configured | `/zalo/leads` |
| `zalo_sync` | Insights sync green | `/zalo/zalo-ads` |
| `zalo_first_lead` | First lead in CRM | `?tab=leads` |

#### Tiêu chí nghiệm thu
- [ ] 5/5 steps auto-detect green
- [ ] Deep-link mở đúng tab không 404

---

## Luồng end-to-end (tóm tắt 15 bước AM)

| # | Actor | Màn hình | Mục tiêu | UC |
|---|-------|----------|---------|-----|
| 1 | AM | `/agency/clients/new` | Tạo client | SYS-001 |
| 2 | AM | `/crm/service-delivery` | Lifecycle Onboard | SVC-001 |
| 3 | Tracking | `?tab=channels` | Zalo account + OAuth | ZALO-001 |
| 4 | Tracking | Zalo Developer | Webhook URL | ZALO-001 |
| 5 | Buyer | `?tab=campaigns` | Hub map | ZALO-002 |
| 6 | Buyer | `/zalo/zalo-ads` | Sync + verify CPL | ZALO-003/004 |
| 7 | Creative | `/crm/creatives` | Submit creative zalo | ZALO-007/008 |
| 8 | Client | portal `/creatives` | Approve | ZALO-019 |
| 9 | Buyer | Launch QA + Zalo UI | Go live | ZALO-008/009 |
| 10 | System | webhook/poll | Leads → CRM | ZALO-011/012/013 |
| 11 | CSKH | `/crm/leads` | Qualify → Won | ZALO-014/015 |
| 12 | AM | `/zalo/zalo-ads` | Báo cáo client | ZALO-016 |
| 13 | Client | portal `/zalo` | Xem KPI | ZALO-005 |
| 14 | AM | `?tab=onboard` | Activate client | ZALO-021 |
| 15 | AM | Handover A4 | Credential portal | SYS-001 |

**Liên kết SYS:** [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md) — nhánh Z1 song song Meta.

---

## Gap vs PTTADS hiện tại (cập nhật post Z3)

| Step | Trạng thái | Wave | GAP ID |
|------|------------|------|--------|
| Channel zalo CRUD | ✅ Shipped | Z0 | — |
| Hub map zalo | ✅ Shipped | Z0 | — |
| Webhook lead | ✅ Shipped | Z0 | — |
| Hub `/zalo/zalo-ads` | ✅ Shipped | Z1 | — |
| Sync job | ✅ Shipped | Z1 | — |
| Portal `/zalo` | ✅ Shipped | Z1 | — |
| Form poll | ✅ Shipped | Z2 | — |
| Orchestrator zalo steps | ✅ Shipped | Z2 | — |
| CRM Won → hub CPA | ✅ Shipped | Z2 | — |
| Combined ads `/meta/ads-combined` | ✅ Shipped | Z3 | — |
| Creative tag `channel=zalo` | ✅ Shipped | Z3 | — |
| Launch QA Zalo checklist | ✅ Shipped | Z3 | — |
| Alerts CPL/zero leads/CTR | ✅ Shipped | Z3 | — |
| Export PDF báo cáo | ✅ Shipped | Z3 | — |
| Milestone notify staff | ✅ Shipped | Z3 | — |
| Portal in-app notify client | ⚠ Partial | — | GAP-P1-02 |
| Campaign write API Zalo | ❌ | Z4 | GAP-Z4-01 |
| DWH/Grafana Zalo drill | ❌ | Z4 | GAP-P2-01 |

Cập nhật gap tổng: [`ACTION-GAP-ANALYSIS.md`](../ACTION-GAP-ANALYSIS.md).
