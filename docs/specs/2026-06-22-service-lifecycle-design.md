# Design: PTTP Service Lifecycle — Phương án B

**Ngày:** 2026-06-22
**Stack:** Flask 3 + SQLite, Anthropic SDK trực tiếp
**Nguyên tắc:** Simplicity First · Surgical Changes · AI-first (CLAUDE.md)

---

## Vấn đề cần giải quyết

Các module hiện tại của PTTP hoạt động rời rạc:
- `crm_contracts` không có `service_slug` → không biết đang giao dịch vụ gì
- `crm_sop_runs` link tới `campaign_id` nhưng không link tới `contract_id`
- `crm_care.py` làm việc trên `case_id`, không biết KH đang ở giai đoạn nào
- `crm_ai_qualify.py` chấm điểm lead nhưng không gán service_slug
- Không có màn hình nào cho thấy "KH X đang ở giai đoạn nào của dịch vụ Y"

**Giải pháp:** Thêm bảng `crm_service_lifecycle` làm orchestration layer — không rebuild, không đổi architecture, chỉ thêm "xương sống" để AI và các module join qua đó.

---

## 1. Schema

### File mới: `crm_service_lifecycle.py`

Theo pattern `_ensure_crm_sop_schema()` hiện có trong `app.py`.

#### Bảng `crm_service_lifecycle`

```sql
CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id          INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL,
    customer_id      INTEGER REFERENCES crm_customers(id) ON DELETE SET NULL,
    contract_id      INTEGER REFERENCES crm_contracts(id) ON DELETE SET NULL,
    service_slug     TEXT NOT NULL,
    stage            TEXT NOT NULL DEFAULT 'lead',
    status           TEXT NOT NULL DEFAULT 'draft',
    assigned_am      INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
    assigned_sp      INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
    stage_entered_at TEXT NOT NULL,
    notes            TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
)
```

**stage values:** `lead | consult | proposal | onboard | deliver | handover | retain`

**status values:**
- `draft` — AI tạo tự động từ lead, chờ AM confirm
- `active` — AM đã confirm, đang theo dõi chính thức
- `closed` — dịch vụ hoàn thành
- `lost` — KH không chuyển đổi

#### Bảng `crm_service_lifecycle_events`

```sql
CREATE TABLE IF NOT EXISTS crm_service_lifecycle_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
    from_stage   TEXT,
    to_stage     TEXT NOT NULL,
    actor_id     INTEGER REFERENCES crm_staff(id),
    actor_type   TEXT NOT NULL DEFAULT 'human',
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
)
```

**actor_type values:** `human | ai`

#### Surgical change — `crm_contracts`

```sql
ALTER TABLE crm_contracts ADD COLUMN service_slug TEXT NOT NULL DEFAULT ''
```

Thực hiện bằng pattern `try/except OperationalError` như các migration hiện có.

---

## 2. Public API của `crm_service_lifecycle.py`

```python
def ensure_schema(conn: sqlite3.Connection) -> None
    """Gọi lúc app init, tạo 2 bảng + migration crm_contracts."""

def create_draft_lifecycle(
    conn: sqlite3.Connection,
    lead_id: int,
    service_slug: str,
    suggested_by: str = 'ai'
) -> int
    """Tạo lifecycle status=draft, stage=lead. Trả về id."""

def activate_lifecycle(
    conn: sqlite3.Connection,
    contract_id: int
) -> bool
    """Khi contract status='active': set lifecycle status=active, stage=onboard.
    Lookup: tìm lifecycle WHERE customer_id = contract.customer_id AND status='draft'
    ORDER BY updated_at DESC LIMIT 1.
    Ghi contract_id vào lifecycle. Trả False nếu không tìm thấy."""

def advance_stage(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    to_stage: str,
    actor_id: int | None = None,
    actor_type: str = 'human',
    notes: str = ''
) -> None
    """Chuyển stage, ghi event vào lifecycle_events."""

def get_by_lead(conn: sqlite3.Connection, lead_id: int) -> dict | None

def get_by_contract(conn: sqlite3.Connection, contract_id: int) -> dict | None

def get_stage_context(conn: sqlite3.Connection, customer_id: int) -> dict | None
    """crm_care.py dùng để lấy {service_slug, stage, stage_days}."""

def list_active(
    conn: sqlite3.Connection,
    service_slug: str | None = None,
    am_id: int | None = None,
    include_draft: bool = False
) -> list[dict]
    """Dashboard kanban dùng."""
```

---

## 3. Data Flow

```
Lead vào form
    │
    ▼
crm_ai_qualify.py  [WIRE +5 dòng]
    └─ AI Call 1: suggest service_slug từ niche/pain_points
    └─ create_draft_lifecycle(lead_id, slug)   → status=draft, stage=lead
    │
    ▼
AM xem lead → thấy draft lifecycle card
    │  AM confirm service_slug (giữ hoặc override)
    │  Stage advance: lead → consult → proposal
    │
    ▼
AM tạo crm_contracts  [WIRE +8 dòng]
    │  contract.service_slug = lifecycle.service_slug
    │  Khi status='active' → activate_lifecycle(contract_id)
    │  → lifecycle: status=active, stage=onboard
    │
    ▼
AM/SP advance stage qua Dashboard
    │  deliver → handover → retain
    │  Mỗi advance ghi event (actor_type=human)
    │
    ▼
crm_care.py  [WIRE +6 dòng]
    │  get_stage_context(customer_id) → thêm vào AI prompt
    │  Care action phù hợp stage hiện tại
    │
    ▼
crm_daily_work_report.py  [WIRE +4 dòng]
    │  JOIN lifecycle → service_slug
    │  Báo cáo biết đây là dịch vụ gì
    │
    ▼
AI Call 3: KPI alert (nền, khi vào retain)
    └─ Severity: ok | warn | critical → ghi vào lifecycle notes
```

