# Design: Profit & Cost Tracking — Phase 3

**Ngày:** 2026-06-23
**Stack:** Flask 3 + SQLite, Anthropic SDK trực tiếp
**Nguyên tắc:** YAGNI · Simplicity First · Surgical Changes

---

## Vấn đề

Trang workflow `/crm/service-delivery/<id>` chưa có thông tin tài chính. AM không có nơi để:
- Xem doanh thu kỳ vọng vs thực nhận
- Track từng khoản chi phí phát sinh
- Xem lợi nhuận và margin thực tế
- Nhận cảnh báo AI về tình trạng tài chính

## Giải pháp (Approach A đã chọn)

**Hai bảng riêng biệt** (`crm_svc_payments` + `crm_svc_expenses`) trong một module `crm_svc_finance.py`.
Revenue tổng hợp từ `crm_contracts.amount_vnd` (kỳ vọng) + sum payments received (thực nhận).
AI hai chế độ: health check + burn rate forecast.

---

## Schema

### `crm_svc_payments`

```sql
CREATE TABLE IF NOT EXISTS crm_svc_payments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
    amount_vnd   INTEGER NOT NULL DEFAULT 0,
    received_on  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'received', 'cancelled'
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT ''
)
```

### `crm_svc_expenses`

```sql
CREATE TABLE IF NOT EXISTS crm_svc_expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
    title        TEXT NOT NULL DEFAULT '',
    category     TEXT NOT NULL DEFAULT 'khac',  -- 'nhan-cong', 'cong-cu', 'quang-cao', 'outsource', 'khac'
    amount_vnd   INTEGER NOT NULL DEFAULT 0,
    expense_on   TEXT NOT NULL DEFAULT '',
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT ''
)
```

### `crm_svc_finance_scans`

```sql
CREATE TABLE IF NOT EXISTS crm_svc_finance_scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
    ai_output    TEXT NOT NULL DEFAULT '',
    scan_type    TEXT NOT NULL DEFAULT 'health',  -- 'health', 'forecast'
    created_at   TEXT NOT NULL DEFAULT ''
)
```

---

## Files

| File | Loại | Mô tả |
|------|------|-------|
| `crm_svc_finance.py` | Tạo mới | Schema + 11 public functions |
| `tests/test_crm_svc_finance.py` | Tạo mới | TDD — ~25 tests |
| `app.py` | Sửa nhỏ | +import, +init schema, +9 routes, update `crm_service_workflow_page` |
| `templates/crm_service_workflow.html` | Sửa nhỏ | +finance section (dưới risk section) |
| `templates/crm_financials.html` | Tạo mới | Trang tổng hợp toàn bộ lifecycles |

---

## Public API `crm_svc_finance.py`

```python
def ensure_schema(conn: sqlite3.Connection) -> None

def get_summary(conn, lifecycle_id: int, contract_amount_vnd: int) -> dict
# contract_amount_vnd: caller truyền vào từ crm_contracts.amount_vnd (nếu lifecycle.contract_id
# là NULL thì truyền 0). Route tự join để lấy giá trị này.
# Returns:
# {
#   expected_revenue: int,   # = contract_amount_vnd
#   received_revenue: int,   # sum(amount_vnd WHERE status='received')
#   pending_revenue: int,    # sum(amount_vnd WHERE status='pending')
#   total_expenses: int,     # sum(amount_vnd) all expenses
#   profit: int,             # received_revenue - total_expenses
#   margin_pct: float,       # profit / received_revenue * 100 (0.0 if received=0)
#   outstanding: int,        # expected_revenue - received_revenue
# }

def list_payments(conn, lifecycle_id: int) -> list[dict]
# ORDER BY received_on DESC, id DESC

def create_payment(conn, lifecycle_id: int, amount_vnd: int, received_on: str,
                   status: str = 'pending', notes: str = '') -> int  # returns payment_id

def update_payment(conn, payment_id: int, *, amount_vnd: int | None = None,
                   received_on: str | None = None, status: str | None = None,
                   notes: str | None = None) -> None

def delete_payment(conn, payment_id: int) -> bool  # True if deleted, False if not found

def list_expenses(conn, lifecycle_id: int) -> list[dict]
# ORDER BY expense_on DESC, id DESC

def create_expense(conn, lifecycle_id: int, title: str, category: str,
                   amount_vnd: int, expense_on: str, notes: str = '') -> int

def update_expense(conn, expense_id: int, *, title: str | None = None,
                   category: str | None = None, amount_vnd: int | None = None,
                   expense_on: str | None = None, notes: str | None = None) -> None

def delete_expense(conn, expense_id: int) -> bool

def run_ai_finance_scan(conn, lifecycle_id: int, scan_type: str,
                        context: dict) -> str  # fail silent → ""
# scan_type: 'health' | 'forecast'
# context keys: service_name, customer_name, contract_amount_vnd, received_revenue,
#               total_expenses, profit, margin_pct, days_elapsed, contract_days
```

