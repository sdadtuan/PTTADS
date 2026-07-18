# Design: AI Proposal Generator

**Ngày:** 2026-06-23
**Stack:** Flask 3 + SQLite, Anthropic SDK trực tiếp, window.print() cho PDF
**Nguyên tắc:** YAGNI · Simplicity First · Surgical Changes

---

## Vấn đề

SP tạo báo giá thủ công (Word/Google Docs), mất 30–60 phút mỗi đề xuất, chất lượng không đồng đều. Không có tool nội bộ nào hỗ trợ cá nhân hóa nội dung theo từng khách hàng hay tự động hóa phần phân tích.

---

## Giải pháp (Approach A: Form trước, AI điền nội dung)

SP chọn khách + dịch vụ + nhập giá/timeline vào form ngắn. AI dùng thông tin đó + lịch sử khách (lead notes, contracts cũ, lifecycle stage) để soạn toàn bộ phần text. SP xem preview HTML → sửa tay nếu muốn → Print/Save PDF qua `window.print()`.

**Hai entry point:**
- `/crm/proposals` — standalone workspace, chọn khách + tạo proposal tự do
- Card trong workflow page khi lifecycle ở stage `proposal`

---

## Schema

### `crm_proposals`

```sql
CREATE TABLE IF NOT EXISTS crm_proposals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
    lifecycle_id    INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE SET NULL,
    service_slugs   TEXT NOT NULL DEFAULT '[]',
    total_vnd       INTEGER NOT NULL DEFAULT 0,
    timeline_months INTEGER NOT NULL DEFAULT 1,
    notes           TEXT NOT NULL DEFAULT '',
    ai_output       TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
)
```

Index: `(customer_id)`.

`service_slugs` — JSON array của service slugs, e.g. `'["dich-vu-seo-local","dich-vu-aeo"]'`.

`ai_output` — JSON object với 5 keys: `problem`, `solution`, `usp`, `kpi`, `pricing_narrative`. Default `'{}'` khi chưa generate.

---

## Files

| File | Loại | Mô tả |
|------|------|-------|
| `crm_proposal.py` | Tạo mới | Schema + 7 functions + SERVICE_NAMES dict |
| `tests/test_crm_proposal.py` | Tạo mới | ~12 tests, SQLite in-memory |
| `app.py` | Sửa nhỏ | +import, +schema init, +5 routes, +proposal card trong workflow |
| `templates/crm_proposals.html` | Tạo mới | Workspace: customer selector + create form + proposal list |
| `templates/crm_proposal_preview.html` | Tạo mới | Full-page HTML proposal cho preview + print |
| `templates/crm_service_workflow.html` | Sửa nhỏ | +proposal card khi stage == "proposal" |

---

## Public API `crm_proposal.py`