---

## 4. Routes mới (thêm vào `app.py`)

| Method | Route | Mô tả |
|--------|-------|--------|
| `GET` | `/crm/service-delivery` | Dashboard kanban |
| `GET` | `/api/crm/service-lifecycle` | List (filter: stage, slug, am_id) |
| `POST` | `/api/crm/service-lifecycle` | Tạo thủ công hoặc confirm draft |
| `PATCH` | `/api/crm/service-lifecycle/<id>` | Advance stage, update fields |
| `GET` | `/api/crm/service-lifecycle/<id>/events` | Lịch sử transitions |

Template: `templates/crm_service_delivery.html`
- Extend `_partials/crm_base.html`
- Kanban 7 cột, Vanilla JS, `fetch()` PATCH để advance stage

---

## 5. AI Integration

### AI Call 1 — Suggest service_slug (hàm nội bộ `_suggest_service_slug()`, gọi từ thread trong `crm_ai_qualify.py`)

```python
# Input
{
  "niche": brief.get("niche"),
  "budget": brief.get("budget"),
  "pain_points": brief.get("pain_points"),
  "lead_message": lead["first_message"]
}

# Output (Pydantic)
class ServiceSuggestion(BaseModel):
    service_slug: str    # 1 trong 12 slug
    confidence: float    # 0.0–1.0
    reason: str          # 1 câu

# Fallback: service_slug='' → lifecycle tạo với slug rỗng, AM tự chọn
```

### AI Call 2 — Stage-aware care context (trong `crm_care.py`)

```python
# Thêm vào system prompt hiện có:
f"KH đang dùng dịch vụ {service_slug}, giai đoạn {stage} ({stage_days} ngày). "
f"Ưu tiên hành động chăm sóc phù hợp giai đoạn này."

# Fallback: không tìm thấy lifecycle → care chạy bình thường
```

### AI Call 3 — KPI alert (chạy nền khi vào stage `retain`)

```python
# Input
{
  "service_slug": str,
  "kpi_actual": dict,
  "kpi_target": dict,   # từ service spec
  "months_active": int
}

# Output (Pydantic)
class KpiAlert(BaseModel):
    severity: str           # ok | warn | critical
    message: str            # 1–2 câu cho AM
    suggested_action: str

# Fallback: fail → log error, không gửi alert, không crash
```

**Quy tắc chung:**
- `anthropic.Anthropic().messages.create()` trực tiếp, model `claude-sonnet-4-6`
- Mọi AI call chạy `threading.Thread(daemon=True)` — không block request
- Fail silent: AI fail → feature vẫn chạy, chỉ thiếu AI enhancement

---

## 6. Checklist Implementation

**Bước 1 — Schema & core module**
- [ ] Tạo `crm_service_lifecycle.py` với schema + 7 hàm public
- [ ] Gọi `ensure_schema()` trong `app.py` init
- [ ] Migration `crm_contracts.service_slug`
- [ ] Test: schema tạo đúng trên SQLite in-memory

**Bước 2 — AI Call 1 + wire qualify**
- [ ] Thêm `suggest_service_slug()` vào `crm_service_lifecycle.py`
- [ ] Wire vào `crm_ai_qualify.py` sau `save_qualify_brief()`
- [ ] Test: lead qualify → draft lifecycle tồn tại

**Bước 3 — Wire contract**
- [ ] Thêm `service_slug` vào form tạo/edit contract
- [ ] Wire `activate_lifecycle()` khi contract `status='active'`
- [ ] Test: contract ký → lifecycle stage = `onboard`

**Bước 4 — Dashboard**
- [ ] Thêm 5 routes vào `app.py`
- [ ] Tạo `templates/crm_service_delivery.html`
- [ ] Test: kanban hiển thị đúng, filter hoạt động, advance stage OK

**Bước 5 — Wire care + report**
- [ ] Wire `get_stage_context()` vào `crm_care.py`
- [ ] Wire service_slug join vào `crm_daily_work_report.py`
- [ ] Test: care report có context stage; report nhóm được theo dịch vụ

**Bước 6 — AI Call 3 KPI alert**
- [ ] Thêm `check_kpi_alert()` chạy nền khi advance → `retain`
- [ ] Test: alert ghi vào log; API fail không crash app

---

## 7. Files bị chạm

| File | Loại thay đổi | Ước tính |
|------|--------------|---------|
| `crm_service_lifecycle.py` | **Tạo mới** | ~200 dòng |
| `app.py` | Thêm: init schema, 5 routes, wire contract | ~80 dòng |
| `crm_ai_qualify.py` | Wire AI Call 1 sau save_qualify_brief | ~15 dòng |
| `crm_care.py` | Wire get_stage_context vào prompt | ~10 dòng |
| `crm_daily_work_report.py` | JOIN lifecycle | ~8 dòng |
| `templates/crm_service_delivery.html` | **Tạo mới** | ~150 dòng |

**Tổng:** ~463 dòng, 4 file sửa surgical + 2 file mới.
