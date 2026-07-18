# Design: Giai đoạn Tư vấn (Consult) — Service Lifecycle CRM

**Ngày:** 2026-06-30  
**Phiên bản:** 1.0  
**Stack:** Flask 3 + SQLite, Anthropic Haiku, Jinja2 + Vanilla JS  
**Nguyên tắc:** Simplicity First · Surgical Changes · AI-first · Single source of truth  
**Phụ thuộc:** [Lead Intake System](./2026-06-30-lead-intake-system-design.md) · [Service Workflow Engine](./2026-06-22-service-workflow-engine-design.md)

---

## 1. Vấn đề cần giải quyết

### 1.1 Hiện trạng ( khảo sát codebase 2026-06-30 )

| Thành phần | Trạng thái | Hạn chế vận hành Consult |
|------------|------------|---------------------------|
| `crm_svc_workflow_steps.py` — stage `consult` | ✅ 12 dịch vụ, 1 task/DV | Chỉ template; AM phải tự hiểu nghiệp vụ |
| `crm_service_workflow.html` | ✅ Task card + AI button | Không panel brief Lead; form Consult trống |
| `crm_lead_intake.py` | ✅ Phone/in_person → merge **task Lead** | Không prefill Consult; không auto ✓ Lead |
| `crm_svc_lead_sync.py` | ✅ Consult ↔ care `qualify` | Chỉ sync status, không artifact Consult |
| `run_ai_assist` (`consult_analysis`) | ⚠️ Partial | Context = field Consult card + tên KH; **bỏ qua** Intake/BANT |
| `crm_proposal.py` | ⚠️ Partial | Proposal AI không đọc task Consult |
| KPI kanban | ✅ Intake coverage | Không đo Go→Consult, Consult→Proposal |
| Module `crm_consult_*` | ❌ Không tồn tại | Consult = stage generic, không có bridge layer |

### 1.2 Hậu quả nghiệp vụ

1. AM hoàn thành Lead Intake nhưng **nhập lại** niche/budget/pain ở Consult.
2. Lead `no_go` vẫn chuyển Consult nếu tick xong task Lead.
3. AI phân tích Consult **generic**, không dùng BANT/decision/answers Intake.
4. Proposal tách rời audit Consult — báo giá thiếu scope/KPI đã thống nhất.
5. Không đo funnel **Go → Consult → Proposal** — khó quản lý AM.

### 1.3 Mục tiêu

1. **Consult Brief Panel** — một màn hình tổng hợp output Lead trước khi làm audit.
2. **Prefill task Consult** từ Lead task + Intake session (chỉ field trống).
3. **Gate funnel** theo `decision` (go / nurture / no_go) khi chuyển Lead → Consult.
4. **AI context đầy đủ** cho `consult_analysis`.
5. **Bridge Consult → Proposal** — proposal AI đọc `form_data` + `ai_output` Consult.
6. **KPI funnel** trên Service Delivery dashboard.

---

## 2. Phạm vi

### In scope (v1)

| # | Hạng mục |
|---|----------|
| 1 | Module `crm_svc_consult_bridge.py` (read-only aggregate + prefill + validate) |
| 2 | Consult Brief panel trên `crm_service_workflow.html` khi `lifecycle.stage == 'consult'` |
| 3 | Hook `advance_stage(..., 'consult')` + lazy prefill khi mở tab Consult |
| 4 | Gate cảnh báo / soft-block `no_go` khi advance Lead→Consult |
| 5 | Auto ✓ task Lead khi Intake `in_person` + `decision=go` + `bant_total≥24` |
| 6 | Enrich `api_svc_task_ai_assist` với brief context |
| 7 | Mở rộng `crm_proposal.get_customer_context` — đọc task Consult |
| 8 | API `GET /api/crm/service-lifecycle/<id>/consult-brief` |
| 9 | KPI `get_funnel_stats()` trên kanban |
| 10 | Tests + PPT đào tạo AM |