```python
SERVICE_NAMES: dict[str, str]
# 12 slugs → tên tiếng Việt đẹp. Dùng trong prompt + preview template.
# {
#   "dich-vu-seo-tong-the": "SEO Tổng thể",
#   "dich-vu-seo-local": "SEO Local",
#   "dich-vu-seo-audit": "SEO Audit",
#   "dich-vu-aeo": "AEO (Answer Engine Optimization)",
#   "dich-vu-quan-tri-website": "Quản trị Website",
#   "thiet-ke-website": "Thiết kế Website",
#   "thiet-ke-website-tron-goi": "Thiết kế Website Trọn gói",
#   "thiet-ke-landing-page": "Thiết kế Landing Page",
#   "quang-cao-facebook": "Quảng cáo Facebook",
#   "quang-cao-google": "Quảng cáo Google",
#   "thue-tai-khoan-quang-cao": "Thuê tài khoản Quảng cáo",
#   "tiep-thi-noi-dung": "Tiếp thị Nội dung",
# }

def ensure_schema(conn: sqlite3.Connection) -> None
# Tạo bảng + index. Idempotent.

def create_proposal(
    conn: sqlite3.Connection,
    customer_id: int,
    service_slugs: list[str],
    total_vnd: int,
    timeline_months: int,
    notes: str,
    *,
    lifecycle_id: int | None = None,
) -> int
# INSERT vào crm_proposals. service_slugs lưu dưới dạng json.dumps(list).
# Trả về id.

def list_proposals(conn: sqlite3.Connection, customer_id: int) -> list[dict]
# SELECT ORDER BY id DESC. Mỗi dict có thêm field generated: bool (ai_output != '{}').

def get_proposal(conn: sqlite3.Connection, proposal_id: int) -> dict | None
# SELECT 1 row. service_slugs parsed thành list. ai_output parsed thành dict.

def delete_proposal(conn: sqlite3.Connection, proposal_id: int) -> None
# DELETE WHERE id=?

def get_customer_context(conn: sqlite3.Connection, customer_id: int) -> dict
# Pull và trả về:
# {
#   customer: {name, company, address, phone, email},
#   lead: {product_interest, need} | None,  # lead mới nhất của khách (JOIN crm_leads)
#   contracts: {count: int, total_vnd: int},  # lịch sử hợp đồng của khách
#   past_service_slugs: list[str],  # slugs từ crm_service_lifecycle của khách (tất cả)
#   active_lifecycles: list[str],   # service_slugs đang status='active'
# }

def run_proposal_ai(conn: sqlite3.Connection, proposal_id: int) -> dict
# 1. Fetch proposal + get_customer_context
# 2. Build prompt (xem mục AI Prompt bên dưới)
# 3. Gọi claude-haiku-4-5-20251001, max_tokens=2000
# 4. Parse 5 sections bằng _extract_section()
# 5. UPDATE crm_proposals SET ai_output=json.dumps(sections), updated_at=_ts()
# 6. Return sections dict
# fail silent → {}
```

---

## AI Prompt

```
Bạn là chuyên gia tư vấn marketing digital, viết đề xuất dịch vụ cho khách hàng doanh nghiệp.

Thông tin khách hàng:
- Tên: {customer.name}
- Công ty: {customer.company hoặc 'Cá nhân'}
- Ngành/Nhu cầu: {lead.product_interest} — {lead.need}
- Lịch sử: {contracts.count} hợp đồng trước (tổng {contracts.total_vnd} VNĐ), đã dùng: {SERVICE_NAMES[s] cho s trong past_service_slugs}

Dịch vụ đề xuất lần này: {SERVICE_NAMES[slug] cho mỗi slug trong service_slugs}
Tổng giá trị: {total_vnd:,} VNĐ / {timeline_months} tháng
Ghi chú từ chuyên viên: {notes hoặc 'Không có'}

Viết đề xuất theo đúng 5 header ## sau (không thêm header khác):

## Phân tích vấn đề
[Pain points của khách dựa trên ngành/nhu cầu. 3-5 câu.]

## Giải pháp đề xuất
[Cách các dịch vụ được chọn giải quyết vấn đề. Đề cập tên từng dịch vụ. 4-6 câu.]

## Tại sao chọn PTTCOM
[USP tailored theo context khách: kinh nghiệm, kết quả, sự phù hợp. 3-4 câu.]

## Kết quả kỳ vọng
[KPIs cụ thể theo từng dịch vụ được chọn. Format danh sách bullet. 4-6 items.]

## Tóm tắt báo giá
[Diễn giải mức giá thành văn thuyết phục: tại sao mức giá này xứng đáng với giá trị nhận được. 2-3 câu.]
```

**Model:** `claude-haiku-4-5-20251001` · `max_tokens=2000` · fail silent (return `{}`)

**Parse:** `_extract_section(text, header)` — reuse regex helper từ `crm_aeo.py`.

**Sections dict keys:** `problem`, `solution`, `usp`, `kpi`, `pricing_narrative`.

---

## Routes

| Method | Route | Mô tả |
|--------|-------|-------|
| GET | `/crm/proposals` | Workspace — customer selector + create form + proposal list |
| GET | `/crm/proposals/<int:proposal_id>/preview` | Full-page HTML proposal |
| POST | `/api/crm/proposals` | Body: `{customer_id, service_slugs[], total_vnd, timeline_months, notes, lifecycle_id?}` → `{id}` |
| POST | `/api/crm/proposals/<int:proposal_id>/generate` | Trigger AI → `{problem, solution, usp, kpi, pricing_narrative, updated_at}` |
| DELETE | `/api/crm/proposals/<int:proposal_id>` | → `{}` |

