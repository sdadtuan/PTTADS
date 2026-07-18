# Design: Customer 360 Meeting Brief — Gap 1

**Ngày:** 2026-06-23
**Stack:** Flask 3 + SQLite, Anthropic SDK trực tiếp
**Nguyên tắc:** YAGNI · Simplicity First · Surgical Changes

---

## Vấn đề

AM chuẩn bị gặp khách phải mở nhiều tab: lifecycle, finance, risk, tasks, contracts — mất 5-10 phút và dễ bỏ sót. Không có "single source of truth" trước cuộc họp.

---

## Giải pháp

AI tổng hợp toàn bộ data khách hàng thành **Meeting Brief** trong 1 click. AM nhập mục đích họp (optional) → AI tạo brief có trọng tâm: tóm tắt + điểm chú ý + câu hỏi gợi ý.

**Hai entry point:**
- Quick panel (slide-out drawer) từ danh sách khách → check nhanh
- Full-page `/crm/customer/<id>/meeting-brief` → chuẩn bị kỹ, có thể in

---

## Schema

### `crm_customer_brief_scans`

```sql
CREATE TABLE IF NOT EXISTS crm_customer_brief_scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
    meeting_purpose TEXT NOT NULL DEFAULT '',
    ai_output       TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT ''
)
```

Index: `(customer_id)` — ORDER BY id DESC để lấy latest.

---

## Files

| File | Loại | Mô tả |
|------|------|-------|
| `crm_customer_brief.py` | Tạo mới | Schema + 3 functions |
| `tests/test_crm_customer_brief.py` | Tạo mới | TDD — ~12 tests |
| `app.py` | Sửa nhỏ | +import, +schema init, +3 routes, update customers page route |
| `templates/crm_customer_meeting_brief.html` | Tạo mới | Full-page brief |
| `templates/crm_customers.html` | Sửa nhỏ | +quick panel drawer + brief button per row |

---

## Public API `crm_customer_brief.py`

```python
def ensure_schema(conn: sqlite3.Connection) -> None
# Tạo crm_customer_brief_scans nếu chưa có. Idempotent.

def get_customer_snapshot(conn: sqlite3.Connection, customer_id: int) -> dict
# Pull data từ 7 nguồn, trả về dict có cấu trúc cho AI prompt.
# Returns:
# {
#   customer: {id, name, industry, lead_source, created_at, months_as_customer},
#   contracts: [{id, amount_vnd, status}],          # tất cả contracts
#   total_contract_vnd: int,                         # sum amount_vnd
#   active_lifecycles: [
#     {
#       id, service_slug, service_label, stage,
#       am_name, sp_name,
#       margin_pct: float,       # từ crm_svc_payments/expenses
#       outstanding: int,        # contract_amount - received
#       last_payment_date: str,  # received_on gần nhất
#       active_risks: int,       # COUNT(crm_svc_risks WHERE is_active=1)
#       pending_tasks: int,      # COUNT(crm_svc_tasks WHERE is_done=0)
#     }
#   ],
#   open_issues: int,            # COUNT(fetch_customer_issues WHERE status open)
# }

def run_brief_ai(
    conn: sqlite3.Connection,
    customer_id: int,
    meeting_purpose: str,        # "" nếu không nhập
    snapshot: dict,
) -> str
# Gọi claude-haiku-4-5-20251001 với prompt từ snapshot + meeting_purpose.
# Lưu kết quả vào crm_customer_brief_scans.
# fail silent → ""

def get_latest_brief(conn: sqlite3.Connection, customer_id: int) -> dict | None
# Returns: {id, meeting_purpose, ai_output, created_at} | None
```

---

## AI Prompt