### Out of scope (v1)

- Consult Intake session riêng (form phone/in_person thứ 3) — dùng Lead Intake PHẦN B + task Consult
- **Phí tư vấn/audit riêng** — PTT không thu phí Consult; không model payment ở stage `consult`
- Mobile app, ghi âm, e-signature
- Form công khai `/api/consultations` (landing) — không liên quan lifecycle nội bộ
- Multi-task Consult per service (giữ 1 task/DV như hiện tại)

---

## 3. Kiến trúc

```
┌─────────────────────┐     ┌──────────────────────────┐
│ crm_lead_intake_    │     │ crm_svc_tasks            │
│ sessions (completed)│────▶│ stage=lead  form_data    │
└─────────────────────┘     └────────────┬─────────────┘
                                         │
┌─────────────────────┐                  ▼
│ crm_leads           │     ┌──────────────────────────┐
│ care: qualify       │◀────│ crm_svc_consult_bridge   │
└─────────────────────┘     │ get_consult_brief()      │
         ▲                  │ prefill_consult_task()   │
         │                  │ validate_consult_advance │
         │                  └────────────┬─────────────┘
         │                               │
         │                  ┌────────────▼─────────────┐
         │                  │ crm_svc_tasks              │
         └──────────────────│ stage=consult form_data  │
                            │ ai_output (consult_analysis)│
                            └────────────┬─────────────┘
                                         │
                            ┌────────────▼─────────────┐
                            │ crm_proposal (AI báo giá) │
                            └──────────────────────────┘
```

**Luồng mục tiêu:**

1. Lead task ✓ + Intake complete (decision set).
2. (Optional auto) Intake in_person + go + BANT≥24 → tick Lead task.
3. AM bấm **Chuyển → Tư vấn** — `validate_consult_advance` + `prefill_consult_task`.
4. UI hiện **Consult Brief** + task Consult đã prefill.
5. AM audit → AI assist → tick Consult ✓ → **Chuyển → Báo giá**.
6. Proposal prefill từ Consult output.

---

## 4. Module `crm_svc_consult_bridge.py`

### 4.1 Public API

```python
def get_consult_brief(conn: sqlite3.Connection, lifecycle_id: int) -> dict[str, Any]:
    """Aggregate Lead task, intake sessions, lead row, readiness flags."""

def prefill_consult_task(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fill empty consult form_data from lead + intake. Returns {filled: N, task_id}."""

def validate_consult_advance(
    conn: sqlite3.Connection,
    lifecycle_id: int,
) -> dict[str, Any]:
    """{ok, level: ok|warn|block, messages[], decision, bant_total, ...}"""

def on_intake_completed(
    conn: sqlite3.Connection,
    session_id: int,
    *,
    actor_id: int | None = None,
) -> dict[str, Any]:
    """Side effects: auto-done lead task, activity reminder. Called from complete_session."""

def build_ai_context_for_consult(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    task_id: int,
    form_context: dict,
) -> dict[str, Any]:
    """Merge brief + form_context for run_ai_assist."""

def get_lead_to_consult_field_map(service_slug: str) -> dict[str, str]:
    """Static + crm_field_map extension per slug."""
```

### 4.2 Cấu trúc `get_consult_brief()` response

```json
{
  "lifecycle_id": 42,
  "service_slug": "dich-vu-seo-tong-the",
  "service_label": "SEO Tổng thể",
  "lead_id": 10,
  "readiness": {
    "lead_task_done": true,
    "has_intake_phone": true,
    "has_intake_in_person": false,
    "decision": "go",
    "bant_total": 26,
    "lead_temperature": "hot",
    "can_advance_from_lead": true,
    "consult_gate_level": "ok"
  },
  "lead_task": {
    "task_id": 101,
    "form_data": {"niche": "...", "budget": 15000000, "domain": "...", "need": "..."},
    "notes": "...",
    "is_done": true
  },
  "intake_sessions": [
    {
      "id": 5,
      "mode": "phone",
      "status": "completed",
      "bant_total": 26,
      "decision": "go",
      "decision_reason": "",
      "ai_summary": "...",
      "next_meeting_at": "2026-07-05",
      "proposal_date": "2026-07-10"
    }
  ],
  "stakeholders": [],
  "commitments": [],
  "red_flags": [],
  "recommended_actions": [
    "Hẹn gặp PHẦN B (in_person) trước audit sâu",
    "Thu GSC/GA4 read access trước buổi Consult"
  ],
  "latest_intake_summary": "..."
}
```

