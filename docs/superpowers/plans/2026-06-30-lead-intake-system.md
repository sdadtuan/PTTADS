# Lead Intake System — Kế hoạch triển khai

> **Mục tiêu:** Đưa form gọi lead & gặp trực tiếp vào CRM PTT — lưu DB, đồng bộ workflow, hỗ trợ chốt khách.

**Design spec:** [2026-06-30-lead-intake-system-design.md](../specs/2026-06-30-lead-intake-system-design.md)

**Tech stack:** Flask 3, SQLite, Jinja2, Vanilla JS, Anthropic Haiku (AI summary)

---

## Global constraints

- Auth: `_ensure_admin_session_html()` / `_ensure_admin_session_api()` như các route CRM hiện có
- DB: `with get_connection() as conn:` — pattern `ensure_schema` trong module riêng
- Timestamps: UTC `strftime("%Y-%m-%d %H:%M:%S")`
- Tests: `unittest` + in-memory SQLite + `Row` factory
- Không phá workflow sequential stage advance đã có
- YAGNI: không build form builder generic v1

---

## Phase 1 — Data layer & static forms (1–2 ngày)

**Goal:** Single source of truth; HTML/PPT sync từ code.

### Task 1.1: Tách definitions

**Files:**
- Create: `crm_lead_intake_definitions.py`
- Modify: `scripts/generate_lead_intake_forms.py` — import từ module mới
- Modify: `scripts/generate_lead_intake_pptx.py` — import nếu cần

**Nội dung module:**
- `INTAKE_COMMON` (scripts, bant, objections, discovery common, checklists)
- `INTAKE_BY_SLUG` (12 dịch vụ — copy từ `SERVICE_FORMS`)
- `INTAKE_SLUGS: tuple[str, ...]`
- `get_intake_definition(slug: str) -> dict`
- `get_crm_field_map(slug: str) -> dict[str, str]`

- [ ] Extract data, chạy lại generator → 13 HTML không đổi nội dung
- [ ] Test: `tests/test_crm_lead_intake_definitions.py` — 12 slug có `phone_questions`; common có 6 bant

### Task 1.2: Serve static forms từ Flask

**Files:**
- Modify: `app.py` — route GET `/crm/forms/lead-intake/<path:filename>`

```python
@app.get("/crm/forms/lead-intake/<path:filename>")
def crm_lead_intake_form_static(filename: str):
    redir = _ensure_admin_session_html()
    if redir: return redir
    # send_from_directory docs/forms/lead-intake, filename whitelist .html
```

- [ ] Whitelist 13 filenames — không path traversal
- [ ] Link từ README nội bộ

### Task 1.3: Nút trên Service Workflow

**Files:**
- Modify: `templates/crm_service_workflow.html` — thêm link cạnh stage Lead:

```html
<a href="{{ url_for('crm_lead_intake_form_static', filename=lifecycle.service_slug + '.html') }}"
   target="_blank" class="...">📋 Form gọi/gặp (in)</a>
```

Fallback slug `00-form-chung.html` nếu slug lạ.

- [ ] AM click mở form in được khi chưa có Phase 2

---

## Phase 2 — Intake sessions DB + API (2–3 ngày)

**Goal:** Lưu kết quả buổi gọi/gặp trong CRM.

### Task 2.1: Schema module

**Files:**
- Create: `crm_lead_intake.py`

**Functions:**
```python
def ensure_schema(conn) -> None
def create_session(conn, *, lifecycle_id, lead_id, service_slug, mode, am_id, ...) -> int
def get_session(conn, session_id) -> dict | None
def update_session(conn, session_id, **fields) -> bool
def list_sessions(conn, *, lifecycle_id=None, lead_id=None) -> list[dict]
def compute_bant_total(bant_json: dict) -> int
def suggest_decision(bant_total: int, red_flags: list[str]) -> str
def complete_session(conn, session_id, actor_id) -> dict  # side effects
def merge_to_lead_task(conn, session_id) -> None
```

- [ ] Migration idempotent
- [ ] Tests CRUD + bant scoring + complete merge

### Task 2.2: API routes

**Files:**
- Modify: `app.py`

| Route | Handler |
|-------|---------|
| GET `/api/crm/intake/definitions` | Trả `INTAKE_COMMON` + slug list |
| GET `/api/crm/intake/definitions/<slug>` | Trả full definition |
| POST `/api/crm/intake/sessions` | Tạo session |
| GET/PATCH `/api/crm/intake/sessions/<id>` | Read/update |
| POST `/api/crm/intake/sessions/<id>/complete` | Complete + side effects |
| GET `/api/crm/intake/sessions?lifecycle_id=` | List |

- [ ] JSON schema validate mode, decision enum
- [ ] Tests API với Flask test client

### Task 2.3: Side effects on complete

Trong `complete_session`:

1. `merge_to_lead_task` — map answers → `crm_svc_tasks.form_data` (lead stage, index 0)
2. `crm_leads` activity log qua existing activity API pattern
3. Gọi `sync_lead_from_lifecycle_stage(conn, lifecycle_id, "lead")` nếu chưa sync
4. Set `status=completed`, `completed_at`