```
Bạn là chuyên gia tư vấn chiến lược khách hàng B2B.

Mục đích cuộc họp: {meeting_purpose hoặc "Không xác định — tạo brief tổng quát"}

=== DATA KHÁCH HÀNG ===
Tên: {name} | Ngành: {industry} | Gắn bó: {months} tháng
Tổng giá trị hợp đồng: {total_contract_vnd:,} VND

Dịch vụ đang triển khai:
{mỗi lifecycle: "- {service_label}: stage={stage}, margin={margin_pct:.1f}%, công nợ={outstanding:,} VND, AM={am_name}, SP={sp_name}, risks active={active_risks}, tasks chưa xong={pending_tasks}"}

Issues/khiếu nại đang mở: {open_issues}

=== YÊU CẦU ===
Tạo Meeting Brief ngắn gọn với đúng 3 phần sau (dùng header ##):

## Tóm tắt khách hàng
[3-4 dòng: profile, thời gian gắn bó, dịch vụ đang dùng, tổng giá trị]

## Điểm cần chú ý
[Tối đa 3 bullet, mỗi bullet 1 vấn đề nổi bật nhất dựa trên data: margin thấp, risk active, task trễ, công nợ cao, khiếu nại mở]

## Câu hỏi gợi ý
[3-4 câu AM nên hỏi khách trong buổi họp này, phù hợp với mục đích và tình trạng thực tế]
```

**Model:** `claude-haiku-4-5-20251001` · `max_tokens=800` · synchronous · fail silent (return `""`)

---

## Routes

| Method | Route | Mô tả |
|--------|-------|-------|
| GET | `/crm/customer/<int:customer_id>/meeting-brief` | Full-page, render `crm_customer_meeting_brief.html` |
| POST | `/api/crm/customers/<int:customer_id>/brief/generate` | Body: `{meeting_purpose?: str}` → tạo brief, return `{ai_output, created_at}` |
| GET | `/api/crm/customers/<int:customer_id>/brief/latest` | Return brief gần nhất `{meeting_purpose, ai_output, created_at}` hoặc `{}` |

Auth: page route dùng `_ensure_crm_session_html()` (khớp với customers page hiện tại); API routes không cần auth check riêng (dùng chung session).

---

## Templates

### `crm_customer_meeting_brief.html` (full-page)

Bố cục:
- Header: tên khách + badge ngành + link "← Danh sách khách"
- **Input box:** textarea "Mục đích cuộc họp hôm nay" (optional, placeholder: *"VD: upsell SEO Local, giải quyết khiếu nại tiến độ, review tháng..."*)
- **Button:** "Tạo Brief" (spinner khi đang tạo)
- **3 card output** (hiện sau khi tạo hoặc nếu đã có brief cũ):
  - Card 1: Tóm tắt khách hàng (xanh dương nhạt)
  - Card 2: Điểm cần chú ý (vàng nhạt)
  - Card 3: Câu hỏi gợi ý (xanh lá nhạt)
- **Footer:** "Brief tạo lúc: {created_at}" + nút Print (`window.print()`)

JS: `generateBrief()` → POST generate → render 3 cards từ ai_output (parse `## header`)

### Cập nhật `crm_customers.html`

Thêm vào mỗi customer row:
- Icon button `📋` → trigger `openBriefPanel(customerId, customerName)`
- **Slide-out drawer** (position fixed, right side):
  - Header: tên khách + X close
  - Nội dung: brief gần nhất (gọi `/api/.../brief/latest`)
  - Nếu chưa có: "Chưa có brief" + nút "Tạo ngay"
  - Nút "Tạo lại" + link "Xem đầy đủ →" (`/crm/customer/<id>/meeting-brief`)

---

## Testing

`tests/test_crm_customer_brief.py` — `unittest.TestCase` + SQLite in-memory

**`_setup_conn()`** tạo: `crm_customers`, `crm_contracts`, `crm_service_lifecycle`, `crm_svc_payments`, `crm_svc_expenses`, `crm_svc_risks`, `crm_svc_tasks`, `crm_customer_purchases` (stub), gọi `ensure_schema`.

| Class | Tests |
|-------|-------|
| `TestEnsureSchema` | tables created, idempotent |
| `TestGetCustomerSnapshot` | no data → zeros, months_as_customer tính đúng, active_lifecycles populated, margin/outstanding đúng, pending_tasks count, active_risks count |
| `TestGetLatestBrief` | no brief → None, returns latest by id DESC |
| `TestRunBriefAi` | no API key → `""`, saves to scans on success (mock) |

~12 tests tổng.