---

## Routes

| Method | Route | Mô tả |
|--------|-------|--------|
| GET | `/crm/financials` | Trang tổng hợp toàn bộ lifecycles, sort by margin_pct |
| GET | `/api/crm/svc-finance/<lifecycle_id>/summary` | Summary dict cho 1 lifecycle |
| POST | `/api/crm/svc-payments` | Tạo payment mới |
| PATCH | `/api/crm/svc-payments/<payment_id>` | Cập nhật payment |
| DELETE | `/api/crm/svc-payments/<payment_id>` | Xoá payment |
| POST | `/api/crm/svc-expenses` | Tạo expense mới |
| PATCH | `/api/crm/svc-expenses/<expense_id>` | Cập nhật expense |
| DELETE | `/api/crm/svc-expenses/<expense_id>` | Xoá expense |
| POST | `/api/crm/svc-finance/<lifecycle_id>/ai-scan` | AI scan (body: `{"scan_type": "health"\|"forecast"}`) |

---

## AI Integration

- Model: `claude-haiku-4-5-20251001`, synchronous, fail silent (return `""`)
- Lưu kết quả vào `crm_svc_finance_scans` sau mỗi scan thành công
- Trang hiển thị latest scan per type (health + forecast riêng biệt)

**`health` prompt context:**
```
service_name, customer_name, contract_amount_vnd, received_revenue,
total_expenses, profit, margin_pct
```
Phân tích: margin có ổn không, expenses có vượt 70% received không, gợi ý cụ thể.

**`forecast` prompt context:**
```
tất cả fields của health + days_elapsed (số ngày đã triển khai), contract_days (tổng thời gian HĐ)
```
Tính burn rate = total_expenses / days_elapsed, chiếu đến cuối HĐ → ước tính total cost và profit cuối kỳ.

---

## Templates

### Finance section trong `crm_service_workflow.html`
Thêm vào cuối, dưới risk section. Bố cục:
- Summary row: 4 metric boxes (Expected / Received / Expenses / Profit+margin%)
- Payments table: date, amount, status badge (pending=vàng, received=xanh, cancelled=xám), notes, edit/delete buttons
- Expenses table: date, title, category badge, amount, notes, edit/delete buttons
- Add forms (inline collapsible `<details>`) cho payment + expense
- AI section: 2 nút (Health Check + Forecast), latest scan output per type

### `crm_financials.html`
Trang mới `/crm/financials`. Bố cục:
- Table tất cả active lifecycles với: KH, Dịch vụ, Stage, Expected, Received, Expenses, Profit, Margin%
- Sort mặc định: margin_pct tăng dần (rủi ro cao lên đầu)
- Badge màu margin: đỏ (<20%), vàng (20-50%), xanh (>50%)

---

## Testing

`tests/test_crm_svc_finance.py` — ~25 tests, `unittest.TestCase` + SQLite in-memory:

- `TestEnsureSchema` — 3 tables created, idempotent
- `TestGetSummary` — no data (all zeros), received vs pending vs cancelled, division-by-zero guard khi received=0, margin_pct calculation
- `TestPayments` — create, list order, update (amount/status/notes), delete (True/False)
- `TestExpenses` — create, list order, update (title/category/amount/date), delete (True/False)
- `TestAiFinanceScan` — no API key → returns `""`
