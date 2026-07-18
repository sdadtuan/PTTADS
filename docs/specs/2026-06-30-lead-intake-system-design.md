# Design: Hệ thống Lead Intake — Form gọi điện & gặp trực tiếp

**Ngày:** 2026-06-30  
**Phiên bản:** 1.0  
**Stack:** Flask 3 + SQLite, Anthropic SDK, Jinja2 + Vanilla JS  
**Nguyên tắc:** Simplicity First · Surgical Changes · AI-first · Single source of truth

---

## 1. Vấn đề cần giải quyết

### 1.1 Hiện trạng

| Thành phần | Trạng thái | Hạn chế |
|------------|------------|---------|
| HTML forms (`docs/forms/lead-intake/`) | ✅ 13 file in được | Ngoài CRM; AM điền giấy → nhập lại CRM thủ công |
| `crm_svc_workflow_steps.py` — task Lead | ✅ 4 field/dịch vụ | Không đủ BANT+, stakeholder, 15+ câu qualify |
| Service Workflow UI | ✅ Form grid trên task card | Không phân PHẦN A (gọi) vs B (gặp); không script/objections |
| `crm_ai_qualify.py` | ✅ Brief BĐS | Chưa map 12 dịch vụ agency; chưa đọc intake session |
| Lead care 8 bước | ✅ `first_contact` sync SVC Lead | Không có artifact “buổi gọi/gặp” lưu DB |
| PowerPoint checklist | ✅ 47 slides | Tài liệu đào tạo, không operational trong app |

### 1.2 Mục tiêu

1. **Một nguồn dữ liệu** cho câu hỏi qualify, script, red flags, checklist tài liệu — 12 dịch vụ + form chung.
2. **Hai mode vận hành:** `phone` (15–25 phút) và `in_person` (45–60 phút).
3. **Lưu kết quả vào CRM** — đồng bộ task Lead, lead care, AI qualify, chuyển stage Consult.
4. **Hỗ trợ chốt khách:** BANT+ scoring, Go/Nurture/No-Go, 3 cam kết KH, script chốt Proposal.
5. **Giữ HTML/PPT** làm fallback in offline; app là canonical khi online.

---

## 2. Phạm vi & không nằm trong phạm vi

### In scope

- Module `crm_lead_intake.py` (schema + CRUD + scoring)
- Module `crm_lead_intake_definitions.py` (data-only — tách từ generator)
- Trang intake trong CRM gắn `lifecycle_id` và/hoặc `lead_id`
- Mở rộng `form_fields` stage Lead trong workflow (hoặc intake session riêng)
- API JSON lưu/đọc session; prefill từ lead + AI brief
- Nút mở form từ Service Workflow + Quản lý Lead
- AI: tóm tắt session → gợi ý Go/No-Go + câu hỏi còn thiếu

### Out of scope (v1)

- Mobile app native
- Ghi âm cuộc gọi / transcription tự động
- E-signature trên form
- Form công khai cho KH tự điền (chỉ nội bộ AM)

---

## 3. Kiến trúc tổng thể

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│ crm_leads       │────▶│ crm_lead_intake_sessions │────▶│ crm_svc_tasks       │
│ (lead_id)       │     │ mode: phone | in_person  │     │ stage=lead          │
└─────────────────┘     │ bant_json, answers_json  │     │ form_data merged    │
         │              │ decision: go|nurture|no  │     └─────────────────────┘
         │              └──────────────────────────┘              │
         ▼                          │                              ▼
┌─────────────────┐                 │              ┌──────────────────────────┐
│ crm_lead_care   │◀────────────────┘              │ crm_service_lifecycle    │
│ first_contact   │  sync on complete                │ advance lead→consult     │
└─────────────────┘                                  └──────────────────────────┘
         ▲
         │