Auth: page routes dùng `_ensure_crm_session_html()`. API routes không cần auth riêng.

---

## Templates

### `crm_proposals.html` — `/crm/proposals`

Bố cục:
- **Customer selector** dropdown (GET param `customer_id`, onchange submit)
- **Create form** (hiện khi đã chọn khách):
  - Checkboxes cho 12 dịch vụ (hiện tên tiếng Việt từ SERVICE_NAMES)
  - Input: Tổng giá trị (VNĐ), Thời hạn (tháng), Ghi chú SP
  - Nút "Tạo Đề xuất" → POST `/api/crm/proposals`
- **Proposal list** (hiện khi đã chọn khách): bảng gồm:
  - Dịch vụ (tên rút gọn), Giá, Thời hạn, Ngày tạo, AI status (badge), Hành động
  - Hành động: [Tạo AI] [Xem / In] [Xoá]
  - Spinner khi đang generate AI
- **Empty state** khi chưa chọn khách / chưa có proposal

### `crm_proposal_preview.html` — `/crm/proposals/<id>/preview`

Full-page HTML tối ưu cho print (A4):

```
┌─────────────────────────────────────────────┐
│  PTTCOM Logo          ĐỀ XUẤT DỊCH VỤ       │
│  Ngày: {created_at}   Mã: PRO-{id:04d}      │
├─────────────────────────────────────────────┤
│  Kính gửi: {customer.name}                   │
│  Công ty: {customer.company}                 │
├─────────────────────────────────────────────┤
│  ## Phân tích vấn đề      [AI text]         │
│  ## Giải pháp đề xuất     [AI text]         │
│  ## Tại sao chọn PTTCOM   [AI text]         │
│  ## Kết quả kỳ vọng       [AI text]         │
├─────────────────────────────────────────────┤
│  BẢNG GIÁ DỊCH VỤ                           │
│  • Dịch vụ 1                                │
│  • Dịch vụ 2                                │
│  Tổng cộng: {total_vnd} VNĐ / {N} tháng    │
│  (Không hiện giá per-service — chỉ total)   │
├─────────────────────────────────────────────┤
│  ## Tóm tắt báo giá      [AI text]          │
├─────────────────────────────────────────────┤
│  Điều khoản: Báo giá có hiệu lực 30 ngày.   │
│  [Nút: In / Tải PDF]  ← ẩn khi print        │
└─────────────────────────────────────────────┘
```

`@media print`: ẩn nav, ẩn nút In, page-break-before cho mỗi `##` section chính, font-size phù hợp A4.

### Workflow page card (sửa `crm_service_workflow.html`)

Thêm card khi `lc["stage"] == "proposal"` (không phụ thuộc vào `aeo_stats`):

```
┌─ Đề xuất Dịch vụ ─────────────────────────┐
│  [→ Tạo / Xem Đề xuất]                     │
│  Link: /crm/proposals?customer_id=X&        │
│         lifecycle_id=Y                      │
└────────────────────────────────────────────┘
```

---

## Testing

`tests/test_crm_proposal.py` — `unittest.TestCase` + SQLite in-memory.

**`_setup_conn()`** tạo: `crm_customers`, `crm_leads`, `crm_contracts`, `crm_service_lifecycle`, gọi `ensure_schema`.

| Class | Tests |
|-------|-------|
| `TestEnsureSchema` | table created, idempotent |
| `TestCreateProposal` | returns int id, lifecycle_id nullable, service_slugs stored |
| `TestListProposals` | empty → `[]`, generated flag False khi ai_output=='{}', True khi có data |
| `TestGetProposal` | returns None khi không có, service_slugs parsed thành list, ai_output parsed thành dict |
| `TestDeleteProposal` | xoá row |
| `TestGetCustomerContext` | no lead → lead=None, với lead → pulls product_interest + need |
| `TestRunProposalAi` | no API key → `{}`, mock → 5 sections saved + returned |

~12 tests tổng.
