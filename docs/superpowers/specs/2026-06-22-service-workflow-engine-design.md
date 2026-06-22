# Design: Service Workflow Engine — Giai đoạn 1

**Ngày:** 2026-06-22
**Stack:** Flask 3 + SQLite, Anthropic SDK trực tiếp
**Nguyên tắc:** Simplicity First · Surgical Changes · AI-first (CLAUDE.md)

---

## Vấn đề cần giải quyết

Kanban `/crm/service-delivery` hiện chỉ hiển thị card tổng quan (stage, status).
AM không có nơi để:
- Theo dõi từng bước chi tiết của từng dịch vụ per KH
- Nhận hướng dẫn thực thi từ spec
- Nhờ AI tạo nội dung (proposal, brief, báo cáo...)
- Theo dõi tiến độ hoàn thành

**Giải pháp:** Thêm trang workflow chi tiết — click từ card kanban → mở trang riêng per lifecycle, hiển thị 7 stage dạng tabs, mỗi stage có danh sách tasks với form + AI assist.

---

## 1. Schema

### Bảng `crm_svc_tasks`

```sql
CREATE TABLE IF NOT EXISTS crm_svc_tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lifecycle_id  INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
    stage         TEXT NOT NULL DEFAULT '',
    step_index    INTEGER NOT NULL DEFAULT 0,
    title         TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    form_data     TEXT NOT NULL DEFAULT '{}',   -- JSON: structured fields AM nhập
    ai_output     TEXT NOT NULL DEFAULT '',     -- nội dung AI tạo ra
    ai_prompt_key TEXT NOT NULL DEFAULT '',     -- key → prompt template
    is_done       INTEGER NOT NULL DEFAULT 0,
    done_at       TEXT NOT NULL DEFAULT '',
    done_by       INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
    notes         TEXT NOT NULL DEFAULT '',
    is_custom     INTEGER NOT NULL DEFAULT 0,   -- 1 = AM tự thêm, 0 = seed từ template
    created_at    TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL DEFAULT ''
)
```

**Index:**
```sql
CREATE INDEX IF NOT EXISTS idx_svc_tasks_lifecycle ON crm_svc_tasks(lifecycle_id, stage)
```

---

## 2. File `crm_svc_workflow_steps.py`

Định nghĩa steps của từng dịch vụ, lấy từ 12 spec files. Cấu trúc:

```python
SERVICE_WORKFLOW_STEPS: dict[str, dict[str, list[dict]]] = {
    "dich-vu-seo-tong-the": {
        "lead": [
            {
                "title": "Tiếp nhận & chấm điểm lead",
                "description": "AI qualify lead, gán tag SEO tổng thể, phân loại ngân sách và nhu cầu.",
                "ai_prompt_key": "qualify_lead",
                "form_fields": [
                    {"key": "niche", "label": "Ngành KH", "type": "text"},
                    {"key": "budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
                    {"key": "current_traffic", "label": "Traffic hiện tại/tháng", "type": "number"},
                ],
            },
        ],
        "consult": [...],
        "proposal": [...],
        "onboard": [...],
        "deliver": [...],
        "handover": [...],
        "retain": [...],
    },
    # ... 11 dịch vụ còn lại
}
```

**AI Prompt Keys:**

| Key | Bước | AI tạo ra |
|-----|------|-----------|
| `qualify_lead` | Lead | Phân tích nhu cầu, gợi ý service |
| `consult_analysis` | Tư vấn | Phân tích website/tình trạng hiện tại |
| `draft_proposal` | Báo giá | Proposal + báo giá chi tiết |
| `kickoff_brief` | Onboarding | Brief kickoff, phân công nhân sự |
| `progress_report` | Triển khai | Báo cáo tiến độ tuần/tháng |
| `handover_report` | Nghiệm thu | Báo cáo kết quả tổng hợp |
| `upsell_suggest` | Chăm sóc | Gợi ý upsell, nhắc gia hạn |

---

## 3. File `crm_svc_tasks.py`

### Public API

