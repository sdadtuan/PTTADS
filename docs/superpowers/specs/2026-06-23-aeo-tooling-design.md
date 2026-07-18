# Design: AEO Tooling — Answer Engine Optimization Workspace

**Ngày:** 2026-06-23
**Stack:** Flask 3 + SQLite, Anthropic SDK trực tiếp
**Nguyên tắc:** YAGNI · Simplicity First · Surgical Changes

---

## Vấn đề

PTTCOM cung cấp dịch vụ AEO (`dich-vu-aeo`) nhưng không có tooling nội bộ hỗ trợ. SP làm thủ công: tự hỏi ChatGPT/Perplexity xem brand khách có xuất hiện không, tự ghi chép gap, tự viết Q&A. AM không có cách báo cáo improvement theo thời gian.

---

## Giải pháp (Approach A: Query-centric)

Mỗi khách hàng có một **query bank** gồm 10-20 câu hỏi được track liên tục. SP scan từng query → Claude simulate AI answer + phân tích brand visibility + content gap → SP generate Q&A pairs + FAQ schema JSON-LD. AM theo dõi % queries có brand visible qua từng tháng.

**Hai entry point:**
- `/crm/aeo` — standalone workspace, chọn khách + làm AEO tự do
- Section trong workflow page (chỉ lifecycle có `service_slug="dich-vu-aeo"`)

---

## Schema

### `crm_aeo_queries`

```sql
CREATE TABLE IF NOT EXISTS crm_aeo_queries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
    lifecycle_id INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE SET NULL,
    query_text  TEXT NOT NULL DEFAULT '',
    brand_name  TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT ''
)
```

Index: `(customer_id)`.

### `crm_aeo_scans`

```sql
CREATE TABLE IF NOT EXISTS crm_aeo_scans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id      INTEGER NOT NULL REFERENCES crm_aeo_queries(id) ON DELETE CASCADE,
    ai_response   TEXT NOT NULL DEFAULT '',
    brand_visible INTEGER NOT NULL DEFAULT 0,
    gap_notes     TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT ''
)
```

Index: `(query_id)`.

### `crm_aeo_content`

```sql
CREATE TABLE IF NOT EXISTS crm_aeo_content (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id    INTEGER NOT NULL REFERENCES crm_aeo_queries(id) ON DELETE CASCADE,
    qa_text     TEXT NOT NULL DEFAULT '',
    schema_json TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT ''
)
```

Index: `(query_id)`.

---

## Files

| File | Loại | Mô tả |
|------|------|-------|
| `crm_aeo.py` | Tạo mới | Schema + 8 public functions |
| `tests/test_crm_aeo.py` | Tạo mới | ~14 tests, SQLite in-memory |
| `app.py` | Sửa nhỏ | +import, +schema init, +5 routes |
| `templates/crm_aeo.html` | Tạo mới | AEO Workspace page |
| `templates/crm_service_workflow.html` | Sửa nhỏ | +AEO section cho lifecycle AEO |

---

## Public API `crm_aeo.py`

```python
def ensure_schema(conn: sqlite3.Connection) -> None
# Tạo 3 bảng nếu chưa có. Idempotent.

def add_query(
    conn: sqlite3.Connection,
    customer_id: int,
    query_text: str,
    brand_name: str,
    *,
    lifecycle_id: int | None = None,
    notes: str = "",
) -> int
# INSERT vào crm_aeo_queries, trả về id.

def list_queries(conn: sqlite3.Connection, customer_id: int) -> list[dict]
# Trả về tất cả queries của khách + latest scan result mỗi query.
# Mỗi dict: {id, query_text, brand_name, notes, lifecycle_id, created_at,
#             last_scan_date: str|None, brand_visible: int|None}

def delete_query(conn: sqlite3.Connection, query_id: int) -> None
# DELETE crm_aeo_queries WHERE id=?
# CASCADE xoá scans + content liên quan (foreign key ON DELETE CASCADE)

def run_scan(conn: sqlite3.Connection, query_id: int) -> str
# Lấy query_text + brand_name + notes từ crm_aeo_queries.
# Gọi claude-haiku-4-5-20251001 với scan prompt.
# Parse brand_visible từ response (tìm "brand_visible: yes/no" trong ## Phân tích).
# Lưu vào crm_aeo_scans (ai_response, brand_visible, gap_notes).
# fail silent → ""

def get_scan_history(conn: sqlite3.Connection, query_id: int) -> list[dict]
# SELECT * FROM crm_aeo_scans WHERE query_id=? ORDER BY id DESC
# Mỗi dict: {id, ai_response, brand_visible, gap_notes, created_at}

def generate_content(conn: sqlite3.Connection, query_id: int) -> dict
# Lấy gap_notes từ scan mới nhất của query.
# Gọi claude-haiku-4-5-20251001 với content prompt.
# Lưu kết quả vào crm_aeo_content (qa_text, schema_json).
# fail silent → {}

def get_latest_content(conn: sqlite3.Connection, query_id: int) -> dict | None
# SELECT * FROM crm_aeo_content WHERE query_id=? ORDER BY id DESC LIMIT 1
# Returns: {id, qa_text, schema_json, created_at} | None
```

---

## AI Prompts

### Scan prompt (`run_scan`)