┌─────────────────┐
│ crm_ai_qualify  │  prefill + post-summary
└─────────────────┘
```

**Luồng chính:**

1. Lead vào CRM → (tuỳ chọn) AI qualify brief.
2. AM tạo / mở **Intake Session** từ lifecycle hoặc lead.
3. Chọn mode **Gọi** hoặc **Gặp** → UI render sections từ definitions.
4. Lưu draft (auto-save) → hoàn thành session.
5. Hệ thống: merge `form_data` task Lead, log activity, sync care stage, gợi ý `advance_stage` nếu Go + task done.

---

## 4. Schema

### 4.1 Bảng `crm_lead_intake_sessions`

```sql
CREATE TABLE IF NOT EXISTS crm_lead_intake_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL,
    lifecycle_id    INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
    service_slug    TEXT NOT NULL DEFAULT '',
    mode            TEXT NOT NULL DEFAULT 'phone',  -- phone | in_person
    status          TEXT NOT NULL DEFAULT 'draft',  -- draft | completed
    am_id           INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,

    -- Meta buổi làm việc
    contact_name    TEXT NOT NULL DEFAULT '',
    contact_role    TEXT NOT NULL DEFAULT '',
    company_name    TEXT NOT NULL DEFAULT '',
    source          TEXT NOT NULL DEFAULT '',

    -- Qualify structured
    bant_json       TEXT NOT NULL DEFAULT '{}',       -- {budget:3, authority:4, ...}
    bant_total      INTEGER NOT NULL DEFAULT 0,
    lead_temperature TEXT NOT NULL DEFAULT '',        -- hot | warm | cold
    decision        TEXT NOT NULL DEFAULT '',         -- go | nurture | no_go
    decision_reason TEXT NOT NULL DEFAULT '',

    -- Answers: key → value (questions, stakeholders, commitments, docs checked)
    answers_json    TEXT NOT NULL DEFAULT '{}',

    -- Stakeholders [{role, name, title, influence, notes}]
    stakeholders_json TEXT NOT NULL DEFAULT '[]',

    -- 3 cam kết KH [{label, detail, deadline}]
    commitments_json  TEXT NOT NULL DEFAULT '[]',

    -- Next steps
    next_meeting_at   TEXT NOT NULL DEFAULT '',
    next_meeting_note TEXT NOT NULL DEFAULT '',
    proposal_date     TEXT NOT NULL DEFAULT '',

    -- AI
    ai_summary        TEXT NOT NULL DEFAULT '',
    ai_suggested_questions TEXT NOT NULL DEFAULT '[]',

    started_at      TEXT NOT NULL DEFAULT '',
    completed_at    TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_intake_lifecycle
    ON crm_lead_intake_sessions(lifecycle_id, status);
CREATE INDEX IF NOT EXISTS idx_intake_lead
    ON crm_lead_intake_sessions(lead_id, mode);
