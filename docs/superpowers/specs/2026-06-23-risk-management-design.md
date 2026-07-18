# Design: Risk Management — Phase 2

**Ngày:** 2026-06-23
**Stack:** Flask 3 + SQLite, Anthropic SDK trực tiếp
**Nguyên tắc:** YAGNI · Simplicity First · Surgical Changes

---

## Vấn đề

Trang workflow `/crm/service-delivery/<id>` chưa có risk tracking. AM không có nơi để:
- Xem danh sách rủi ro phổ biến của từng dịch vụ
- Đánh dấu rủi ro đã được xử lý
- Nhận cảnh báo AI về rủi ro đang hoạt động

## Giải pháp (Approach C đã chọn)

**Fixed risk list** — seed từ registry per service_slug, AM có thể thêm/xoá custom.
**AI dynamic alerts** — nút "Scan AI" phân tích lifecycle hiện tại và liệt kê TOP 3 rủi ro cấp bách.

---

## Schema

### `crm_svc_risks`

```sql
CREATE TABLE IF NOT EXISTS crm_svc_risks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
    stage        TEXT NOT NULL DEFAULT '',
    title        TEXT NOT NULL DEFAULT '',
    category     TEXT NOT NULL DEFAULT '',
    probability  TEXT NOT NULL DEFAULT 'trung',  -- 'cao', 'trung', 'thap'
    impact       TEXT NOT NULL DEFAULT 'trung',  -- 'cao', 'trung', 'thap'
    mitigation   TEXT NOT NULL DEFAULT '',
    is_active    INTEGER NOT NULL DEFAULT 1,
    is_custom    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT ''
)
```

### `crm_svc_risk_scans`

```sql
CREATE TABLE IF NOT EXISTS crm_svc_risk_scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
    ai_output    TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT ''
)
```

---

## Files

| File | Loại | Mô tả |
|------|------|-------|
| `crm_svc_risk_registry.py` | Tạo mới | Data-only: SERVICE_RISK_REGISTRY + AI_RISK_SCAN_PROMPT |
| `crm_svc_risk.py` | Tạo mới | Schema + 7 public functions |
| `tests/test_crm_svc_risk.py` | Tạo mới | TDD — ~20 tests |
| `app.py` | Sửa nhỏ | +import, +init schema, +5 routes, cập nhật crm_service_workflow_page |
| `templates/crm_service_workflow.html` | Sửa nhỏ | +risk section cuối trang |

---

## Public API `crm_svc_risk.py`

```python
def ensure_schema(conn) -> None
def seed_risks(conn, lifecycle_id: int, service_slug: str) -> int
def list_risks(conn, lifecycle_id: int) -> list[dict]
def update_risk(conn, risk_id: int, *, probability=None, impact=None, mitigation=None, is_active=None) -> None
def create_custom_risk(conn, lifecycle_id: int, stage: str, title: str, category: str = "") -> int
def delete_risk(conn, risk_id: int) -> bool
def get_latest_scan(conn, lifecycle_id: int) -> str
def run_ai_risk_scan(conn, lifecycle_id: int, customer_context: dict) -> str
```

---

## Routes

| Method | Route | Mô tả |
|--------|-------|-------|
| GET | `/api/crm/svc-risks/<lifecycle_id>` | List risks + latest scan |
| PATCH | `/api/crm/svc-risks/<risk_id>` | Update probability/impact/mitigation/is_active |
| POST | `/api/crm/svc-risks` | Create custom risk |
| DELETE | `/api/crm/svc-risks/<risk_id>` | Delete custom risk |
| POST | `/api/crm/svc-risks/<lifecycle_id>/ai-scan` | AI scan + save result |

---

## AI Integration

- Model: `claude-haiku-4-5-20251001`, synchronous, fail silent
- Input: danh sách active risks + current_stage + customer_name
- Output: TOP 3 rủi ro cấp bách với lý do ngắn (1-2 câu mỗi)
- Lưu vào `crm_svc_risk_scans`, hiển thị latest scan trên trang
