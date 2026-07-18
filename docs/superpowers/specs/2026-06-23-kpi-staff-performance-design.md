# Design: KPI Staff Performance — Phase 4

**Ngày:** 2026-06-23
**Stack:** Flask 3 + SQLite, Anthropic SDK trực tiếp
**Nguyên tắc:** YAGNI · Simplicity First · Surgical Changes

---

## Vấn đề

PTTP CRM đã có `crm_service_lifecycle` với `assigned_am` và `assigned_sp`, `crm_svc_tasks` với `done_by`, nhưng không có cách nào xem hiệu suất của từng nhân viên theo dịch vụ. AM/SP không biết mình đang đạt bao nhiêu % target tháng này.

---

## Giải pháp (Approach B đã chọn)

**Targets + actuals:** Metrics tính live từ dữ liệu hiện có (lifecycle, tasks, payments, expenses, risks). AM/SP đặt target theo tháng. So sánh actual vs target. AI phân tích hiệu suất theo staff+tháng.

---

## Schema

### `crm_svc_kpi_targets`

```sql
CREATE TABLE IF NOT EXISTS crm_svc_kpi_targets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id     INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
    role         TEXT NOT NULL DEFAULT 'am',   -- 'am' | 'sp'
    metric_key   TEXT NOT NULL DEFAULT '',
    year         INTEGER NOT NULL,
    month        INTEGER NOT NULL,
    target_value REAL NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT '',
    UNIQUE(staff_id, metric_key, year, month)
)
```

### `crm_svc_kpi_scans`

```sql
CREATE TABLE IF NOT EXISTS crm_svc_kpi_scans (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id  INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
    ai_output TEXT NOT NULL DEFAULT '',
    role      TEXT NOT NULL DEFAULT 'am',
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT ''
)
```

---

## Metric Keys (fixed set)

### AM metrics

| metric_key | Tính từ | Ghi chú |
|-----------|--------|--------|
| `received_revenue` | SUM(payments.amount_vnd WHERE status='received' AND received_on trong month/year), từ lifecycles có `assigned_am = staff_id` | Monthly |
| `active_services` | COUNT(lifecycles WHERE assigned_am=staff_id AND status='active') | Current state |
| `avg_margin_pct` | AVG(margin_pct) tính từ `get_summary` cho từng active lifecycle | Current state |
| `outstanding` | SUM(outstanding) từ `get_summary` qua tất cả active lifecycles | Current state |

### SP metrics

| metric_key | Tính từ | Ghi chú |
|-----------|--------|--------|
| `tasks_completed` | COUNT(tasks WHERE done_by=staff_id AND is_done=1 AND updated_at trong month/year) | Monthly |
| `tasks_pending` | COUNT(tasks WHERE is_done=0, từ lifecycles có assigned_sp=staff_id) | Current state |
| `risks_resolved` | COUNT(risks WHERE is_active=0 AND updated_at trong month/year, từ lifecycles có assigned_sp=staff_id) | Monthly (approx) |

---

## Files

| File | Loại | Mô tả |
|------|------|-------|
| `crm_svc_kpi.py` | Tạo mới | Schema + 8 public functions |
| `tests/test_crm_svc_kpi.py` | Tạo mới | TDD — ~20 tests |
| `app.py` | Sửa nhỏ | +import, +init schema, +5 routes, update `crm_service_workflow_page` |
| `templates/crm_service_workflow.html` | Sửa nhỏ | +staff section (dưới finance section) |
| `templates/crm_staff_kpi.html` | Tạo mới | Dashboard tổng hợp KPI toàn staff |

---

## Public API `crm_svc_kpi.py`