### 4.3 Field mapping Lead → Consult (mặc định + theo slug)

**Mapping chung (mọi slug):**

| Nguồn | Target Consult field | Quy tắc |
|-------|---------------------|---------|
| Lead `need` | `current_status` | Prefix `"Pain: {need}"` nếu trống |
| Lead `niche` | notes append | `"Ngành: {niche}"` |
| Lead `budget` | notes append | `"NS: {budget} VND"` |
| Intake `answers.meta.pain_summary` | `current_status` | Fallback nếu Lead need trống |
| Intake `crm_fields.*` | theo `get_crm_field_map(slug)` | Best effort |

**Ví dụ theo slug (`crm_svc_workflow_steps` keys):**

| Slug | Lead keys | Consult keys |
|------|-----------|--------------|
| `dich-vu-seo-tong-the` | domain, need | current_status, target_keywords (từ intake p*) |
| `quang-cao-facebook` | niche, campaign_goal | target_audience, product_usp |
| `quang-cao-google` | niche | target_keywords, current_status |
| `thiet-ke-landing-page` | lp_purpose | usp, cta, target_audience |
| `thue-tai-khoan-quang-cao` | platform, urgency | current_status, risk_assessment |

Implement `get_crm_field_map(slug)` trong `crm_lead_intake_definitions.py` (spec Lead Intake Phase 1 — bổ sung).

### 4.4 Gate `validate_consult_advance`

| Level | Điều kiện | UI |
|-------|-----------|-----|
| `ok` | Lead tasks done + decision=`go` + BANT≥18 | Cho phép advance |
| `warn` | decision=`nurture` HOẶC BANT 18–23 | Confirm dialog + ghi lý do |
| `block` | decision=`no_go` | Block trừ `override_reason` + role Director |

**Lead task done** vẫn là hard requirement (`validate_stage_advance` hiện có).

### 4.5 `on_intake_completed` side effects

Gọi từ `crm_lead_intake.complete_session` sau merge:

```python
if session["decision"] == "go" and session["mode"] == "in_person" and session["bant_total"] >= 24:
    mark_lead_task_done(conn, lifecycle_id)
if session["decision"] == "go" and session["mode"] == "phone":
    log_reminder(conn, lead_id, "Hẹn gặp PHẦN B", session.get("next_meeting_at"))
if session["decision"] == "no_go":
    append_lifecycle_note(conn, lifecycle_id, "Intake No-Go — cân nhắc lifecycle lost")
```

Không auto `advance_stage` → Consult (giữ sequential manual trừ flag config sau này).

---