```
Bạn là chuyên gia AEO phân tích cách AI engine trả lời câu hỏi.

Query: "{query_text}"
Brand cần monitor: "{brand_name}"
Thông tin brand: "{notes hoặc 'Không có thêm thông tin'}"

Hãy thực hiện 3 bước sau, dùng đúng header ##:

## Câu trả lời AI điển hình
[Viết câu trả lời mà ChatGPT hoặc Perplexity thường trả lời cho query này, dựa trên kiến thức phổ biến. 3-5 câu.]

## Phân tích Brand Visibility
brand_visible: [yes/no]
[Giải thích: {brand_name} có xuất hiện trong câu trả lời trên không, và tại sao. 2-3 câu.]

## Content Gap
[Liệt kê 2-3 loại nội dung/tín hiệu mà {brand_name} đang thiếu để AI engine đề cập đến khi trả lời query này.]
```

**Model:** `claude-haiku-4-5-20251001` · `max_tokens=1000` · fail silent (return `""`)

**Parse `brand_visible`:** tìm dòng `brand_visible: yes` (case-insensitive) trong response → `1`, ngược lại `0`.

**Parse `gap_notes`:** extract text sau `## Content Gap` header.

### Content prompt (`generate_content`)

```
Bạn là chuyên gia viết content AEO.

Query: "{query_text}"
Brand: "{brand_name}"
Content gap cần fill: "{gap_notes}"

Hãy tạo:

## Q&A Pairs
[3-5 cặp câu hỏi – câu trả lời, mỗi cặp giúp {brand_name} xuất hiện khi AI engine trả lời câu hỏi liên quan. Format:
Q: [câu hỏi]
A: [câu trả lời 2-3 câu, tự nhiên, có đề cập {brand_name}]]

## FAQ Schema JSON-LD
[JSON-LD hợp lệ dùng schema.org/FAQPage, bao gồm tất cả Q&A pairs ở trên. Chỉ trả về JSON thuần, không thêm markdown code block.]
```

**Model:** `claude-haiku-4-5-20251001` · `max_tokens=1200` · fail silent (return `{}`)

**Parse `qa_text`:** extract text sau `## Q&A Pairs` header, lưu raw (Q:/A: markdown format).

**Parse `schema_json`:** extract JSON sau `## FAQ Schema JSON-LD`.

---

## Routes

| Method | Route | Mô tả |
|--------|-------|-------|
| GET | `/crm/aeo` | AEO Workspace — customer selector + query bank |
| POST | `/api/crm/aeo/queries` | Body: `{customer_id, query_text, brand_name, lifecycle_id?, notes?}` → `{id}` |
| DELETE | `/api/crm/aeo/queries/<int:query_id>` | Xoá query → `{}` |
| POST | `/api/crm/aeo/queries/<int:query_id>/scan` | Trigger AI scan → `{ai_response, brand_visible, gap_notes, created_at}` |
| POST | `/api/crm/aeo/queries/<int:query_id>/content` | Trigger content gen → `{qa_text, schema_json, created_at}` |

Auth: page route dùng `_ensure_crm_session_html()`. API routes không cần auth check riêng.

---

## Templates

### `crm_aeo.html` — `/crm/aeo`

Bố cục:
- **Header bar:** dropdown chọn khách hàng (GET param `customer_id`, `onchange="this.form.submit()"`) — brand name được nhập per-query, không cần header input riêng
- **Query Bank section** (hiện sau khi chọn khách):
  - Nút "+ Thêm câu hỏi" → inline form: `[query_text input] [brand_name input] [notes input] [Thêm]`
  - Danh sách queries dạng bảng:

| Câu hỏi | Brand | Lần scan | Visibility | Hành động |
|---------|-------|----------|-----------|-----------|
| "SEO local giá?" | PTTCOM | 2026-06-01 | ✓ Có | [Scan lại] [Kết quả] [Content] [Xoá] |
| "agency uy tín?" | PTTCOM | Chưa scan | — | [Scan] [Content] [Xoá] |

  - Click **[Kết quả]** → slide-down row hiện 3 section từ `ai_response` (parse `## ` headers)
  - Click **[Content]** → slide-down row hiện Q&A pairs + schema JSON-LD + nút "Copy Schema"
  - Spinner khi đang scan/generating

- **Scan summary bar** (bottom of list): `X/Y queries có brand visible` — dành cho AM

### AEO section trong `crm_service_workflow.html`

Chỉ hiện nếu `lc["service_slug"] == "dich-vu-aeo"`. Bố cục:

```
┌─ AEO Monitoring ──────────────────────────────────┐
│  Queries đang track: {N}   Brand visible: {X}/{N}  │
│  [→ Mở AEO Workspace]                              │
└───────────────────────────────────────────────────┘
```

Link "Mở AEO Workspace" → `/crm/aeo?customer_id={customer_id}`.

---

## Testing

`tests/test_crm_aeo.py` — `unittest.TestCase` + SQLite in-memory.

**`_setup_conn()`** tạo: `crm_customers`, `crm_service_lifecycle`, gọi `ensure_schema`.

| Class | Tests |
|-------|-------|
| `TestEnsureSchema` | 3 tables created, idempotent |
| `TestAddQuery` | tạo row, lifecycle_id nullable, trả về int id |
| `TestListQueries` | empty → `[]`, last_scan_date + brand_visible từ latest scan |
| `TestDeleteQuery` | xoá query (cascade kiểm tra qua count scans/content) |
| `TestRunScan` | no API key → `""`, mock: saves ai_response + brand_visible parsed, gap_notes saved |
| `TestGetScanHistory` | no scans → `[]`, ORDER BY id DESC |
| `TestGenerateContent` | no API key → `{}`, mock: saves qa_text + schema_json |
| `TestGetLatestContent` | no content → `None`, returns latest by id DESC |

~14 tests tổng.