```

### 4.2 Ràng buộc nghiệp vụ

| Rule | Mô tả |
|------|--------|
| `lifecycle_id` hoặc `lead_id` | Ít nhất một phải có |
| `mode=phone` completed | Gợi ý tạo lịch `in_person` nếu decision=go |
| `mode=in_person` completed + decision=go | Cho phép đánh dấu task Lead done (nếu BANT≥24) |
| `bant_total` | Auto-sum từ `bant_json` (6 tiêu chí × 1–5) |
| Một lifecycle | Nhiều session (gọi lần 1, gặp lần 1, gọi follow-up) |

### 4.3 Không thêm bảng mới cho definitions

Definitions nằm trong `crm_lead_intake_definitions.py` (Python dict) — version cùng code, regenerate HTML từ script.

---

## 5. Data model — Definitions

### 5.1 Cấu trúc `INTAKE_COMMON`

```python
INTAKE_COMMON = {
    "call_scripts": [...],           # 3 biến thể
    "bant_criteria": [...],          # 6 rows hint
    "stakeholder_roles": [...],
    "objections_common": [...],
    "discovery_common": [...],       # 10 câu PHẦN B chung
    "crm_sync_checklist": [...],
    "meeting_prep_checklist": [...],
    "go_thresholds": {"go": 24, "nurture_min": 18},
}
```

### 5.2 Cấu trúc `INTAKE_BY_SLUG[slug]`

| Key | Mục đích |
|-----|----------|
| `title`, `group`, `overview`, `icp`, `sla` | Header + training |
| `call_script` | Script mở đầu tailored |
| `phone_questions[]` | 12–15 câu PHẦN A |
| `inperson_questions[]` | 15–20 câu PHẦN B |
| `red_flags[]` | Checkbox No-Go |
| `urgency_triggers[]` | Hot lead signals |
| `objections[]` | (title, hint) |
| `demo_checklist[]` | Live audit khi gặp |
| `docs[]` | (name, lead_col, onboard_col) |
| `kpi_questions[]`, `scope_questions[]` | Chốt cam kết |
| `closing_script` | Book Proposal |
| `upsell[]` | Paths |
| `crm_field_map` | Map answer keys → `form_fields` keys |

**Nguồn hiện tại:** `scripts/generate_lead_intake_forms.py` → `SERVICE_FORMS` (tách ra module riêng).

---

## 6. UI / UX

### 6.1 Entry points

| Vị trí | Hành động |
|--------|-----------|
| `/crm/service-delivery/<lifecycle_id>` | Nút **「Lead Intake」** → `/crm/intake?lifecycle_id=` |
| Quản lý Lead (drawer/modal chi tiết) | **「Gọi lead」** / **「Gặp KH」** |
| Task card stage Lead | Link **「Mở form đầy đủ」** |

### 6.2 Trang `/crm/intake` (hoặc `/crm/intake/<session_id>`)

**Layout:**

```
[Header: Dịch vụ · KH · Mode toggle: Gọi | Gặp]
[Progress: sections completed / total]
┌─────────────────────────────────────────────┐
│ Section accordion (collapsible)              │
│  - Meta & Script                             │
│  - BANT+ (score 1-5 radio per row)           │
│  - Câu hỏi qualify (table + textarea)        │
│  - Red flags / Urgency (checkbox)            │
│  - Objections (textarea per row)             │
│  - Stakeholder map (editable table)          │
│  - [Gặp only] Discovery / Demo / Docs        │
│  - Decision + 3 cam kết                      │
│  - Next steps                                │
└─────────────────────────────────────────────┘
[Sticky footer: Lưu nháp | Hoàn thành | In PDF]
```

**Mode `phone`:** ẩn sections Discovery sâu, Demo, Docs onboard — chỉ hiện subset + lịch hẹn gặp.

**Mode `in_person`:** hiện đủ; prefill recap từ session `phone` completed gần nhất.

### 6.3 Auto-save

- Debounce 2s → `PATCH /api/crm/intake/<id>`
- Indicator “Đã lưu lúc HH:MM”

### 6.4 In / PDF

- Link **「In form giấy」** → static HTML (`/static/forms/lead-intake/<slug>.html`) hoặc print view cùng template.

---

## 7. API

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/api/crm/intake/definitions` | `{common, slugs, fields}` cho UI builder |
| GET | `/api/crm/intake/definitions/<slug>` | Definition một dịch vụ |
| POST | `/api/crm/intake/sessions` | Tạo session `{lifecycle_id?, lead_id?, mode, service_slug}` |
| GET | `/api/crm/intake/sessions/<id>` | Chi tiết session |
| PATCH | `/api/crm/intake/sessions/<id>` | Cập nhật partial (auto-save) |
| POST | `/api/crm/intake/sessions/<id>/complete` | Hoàn thành + side effects |
| GET | `/api/crm/intake/sessions?lifecycle_id=` | List sessions của lifecycle |
| POST | `/api/crm/intake/sessions/<id>/ai-summary` | AI tóm tắt + gợi ý |

### 7.1 Side effects khi `complete`

```python
def complete_intake_session(conn, session_id, actor_id):
    # 1. Validate: decision set; nếu go → bant_total >= 18
    # 2. Merge answers → crm_svc_tasks form_data (stage lead, step 0)
    # 3. Log crm_leads activity: "intake_phone" | "intake_in_person"
    # 4. sync_lead_from_lifecycle_stage nếu lifecycle_id
    # 5. Nếu phone+go: tạo reminder activity "Hẹn gặp KH"
    # 6. Nếu in_person+go: complete lead task (optional flag)
    # 7. trigger AI summary async → ai_summary field
```

---

## 8. Tích hợp AI

### 8.1 Prefill (khi mở session mới)

- Đọc `crm_leads.meta_json.ai_qualify_brief`
- Đọc lead fields: `need`, `budget`, `product_interest`, `source`
- Prefill: `company_name`, câu trả lời P1–P3 nếu có trong brief

### 8.2 Prompt `intake_summary` (Haiku)

```
Bạn là AM PTT. Tóm tắt buổi {mode} dịch vụ {service_name}:
BANT: {bant_json}, Decision: {decision}
Câu trả lời: {answers_json}
→ JSON: {summary, risks[], missing_questions[], recommended_next_step}
```

### 8.3 Prompt `intake_coach` (real-time, optional v2)

Gợi ý câu hỏi tiếp theo dựa trên red flags đã tick.