## 5. API

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/api/crm/service-lifecycle/<id>/consult-brief` | JSON brief panel |
| POST | `/api/crm/service-lifecycle/<id>/consult-prefill` | Chạy prefill Consult task |
| GET | `/api/crm/service-lifecycle/funnel-stats` | KPI Go→Consult→Proposal |
| PATCH | `/api/crm/service-lifecycle/<id>` | *(existing)* — trước advance gọi validate, trả 400 nếu block |

**Auth:** `_ensure_admin_session_api()` + `_cms_can("service_delivery", ...)`.

---

## 6. UI — Consult Brief Panel

**Vị trí:** `crm_service_workflow.html`, ngay dưới progress bar, **chỉ khi** `lifecycle.stage == 'consult'`.

**Layout:**

```
┌─ Consult Brief ─────────────────────────────────────────────┐
│ Decision: GO · BANT 26/30 · Hot · Intake #5 (gọi) ✓       │
│ Pain: ... | Budget: 15M | Domain: example.com              │
│ ⚠ Chưa có buổi gặp PHẦN B → [Mở Intake gặp]               │
│ Stakeholders: DM: Nguyễn A · Influencer: ...               │
│ Cam kết KH: ... | Proposal date: 2026-07-10               │
│ AI summary: [2 câu tóm tắt]                                │
│ [Prefill lại form Consult]  [Mở Intake]  [Xem task Lead]   │
└────────────────────────────────────────────────────────────┘
```

**Lead Intake banner:** Ẩn khi `stage != 'lead'`; thay bằng link nhỏ “Xem phiên Intake” trong Brief.

**Advance banner (stage=lead):** Hiện gợi ý sau Intake complete:

- `"Sẵn sàng chuyển Tư vấn"` (go + lead done)
- `"Nurture — cân nhắc trước khi Consult sâu"`
- `"No-Go — không nên chuyển Consult"`

---

## 7. AI — `consult_analysis`

### 7.1 Context bổ sung vào prompt

```python
extra = {
    "intake_summary": brief["latest_intake_summary"],
    "bant_total": brief["readiness"]["bant_total"],
    "decision": brief["readiness"]["decision"],
    "lead_form_json": json.dumps(lead_task["form_data"], ensure_ascii=False),
}
```

### 7.2 Template mở rộng (optional v1.1)

Thêm placeholder vào `AI_PROMPT_TEMPLATES["consult_analysis"]`:

```
BANT: {bant_total}/30 · Quyết định: {decision}
Lead qualify: {lead_form_json}
Intake: {intake_summary}
```

---

## 8. Bridge Consult → Proposal

**Modify `crm_proposal.get_customer_context`:**

```python
consult_task = get_stage_task(conn, lifecycle_id, "consult")
return {
    ...
    "consult": {
        "form_data": consult_task.get("form_data") or {},
        "ai_output": consult_task.get("ai_output") or "",
        "notes": consult_task.get("notes") or "",
    },
}
```

**Workflow UI (stage consult/proposal):** Nút **「Tạo Proposal từ Consult」** → mở proposal form prefill.

---

## 9. KPI

| KPI | Công thức | Ngưỡng |
|-----|-----------|--------|
| Go → Consult | lifecycle stage≥consult AND latest intake decision=go / lifecycles có intake go | ≥35% |
| Consult → Proposal ≤7 ngày | stage proposal within 7d of consult entered | ≥60% |
| Consult task completion | consult tasks done / entered consult | ≥80% |
| BANT avg won | avg bant lifecycle status=closed won | ≥22 |
| Intake in_person trước Consult | in_person completed before consult advance / go leads | ≥80% |

**Nguồn:** `crm_service_lifecycle`, `crm_lead_intake_sessions`, `crm_svc_tasks`.

---

## 10. RACI & SLA

| Hoạt động | AM | SP | AI | Director | SLA |
|-----------|----|----|-----|----------|-----|
| Đọc Consult Brief | R | I | C | I | Ngay khi vào Consult |
| Audit/discovery | R | R | C | — | 3–7 ngày |
| Prefill + form Consult | R | C | — | — | Trong buổi tư vấn |
| AI consult_analysis | R | I | C | — | Cùng buổi |
| Chuyển Proposal | R | I | — | — | ≤48h sau meeting |
| Override No-Go→Consult | R | — | — | A | Có `decision_reason` |

---

## 11. Nghiệp vụ Consult theo 12 dịch vụ

Task title + form fields lấy từ `SERVICE_WORKFLOW_STEPS[slug]["consult"][0]` (đã seed DB).

| # | Dịch vụ | Task Consult | Form fields |
|---|---------|--------------|-------------|
| 1 | SEO Tổng thể | Audit website & từ khóa | current_status, top_competitors, target_keywords |
| 2 | AEO | Audit AI search presence | current_status, content_gaps |
| 3 | SEO Local | GBP audit & local KW | current_status, local_keywords |
| 4 | SEO Audit | Scoping & phân tích sơ bộ | audit_scope, current_status |
| 5 | Quản trị website | Đánh giá website & scope | current_status, pain_points |
| 6 | Thiết kế website | Thu thập yêu cầu | current_status, design_refs, pages_count |
| 7 | Website trọn gói | Tư vấn kỹ thuật | current_status, integrations |
| 8 | Landing page | Brief LP | target_audience, usp, cta |
| 9 | Facebook Ads | Strategy | target_audience, current_status, product_usp |
| 10 | Google Ads | Keyword research | target_keywords, current_status |
| 11 | Thuê TK Ads | Đánh giá rủi ro | current_status, risk_assessment |
| 12 | Content marketing | Content strategy | current_status, top_competitors, target_audience |

**Output bắt buộc trước khi rời Consult:** tất cả `form_fields` điền + AI output reviewed + task ✓.

---

## 12. Tests

| File | Case |
|------|------|
| `tests/test_crm_svc_consult_bridge.py` | brief aggregate; prefill không ghi đè; gate no_go block |
| `tests/test_crm_lead_intake.py` | extend: in_person go → lead task auto done |
| `tests/test_crm_service_lifecycle.py` | advance consult with gate warn |
| `tests/test_crm_proposal.py` | context includes consult form_data |

---

## 13. Kế hoạch triển khai

Chi tiết task breakdown: [../superpowers/plans/2026-06-30-consult-stage-system.md](../superpowers/plans/2026-06-30-consult-stage-system.md)

| Phase | Thời gian | Deliverable |
|-------|-----------|-------------|
| C0 | 2 ngày | SOP + PPT đào tạo |
| C1 | 4 ngày | `get_consult_brief` + UI panel |
| C2 | 3 ngày | Prefill + field map |
| C3 | 4 ngày | Gates + auto ✓ Lead |
| C4 | 3 ngày | AI context enrich |
| C5 | 4 ngày | Proposal bridge |
| C6 | 2 ngày | KPI funnel dashboard → **gộp [Lead KPI L3](../superpowers/plans/2026-06-30-lead-kpi-precontract-cost.md)** |

---

## 14. Tiêu chí nghiệm thu v1

- [ ] Lifecycle stage Consult hiển thị Brief với BANT/decision/intake summary
- [ ] Chuyển Lead→Consult prefill ≥1 field Consult (slug SEO smoke test)
- [ ] `no_go` hiển thị block/warn; Director override ghi log
- [ ] Intake in_person + go + BANT≥24 auto ✓ task Lead
- [ ] AI Consult output phản ánh pain từ Intake (test snapshot)
- [ ] Proposal AI nhận `current_status` từ Consult task
- [ ] KPI funnel hiển thị trên Service Delivery
- [ ] PPT đào tạo AM phát hành trong `docs/`

---

## 15. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|--------|------------|
| AM bỏ qua Brief | KPI consult completion; mandatory fields trước tick ✓ |
| Prefill sai mapping | `get_crm_field_map` per slug + test snapshot |
| Gate quá cứng | warn vs block; Director override |
| Trùng Lead Intake PHẦN B vs Consult | SOP: PHẦN B = qualify; Consult = audit chuyên môn |

---

**Tài liệu liên quan:**

- [Lead Intake Design](./2026-06-30-lead-intake-system-design.md)
- [Service Workflow Engine](./2026-06-22-service-workflow-engine-design.md)
- [CRM docs hub](../crm/README.md) — PPT, SOP, training C0
- [Checklist Lead PPT](../Checklist_Tiep_Nhan_Lead_12_Dich_Vu.pptx)
- [Consult Stage PPT](../Consult_Stage_Service_Delivery.pptx)