```python
def ensure_schema(conn: sqlite3.Connection) -> None

def get_am_metrics(conn, staff_id: int, year: int, month: int) -> dict
# Returns:
# {
#   received_revenue: int,    # sum payments received trong tháng từ AM's lifecycles
#   active_services: int,     # count active lifecycles hiện tại
#   avg_margin_pct: float,    # avg margin% across active lifecycles (0.0 if none)
#   outstanding: int,         # sum outstanding across active lifecycles
# }

def get_sp_metrics(conn, staff_id: int, year: int, month: int) -> dict
# Returns:
# {
#   tasks_completed: int,     # tasks done by SP trong tháng
#   tasks_pending: int,       # tasks chưa xong trong SP's lifecycles
#   risks_resolved: int,      # risks resolved trong tháng trong SP's lifecycles
# }

def get_lifecycle_staff_metrics(conn, lifecycle_id: int) -> dict
# Returns:
# {
#   am: {id, name, tasks_done, received_revenue} | None,
#   sp: {id, name, tasks_done, risks_resolved} | None,
# }
# AM tasks_done: COUNT(tasks WHERE lifecycle_id=X AND is_done=1) — tất cả tasks done trong lifecycle
# AM received_revenue: SUM(payments WHERE lifecycle_id=X AND status='received')
# SP tasks_done: COUNT(tasks WHERE lifecycle_id=X AND is_done=1 AND done_by=sp_id) — chỉ tasks SP làm
# SP risks_resolved: COUNT(risks WHERE lifecycle_id=X AND is_active=0)

def set_target(conn, staff_id: int, role: str, metric_key: str,
               year: int, month: int, target_value: float) -> None
# INSERT OR REPLACE

def get_targets(conn, staff_id: int, year: int, month: int) -> dict[str, float]
# Returns: {metric_key: target_value} — chỉ trả keys đã được set

def get_latest_kpi_scan(conn, staff_id: int, role: str, year: int, month: int) -> str
# Filter by staff_id + role + year + month, ORDER BY id DESC LIMIT 1

def run_ai_kpi_scan(conn, staff_id: int, role: str,
                    year: int, month: int, context: dict) -> str
# fail silent → ""
# Lưu vào crm_svc_kpi_scans sau khi scan thành công
```

---

## Routes

| Method | Route | Mô tả |
|--------|-------|--------|
| GET | `/crm/staff-kpi` | Dashboard page — staff selector + month filter |
| GET | `/api/crm/staff-kpi/<staff_id>/metrics` | Query params: `role`, `year`, `month` |
| POST | `/api/crm/staff-kpi/<staff_id>/targets` | Body: `{role, metric_key, year, month, target_value}` |
| POST | `/api/crm/staff-kpi/<staff_id>/ai-scan` | Body: `{role, year, month}` |
| GET | `/api/crm/svc-lifecycle/<lifecycle_id>/staff-metrics` | Per-lifecycle metrics cho workflow page |

---

## AI Integration

- Model: `claude-haiku-4-5-20251001`, synchronous, fail silent (return `""`)
- Lưu vào `crm_svc_kpi_scans` sau mỗi scan thành công
- Latest scan per staff+month hiển thị trên dashboard

**AI prompt context (AM):**
```
staff_name, role='AM', year, month,
received_revenue, active_services, avg_margin_pct, outstanding,
targets: {received_revenue: X, active_services: X, avg_margin_pct: X}
```
Phân tích: so sánh actual vs target, highlight gap lớn nhất, gợi ý 2-3 hành động cụ thể.

**AI prompt context (SP):**
```
staff_name, role='SP', year, month,
tasks_completed, tasks_pending, risks_resolved,
targets: {tasks_completed: X, risks_resolved: X}
```
Phân tích: tốc độ hoàn thành task, rủi ro tồn đọng, gợi ý ưu tiên.

---

## Templates

### `crm_staff_kpi.html` — `/crm/staff-kpi`

Bố cục:
- Header filter bar: dropdown chọn staff (all active staff), month/year selector
- **AM Section** (hiện nếu staff có assigned_am lifecycles):
  - 4 metric cards: Received Revenue / Active Services / Avg Margin% / Outstanding
  - Mỗi card: actual (lớn) + target (nhỏ, editable inline) + badge màu (xanh=đạt, đỏ=chưa đạt, xám=chưa set target)
  - Nút "AI Phân tích AM" → hiện AI output box
- **SP Section** (hiện nếu staff có assigned_sp lifecycles):
  - 3 metric cards: Tasks Completed / Tasks Pending / Risks Resolved
  - Tương tự AM section
  - Nút "AI Phân tích SP"
- AI output box: latest scan cho staff+month đang chọn

### Staff section trong `crm_service_workflow.html`

Thêm vào cuối, dưới finance section. Bố cục:
- "Nhân sự phụ trách" header
- AM card: avatar-style (tên + badge AM) + 3 số: tasks done, revenue received, margin%
- SP card: tương tự + tasks done, risks resolved
- Nếu chưa assign AM/SP → hiển thị "Chưa phân công"

---

## Testing

`tests/test_crm_svc_kpi.py` — ~20 tests, `unittest.TestCase` + SQLite in-memory:

- `TestEnsureSchema` — 2 tables created, idempotent
- `TestGetAmMetrics` — no data (all zeros), received_revenue tính đúng tháng (exclude other months), avg_margin_pct=0.0 khi no active lifecycles, outstanding sum
- `TestGetSpMetrics` — tasks_completed tính đúng tháng, tasks_pending count, risks_resolved tính đúng tháng
- `TestGetLifecycleStaffMetrics` — no AM/SP returns None, with AM only, with both AM and SP
- `TestTargets` — set_target creates, overwrite updates, get_targets returns only set keys, missing returns {}
- `TestAiKpiScan` — no API key → returns `""`