- [ ] Test: complete phone go → form_data có domain/budget
- [ ] Test: không complete nếu thiếu decision

---

## Phase 3 — UI trang Intake trong CRM (3–4 ngày)

**Goal:** AM điền form trên web, auto-save.

### Task 3.1: Template + JS

**Files:**
- Create: `templates/crm_lead_intake.html`
- Create: `static/crm_lead_intake.js`
- Create: `static/crm_lead_intake.css`

**Route:**
```python
@app.get("/crm/intake")
def crm_lead_intake_page():
    # query: lifecycle_id, lead_id, mode, session_id
```

**UI sections:** render từ API definitions theo slug + mode filter.

- [ ] Accordion sections
- [ ] BANT radio 1–5 per row, live total
- [ ] Question table với textarea bind `answers_json`
- [ ] Stakeholder editable rows
- [ ] Decision + reason + 3 commitments
- [ ] Auto-save PATCH debounce
- [ ] Nút Hoàn thành → POST complete → redirect workflow

### Task 3.2: Prefill

- Load lead + latest AI brief + previous phone session nếu mode=in_person
- Hiển thị banner "Recap từ cuộc gọi [date]"

### Task 3.3: Entry points

- Workflow page: **「Mở Lead Intake」** → `/crm/intake?lifecycle_id=X&mode=phone`
- Lead UI (nếu có drawer): thêm 2 nút Gọi / Gặp

- [ ] E2E manual: tạo lifecycle → intake phone → complete → thấy form_data trên task

---

## Phase 4 — AI & KPI (1–2 ngày)

### Task 4.1: AI summary on complete

**Files:**
- Modify: `crm_lead_intake.py` — `generate_intake_summary_async`
- Add prompt template `intake_summary` trong definitions hoặc `crm_svc_workflow_steps.AI_PROMPT_TEMPLATES`

- [ ] Non-blocking thread như `crm_ai_qualify`
- [ ] Lưu `ai_summary` + `ai_suggested_questions`

### Task 4.2: Mở rộng `crm_ai_qualify.py`

- Prompt theo `service_slug` (không chỉ BĐS) khi `product_interest` map được slug
- Link qualify brief → prefill intake

### Task 4.3: Dashboard KPI (optional v1.1)

- Widget trên `/crm/service-delivery`: % lifecycle có intake completed
- API stats: avg bant_total by slug

---

## Phase 5 — Mở rộng form_fields (tuỳ chọn)

Nếu muốn task card workflow self-contained hơn mà không mở full page:

**Modify:** `crm_svc_workflow_steps.py` — thêm fields cho stage Lead:

| Field type mới | UI |
|----------------|-----|
| `select` | decision, temperature |
| `score` | bant_* (hoặc 1 JSON field) |
| `checkbox_group` | red_flags |

**Khuyến nghị:** Chỉ thêm 6 field chung mọi slug:

```python
{"key": "bant_total", "label": "BANT+ tổng", "type": "number"},
{"key": "lead_temperature", "label": "Nhiệt độ", "type": "text"},
{"key": "decision", "label": "Go/Nurture/No-Go", "type": "text"},
{"key": "decision_maker", "label": "Decision maker", "type": "text"},
{"key": "next_meeting", "label": "Lịch gặp tiếp", "type": "date"},
{"key": "intake_session_id", "label": "Intake session ID", "type": "number"},
```

Sync từ intake session on complete — không bắt AM nhập 2 lần.

---

## Thứ tự ưu tiên triển khai

```
Phase 1 (ngay) ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4
                     │              │
                     └──────────────┴── Phase 5 (optional)
```

| Tuần | Deliverable |
|------|-------------|
| 1 | Definitions module + static route + workflow link (Phase 1) |
| 2 | DB + API + merge task (Phase 2) |
| 3 | Intake UI + prefill (Phase 3) |
| 4 | AI summary + KPI (Phase 4) |

---

## Checklist go-live

- [ ] AM training: 30p walkthrough form phone vs gặp
- [ ] In 1 bộ form giấy backup per dịch vụ
- [ ] Verify 12 slug definitions khớp spec dịch vụ
- [ ] DIR sign-off ngưỡng BANT Go/Nurture
- [ ] Monitor 2 tuần: session count vs lead count

---

## Files tổng hợp (dự kiến)

| File | Phase |
|------|-------|
| `crm_lead_intake_definitions.py` | 1 |
| `crm_lead_intake.py` | 2 |
| `templates/crm_lead_intake.html` | 3 |
| `static/crm_lead_intake.js` | 3 |
| `tests/test_crm_lead_intake.py` | 2 |
| `tests/test_crm_lead_intake_definitions.py` | 1 |
| `docs/specs/2026-06-30-lead-intake-system-design.md` | ✅ |
| `docs/forms/lead-intake/*.html` | 1 (regenerate) |