---

## 9. Mở rộng Workflow Steps (stage Lead)

Hai hướng (chọn **B** cho v1):

| | Hướng A | Hướng B (khuyến nghị) |
|---|---------|------------------------|
| Cách | Mở rộng `form_fields` lên 20+ field | Giữ 4 field CRM; intake session là master |
| Sync | Trực tiếp trên task card | Merge khi complete intake |
| UI | Grid nhỏ trên workflow | Trang intake riêng |

**Mapping merge (ví dụ SEO tổng thể):**

| Intake answer key | CRM `form_fields.key` |
|-------------------|------------------------|
| `p1_domain` | `domain` |
| `p6_budget` | `budget` |
| `p11_niche` | `niche` |
| `pain_summary` | `need` |
| `bant_total`, `decision` | `notes` (append) |

---

## 10. BANT+ & Quyết định

| Tổng điểm (6–30) | Quyết định gợi ý | Hành động |
|------------------|------------------|-----------|
| ≥ 24 | **Go** | Book Consult/Proposal; complete phone → schedule in_person |
| 18–23 | **Nurture** | Drip + follow-up 7–14 ngày |
| < 18 | **No-Go** | Từ chối + gợi ý dịch vụ khác nếu fit |

**Override:** AM có thể chọn decision khác với ghi `decision_reason` bắt buộc.

**Red flag bắt buộc No-Go:** tick ≥2 red flags → cảnh báo UI (không block hard trừ regulated industries).

---

## 11. RACI

| Hoạt động | AM | SP | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Gọi lead — PHẦN A | R | I | C (prefill) | — | I |
| Gặp trực tiếp — PHẦN B | R | C (demo kỹ thuật) | C (summary) | — | I |
| Quyết định Go/No-Go | R | — | C | — | A (deal lớn) |
| Nhập CRM / complete session | R | — | I | — | — |
| Duyệt exception No-Go→Go | R | — | — | — | A |

---

## 12. KPI nội bộ (sau triển khai)

| KPI | Ngưỡng | Nguồn |
|-----|--------|-------|
| % lead có intake phone trong 48h | ≥ 90% | sessions / new leads |
| Convert Go → Consult | ≥ 35% | decision=go → stage consult |
| Thời gian trung bình phone session | 15–25 phút | completed_at - started_at |
| BANT avg trên lead won | ≥ 22 | bant_total |
| Intake in_person trước Proposal | ≥ 80% Go leads | sessions mode=in_person |

---

## 13. Liên kết tài sản hiện có

| Tài sản | Vai trò sau triển khai |
|---------|------------------------|
| `docs/forms/lead-intake/*.html` | Generated từ definitions — in offline |
| `docs/Checklist_Tiep_Nhan_Lead_12_Dich_Vu.pptx` | Training / onboarding AM |
| `docs/specs/services/*.md` | Spec nghiệp vụ gốc — definitions sync thủ công khi đổi spec |
| `crm_svc_workflow_steps.py` | Task Lead + AI prompts |
| `crm_svc_lead_sync.py` | Sync care ↔ lifecycle on complete |

---

## 14. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|--------|------------|
| AM không dùng app, vẫn giấy | Giữ HTML print; KPI tracking sessions |
| Definitions lệch spec dịch vụ | Single module + test snapshot; review khi đổi spec |
| Form quá dài | Accordion + mode phone ẩn bớt section |
| Duplicate data task vs session | Session master; merge on complete only |
| AI qualify BĐS-centric | Phase 2: prompt theo `service_slug` |

---

## 15. Tiêu chí nghiệm thu v1

- [ ] AM tạo session phone từ workflow page, lưu draft, complete với decision=go
- [ ] Session in_person prefill recap từ phone
- [ ] Complete merge vào `crm_svc_tasks.form_data` stage lead
- [ ] Activity log trên lead
- [ ] HTML forms regenerate từ cùng definitions module
- [ ] BANT total tính đúng; gợi ý Go/Nurture/No-Go hiển thị
- [ ] Ít nhất 1 test integration per slug (smoke: definition load)

---

**Tài liệu liên quan:**  
- [Kế hoạch triển khai Phase 1–4](../superpowers/plans/2026-06-30-lead-intake-system.md)  
- [Form README](../forms/lead-intake/README.md)  
- [Service Lifecycle Design](./2026-06-22-service-lifecycle-design.md)