```python
def ensure_schema(conn: sqlite3.Connection) -> None
    """Tạo bảng crm_svc_tasks. Gọi lúc app init."""

def seed_tasks(conn: sqlite3.Connection, lifecycle_id: int, service_slug: str) -> int
    """Seed tasks từ SERVICE_WORKFLOW_STEPS vào DB cho lifecycle này.
    Idempotent: nếu đã có tasks rồi thì không seed lại.
    Trả về số tasks đã tạo."""

def list_tasks(conn: sqlite3.Connection, lifecycle_id: int) -> dict[str, list[dict]]
    """Trả về {stage: [task, ...]} cho toàn bộ lifecycle."""

def update_task(
    conn: sqlite3.Connection,
    task_id: int,
    *,
    is_done: bool | None = None,
    notes: str | None = None,
    form_data: dict | None = None,
    done_by: int | None = None,
) -> None

def create_custom_task(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    stage: str,
    title: str,
    description: str = "",
) -> int
    """AM tự thêm task ngoài template. Trả về task_id mới."""

def delete_task(conn: sqlite3.Connection, task_id: int) -> None
    """Chỉ xoá được task is_custom=1."""

def run_ai_assist(
    conn: sqlite3.Connection,
    task_id: int,
    customer_context: dict,
) -> str
    """Gọi Claude Haiku để tạo nội dung cho task. Lưu vào ai_output.
    Trả về output hoặc '' nếu fail."""

def get_progress(conn: sqlite3.Connection, lifecycle_id: int) -> dict[str, dict]
    """Trả về {stage: {total: N, done: M, pct: X}} per stage."""
```

---

## 4. Routes (thêm vào `app.py`)

| Method | Route | Mô tả |
|--------|-------|--------|
| `GET` | `/crm/service-delivery/<int:lifecycle_id>` | Trang workflow chi tiết |
| `POST` | `/api/crm/svc-tasks/seed` | Seed tasks khi mở trang lần đầu |
| `PATCH` | `/api/crm/svc-tasks/<int:task_id>` | Tick done / lưu form_data / notes |
| `POST` | `/api/crm/svc-tasks` | AM tạo custom task |
| `DELETE` | `/api/crm/svc-tasks/<int:task_id>` | Xoá custom task |
| `POST` | `/api/crm/svc-tasks/<int:task_id>/ai-assist` | AI generate nội dung |

---

## 5. Template `crm_service_workflow.html`

Extends `admin_layout.html`. Cấu trúc:

```
Header:
  - Tên dịch vụ (service_slug → label đẹp)
  - KH: [tên KH] | Stage hiện tại: [badge màu]
  - Nút "← Về kanban"

Progress bar tổng:
  - X/Y tasks hoàn thành (toàn bộ lifecycle)

Tabs 7 stages (horizontal):
  - Tab active = stage hiện tại của lifecycle
  - Mỗi tab có badge: "3/5 ✓"

Nội dung tab:
  Mỗi task:
  ┌─────────────────────────────────────────────┐
  │ ☐ / ✓  [Tên bước]              [Người phụ trách?]
  │ Hướng dẫn: [description từ spec]
  │
  │ Form fields (nếu có):
  │   Ngành KH: [____]  Ngân sách: [____]
  │
  │ Ghi chú AM: [textarea]
  │
  │ AI Output: [nội dung AI đã tạo — nếu có]
  │
  │ [🤖 AI Hỗ trợ]  [✓ Hoàn thành]
  └─────────────────────────────────────────────┘

  [+ Thêm task tuỳ chỉnh]
```

**JS:** Vanilla JS + fetch() cho tất cả actions. Không reload page.

---

## 6. AI Integration

- Model: `claude-haiku-4-5-20251001`
- Chạy **synchronous** trong route (không thread) vì AM đang chờ response
- Timeout: 30s
- Fail silent: lỗi → trả `{"ai_output": "", "error": "AI không khả dụng"}`
- Context đưa vào prompt:
  - `service_slug`, `stage`, `task.title`, `task.description`
  - `customer_name`, `niche`, `budget` (từ crm_customers + crm_leads)
  - Tasks đã done trước đó trong stage này (để AI có context tiến độ)

---

## 7. Files bị chạm

| File | Loại | Ước tính |
|------|------|---------|
| `crm_svc_workflow_steps.py` | Tạo mới | ~400 dòng (steps 12 dịch vụ + AI prompts) |
| `crm_svc_tasks.py` | Tạo mới | ~200 dòng |
| `tests/test_crm_svc_tasks.py` | Tạo mới | ~120 dòng |
| `app.py` | Sửa surgical | +60 dòng (6 routes + import + init) |
| `templates/crm_service_workflow.html` | Tạo mới | ~250 dòng |
| `templates/crm_service_delivery.html` | Sửa surgical | +5 dòng (link card → detail page) |

**Tổng:** ~1035 dòng, 3 file Python mới + 1 template mới + 2 file sửa nhỏ.

---

## 8. Checklist Implementation

- [ ] `crm_svc_workflow_steps.py` — 12 dịch vụ × 7 stages × steps
- [ ] `crm_svc_tasks.py` — schema + 7 hàm public
- [ ] `tests/test_crm_svc_tasks.py` — TDD
- [ ] Wire `ensure_schema` vào `app.py` init
- [ ] 6 routes trong `app.py`
- [ ] `templates/crm_service_workflow.html`
- [ ] Update kanban card → link detail
