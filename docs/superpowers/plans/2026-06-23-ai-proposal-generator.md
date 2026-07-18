# AI Proposal Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây AI Proposal Generator cho PTTP CRM — SP nhập form ngắn (dịch vụ + giá + timeline), Claude soạn toàn bộ nội dung đề xuất, xem preview HTML + in/export PDF qua `window.print()`.

**Architecture:** Module `crm_proposal.py` với 1 bảng `crm_proposals`. Flask routes wired vào `app.py`. Workspace tại `/crm/proposals`. Preview/print tại `/crm/proposals/<id>/preview`. Card trong workflow page khi lifecycle ở stage `proposal`.

**Tech Stack:** Python 3, Flask 3, SQLite (`get_connection()`), Anthropic SDK trực tiếp (`claude-haiku-4-5-20251001`), `window.print()` cho PDF.

## Global Constraints

- `from __future__ import annotations` ở đầu mỗi file Python mới.
- Inline imports bên trong route functions (pattern của app.py).
- Auth: page routes dùng `_ensure_crm_session_html()`. API routes không cần auth riêng.
- AI model: `claude-haiku-4-5-20251001`, synchronous, fail silent (`run_proposal_ai` → `{}`).
- `_ts()` = `datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")`.
- `_extract_section(text, header)`: regex helper — định nghĩa lại trong crm_proposal.py (không import từ crm_aeo.py).
- `service_slugs` lưu dưới dạng `json.dumps(list)` trong DB, parse lại khi đọc.
- `ai_output` lưu dưới dạng `json.dumps(dict)` trong DB, parse lại khi đọc.
- Không có git — không commit. Verify: `python3 -c "import app; print('OK')"`, tests: `python3 -m pytest`.
- `brand_visible` không liên quan — đây là proposal generator, không phải AEO.
- `crm_leads` có cột `converted_customer_id INTEGER REFERENCES crm_customers(id)` — dùng để join lead → customer.

## File Map

| File | Loại | Nhiệm vụ |
|------|------|---------|
| `crm_proposal.py` | Tạo mới | Schema + SERVICE_NAMES + 7 functions |
| `tests/test_crm_proposal.py` | Tạo mới | ~12 tests TDD, SQLite in-memory |
| `app.py` | Sửa nhỏ (3 điểm) | +import dòng 338, +schema init dòng 2284, +5 routes sau api_crm_aeo_content |
| `templates/crm_proposals.html` | Tạo mới | Workspace: selector + create form + proposal list |
| `templates/crm_proposal_preview.html` | Tạo mới | Full-page preview + @media print |
| `templates/crm_service_workflow.html` | Sửa nhỏ | +proposal card khi stage == "proposal" |

---

### Task 1: `crm_proposal.py` + TDD tests

**Files:**
- Create: `crm_proposal.py`
- Create: `tests/test_crm_proposal.py`

**Interfaces — Produces:**
- `SERVICE_NAMES: dict[str, str]` — 12 slug → tên tiếng Việt
- `ensure_schema(conn: sqlite3.Connection) -> None`
- `create_proposal(conn, customer_id: int, service_slugs: list[str], total_vnd: int, timeline_months: int, notes: str, *, lifecycle_id: int | None = None) -> int`
- `list_proposals(conn, customer_id: int) -> list[dict]` — mỗi dict có field `generated: bool`
- `get_proposal(conn, proposal_id: int) -> dict | None` — service_slugs là list, ai_output là dict
- `delete_proposal(conn, proposal_id: int) -> None`
- `get_customer_context(conn, customer_id: int) -> dict`
- `run_proposal_ai(conn, proposal_id: int) -> dict` — fail silent → `{}`

- [ ] **Step 1: Tạo test file với failing tests**

```python
# tests/test_crm_proposal.py
from __future__ import annotations
import json
import sqlite3
import unittest
from unittest.mock import MagicMock, patch
import crm_proposal as m


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            company TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL DEFAULT '',
            product_interest TEXT NOT NULL DEFAULT '',
            need TEXT NOT NULL DEFAULT '',
            converted_customer_id INTEGER
        );
        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft'
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_slug TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            stage TEXT NOT NULL DEFAULT 'lead'
        );
    """)
    m.ensure_schema(conn)
    return conn


def _seed_customer(conn: sqlite3.Connection, name: str = "Test KH", company: str = "Test Co") -> int:
    conn.execute("INSERT INTO crm_customers (name, company) VALUES (?, ?)", (name, company))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestEnsureSchema(unittest.TestCase):
    def test_table_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_proposals", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        m.ensure_schema(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crm_proposals").fetchone()[0], 0)


class TestCreateProposal(unittest.TestCase):
    def test_returns_int_id(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-seo-local"], 5000000, 3, "")
        self.assertIsInstance(pid, int)
        self.assertGreater(pid, 0)

    def test_lifecycle_id_nullable(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-aeo"], 1000000, 1, "", lifecycle_id=None)
        row = conn.execute("SELECT lifecycle_id FROM crm_proposals WHERE id = ?", (pid,)).fetchone()
        self.assertIsNone(row["lifecycle_id"])

    def test_service_slugs_stored_as_json(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        slugs = ["dich-vu-seo-local", "dich-vu-aeo"]
        pid = m.create_proposal(conn, cid, slugs, 5000000, 3, "")
        row = conn.execute("SELECT service_slugs FROM crm_proposals WHERE id = ?", (pid,)).fetchone()
        self.assertEqual(json.loads(row["service_slugs"]), slugs)


class TestListProposals(unittest.TestCase):
    def test_empty_returns_empty_list(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        self.assertEqual(m.list_proposals(conn, cid), [])

    def test_generated_flag_false_by_default(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        m.create_proposal(conn, cid, ["dich-vu-aeo"], 1000000, 1, "")
        rows = m.list_proposals(conn, cid)
        self.assertFalse(rows[0]["generated"])

    def test_generated_flag_true_when_ai_output_set(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-aeo"], 1000000, 1, "")
        conn.execute(
            "UPDATE crm_proposals SET ai_output = ? WHERE id = ?",
            ('{"problem":"x","solution":"y","usp":"z","kpi":"k","pricing_narrative":"p"}', pid),
        )
        conn.commit()
        rows = m.list_proposals(conn, cid)
        self.assertTrue(rows[0]["generated"])


class TestGetProposal(unittest.TestCase):
    def test_returns_none_when_not_found(self):
        conn = _setup_conn()
        self.assertIsNone(m.get_proposal(conn, 999))

    def test_parses_service_slugs_and_ai_output(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-seo-local"], 5000000, 3, "")
        p = m.get_proposal(conn, pid)
        self.assertIsNotNone(p)
        self.assertIsInstance(p["service_slugs"], list)
        self.assertIsInstance(p["ai_output"], dict)


class TestDeleteProposal(unittest.TestCase):
    def test_deletes_row(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-aeo"], 1000000, 1, "")
        m.delete_proposal(conn, pid)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM crm_proposals WHERE id = ?", (pid,)).fetchone()[0],
            0,
        )


class TestGetCustomerContext(unittest.TestCase):
    def test_no_lead_returns_none_lead(self):
        conn = _setup_conn()
        cid = _seed_customer(conn, "Test KH", "Test Co")
        ctx = m.get_customer_context(conn, cid)
        self.assertIsNone(ctx["lead"])
        self.assertEqual(ctx["customer"]["name"], "Test KH")

    def test_with_lead_pulls_product_interest(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        conn.execute(
            "INSERT INTO crm_leads (full_name, product_interest, need, converted_customer_id) VALUES (?,?,?,?)",
            ("Test KH", "SEO Local", "Tăng traffic", cid),
        )
        conn.commit()
        ctx = m.get_customer_context(conn, cid)
        self.assertIsNotNone(ctx["lead"])
        self.assertEqual(ctx["lead"]["product_interest"], "SEO Local")
        self.assertEqual(ctx["lead"]["need"], "Tăng traffic")


class TestRunProposalAi(unittest.TestCase):
    def test_no_api_key_returns_empty_dict(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-seo-local"], 5000000, 3, "")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = Exception("no key")
            result = m.run_proposal_ai(conn, pid)
        self.assertEqual(result, {})

    def test_mock_saves_and_returns_five_sections(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        pid = m.create_proposal(conn, cid, ["dich-vu-seo-local"], 5000000, 3, "")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=(
            "## Phân tích vấn đề\nKhách cần SEO.\n"
            "## Giải pháp đề xuất\nSEO Local giải quyết vấn đề.\n"
            "## Tại sao chọn PTTCOM\nKinh nghiệm 5 năm.\n"
            "## Kết quả kỳ vọng\n- Traffic tăng 50%\n- Top 3 Google\n"
            "## Tóm tắt báo giá\nGiá trị xứng đáng với đầu tư."
        ))]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = m.run_proposal_ai(conn, pid)
        self.assertIn("problem", result)
        self.assertIn("solution", result)
        self.assertIn("usp", result)
        self.assertIn("kpi", result)
        self.assertIn("pricing_narrative", result)
        row = conn.execute("SELECT ai_output FROM crm_proposals WHERE id = ?", (pid,)).fetchone()
        saved = json.loads(row["ai_output"])
        self.assertIn("problem", saved)
        self.assertNotEqual(saved["problem"], "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

```bash
python3 -m pytest tests/test_crm_proposal.py -v
```
Expected: `ModuleNotFoundError: No module named 'crm_proposal'`

- [ ] **Step 3: Tạo `crm_proposal.py`**

```python
# crm_proposal.py
from __future__ import annotations
import json
import re
import sqlite3
from datetime import datetime


SERVICE_NAMES: dict[str, str] = {
    "dich-vu-seo-tong-the": "SEO Tổng thể",
    "dich-vu-seo-local": "SEO Local",
    "dich-vu-seo-audit": "SEO Audit",
    "dich-vu-aeo": "AEO (Answer Engine Optimization)",
    "dich-vu-quan-tri-website": "Quản trị Website",
    "thiet-ke-website": "Thiết kế Website",
    "thiet-ke-website-tron-goi": "Thiết kế Website Trọn gói",
    "thiet-ke-landing-page": "Thiết kế Landing Page",
    "quang-cao-facebook": "Quảng cáo Facebook",
    "quang-cao-google": "Quảng cáo Google",
    "thue-tai-khoan-quang-cao": "Thuê tài khoản Quảng cáo",
    "tiep-thi-noi-dung": "Tiếp thị Nội dung",
}


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _extract_section(text: str, header: str) -> str:
    pattern = rf"## {re.escape(header)}\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        PRAGMA foreign_keys = ON;
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
        );
        CREATE INDEX IF NOT EXISTS idx_crm_proposals_customer ON crm_proposals (customer_id);
    """)


def create_proposal(
    conn: sqlite3.Connection,
    customer_id: int,
    service_slugs: list[str],
    total_vnd: int,
    timeline_months: int,
    notes: str,
    *,
    lifecycle_id: int | None = None,
) -> int:
    ts = _ts()
    cur = conn.execute(
        """INSERT INTO crm_proposals
           (customer_id, lifecycle_id, service_slugs, total_vnd, timeline_months, notes, ai_output, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (customer_id, lifecycle_id, json.dumps(service_slugs), total_vnd, timeline_months, notes, "{}", ts, ts),
    )
    conn.commit()
    return cur.lastrowid


def list_proposals(conn: sqlite3.Connection, customer_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM crm_proposals WHERE customer_id = ? ORDER BY id DESC",
        (customer_id,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["service_slugs"] = json.loads(d.get("service_slugs") or "[]")
        d["generated"] = d.get("ai_output", "{}") != "{}"
        result.append(d)
    return result


def get_proposal(conn: sqlite3.Connection, proposal_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM crm_proposals WHERE id = ?",
        (proposal_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["service_slugs"] = json.loads(d.get("service_slugs") or "[]")
    d["ai_output"] = json.loads(d.get("ai_output") or "{}")
    return d


def delete_proposal(conn: sqlite3.Connection, proposal_id: int) -> None:
    conn.execute("DELETE FROM crm_proposals WHERE id = ?", (proposal_id,))
    conn.commit()


def get_customer_context(conn: sqlite3.Connection, customer_id: int) -> dict:
    customer_row = conn.execute(
        "SELECT name, company, address, phone, email FROM crm_customers WHERE id = ?",
        (customer_id,),
    ).fetchone()
    customer = dict(customer_row) if customer_row else {
        "name": "", "company": "", "address": "", "phone": "", "email": "",
    }

    lead_row = conn.execute(
        "SELECT product_interest, need FROM crm_leads WHERE converted_customer_id = ? ORDER BY id DESC LIMIT 1",
        (customer_id,),
    ).fetchone()
    lead = dict(lead_row) if lead_row else None

    contract_row = conn.execute(
        "SELECT COUNT(*) as count, COALESCE(SUM(amount_vnd), 0) as total_vnd FROM crm_contracts WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    contracts = {
        "count": contract_row["count"] if contract_row else 0,
        "total_vnd": contract_row["total_vnd"] if contract_row else 0,
    }

    past_rows = conn.execute(
        "SELECT DISTINCT service_slug FROM crm_service_lifecycle WHERE customer_id = ?",
        (customer_id,),
    ).fetchall()
    past_service_slugs = [r["service_slug"] for r in past_rows]

    active_rows = conn.execute(
        "SELECT service_slug FROM crm_service_lifecycle WHERE customer_id = ? AND status = 'active'",
        (customer_id,),
    ).fetchall()
    active_lifecycles = [r["service_slug"] for r in active_rows]

    return {
        "customer": customer,
        "lead": lead,
        "contracts": contracts,
        "past_service_slugs": past_service_slugs,
        "active_lifecycles": active_lifecycles,
    }


def run_proposal_ai(conn: sqlite3.Connection, proposal_id: int) -> dict:
    try:
        import anthropic
        proposal = get_proposal(conn, proposal_id)
        if proposal is None:
            return {}
        ctx = get_customer_context(conn, proposal["customer_id"])

        service_names_str = ", ".join(
            SERVICE_NAMES.get(s, s) for s in proposal["service_slugs"]
        ) or "Chưa chọn dịch vụ"
        past_services_str = ", ".join(
            SERVICE_NAMES.get(s, s) for s in ctx["past_service_slugs"]
        ) or "Chưa có"
        lead = ctx["lead"] or {}
        product_interest = lead.get("product_interest") or "Không rõ"
        need = lead.get("need") or "Không rõ"

        prompt = (
            f"Bạn là chuyên gia tư vấn marketing digital, viết đề xuất dịch vụ cho khách hàng doanh nghiệp.\n\n"
            f"Thông tin khách hàng:\n"
            f"- Tên: {ctx['customer']['name']}\n"
            f"- Công ty: {ctx['customer']['company'] or 'Cá nhân'}\n"
            f"- Ngành/Nhu cầu: {product_interest} — {need}\n"
            f"- Lịch sử: {ctx['contracts']['count']} hợp đồng trước "
            f"(tổng {ctx['contracts']['total_vnd']:,} VNĐ), đã dùng: {past_services_str}\n\n"
            f"Dịch vụ đề xuất lần này: {service_names_str}\n"
            f"Tổng giá trị: {proposal['total_vnd']:,} VNĐ / {proposal['timeline_months']} tháng\n"
            f"Ghi chú từ chuyên viên: {proposal['notes'] or 'Không có'}\n\n"
            f"Viết đề xuất theo đúng 5 header ## sau (không thêm header khác):\n\n"
            f"## Phân tích vấn đề\n"
            f"[Pain points của khách dựa trên ngành/nhu cầu. 3-5 câu.]\n\n"
            f"## Giải pháp đề xuất\n"
            f"[Cách các dịch vụ được chọn giải quyết vấn đề. Đề cập tên từng dịch vụ. 4-6 câu.]\n\n"
            f"## Tại sao chọn PTTCOM\n"
            f"[USP tailored theo context khách: kinh nghiệm, kết quả, sự phù hợp. 3-4 câu.]\n\n"
            f"## Kết quả kỳ vọng\n"
            f"[KPIs cụ thể theo từng dịch vụ được chọn. Format danh sách bullet. 4-6 items.]\n\n"
            f"## Tóm tắt báo giá\n"
            f"[Diễn giải mức giá thành văn thuyết phục: tại sao mức giá này xứng đáng. 2-3 câu.]"
        )

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        output = resp.content[0].text.strip()

        sections = {
            "problem": _extract_section(output, "Phân tích vấn đề"),
            "solution": _extract_section(output, "Giải pháp đề xuất"),
            "usp": _extract_section(output, "Tại sao chọn PTTCOM"),
            "kpi": _extract_section(output, "Kết quả kỳ vọng"),
            "pricing_narrative": _extract_section(output, "Tóm tắt báo giá"),
        }

        ts = _ts()
        conn.execute(
            "UPDATE crm_proposals SET ai_output = ?, updated_at = ? WHERE id = ?",
            (json.dumps(sections), ts, proposal_id),
        )
        conn.commit()
        return sections
    except Exception:
        return {}
```

- [ ] **Step 4: Chạy tests để xác nhận pass**

```bash
python3 -m pytest tests/test_crm_proposal.py -v
```
Expected: 12 tests PASS

- [ ] **Step 5: Xác nhận import sạch**

```bash
python3 -c "import crm_proposal; print('OK')"
```

---

### Task 2: Wire `app.py` — import + schema init + 5 routes

**Files:**
- Modify: `app.py` (3 điểm)

**Interfaces:**
- Consumes từ Task 1: tất cả 7 functions + `SERVICE_NAMES`
- Import alias pattern: `from crm_proposal import X as _prop_X`

- [ ] **Step 1: Thêm import tại dòng 338**

Tìm:
```python
from crm_aeo import ensure_schema as _ensure_aeo_schema
```
Thêm ngay sau:
```python
from crm_proposal import ensure_schema as _ensure_proposal_schema
```

- [ ] **Step 2: Thêm schema init tại dòng ~2284**

Tìm:
```python
    _ensure_aeo_schema(conn)
```
Thêm ngay sau:
```python
    _ensure_proposal_schema(conn)
```

- [ ] **Step 3: Thêm 5 routes sau `api_crm_aeo_content` (~dòng 5034)**

Tìm function `api_crm_aeo_content` và thêm sau phần body của nó:

```python
@app.get("/crm/proposals")
def crm_proposals_page() -> Any:
    redir = _ensure_crm_session_html()
    if redir is not None:
        return redir
    from crm_proposal import list_proposals as _prop_list, SERVICE_NAMES as _svc_names
    customer_id = _opt_pos_int(request.args.get("customer_id"))
    with get_connection() as conn:
        all_customers = [
            dict(r) for r in conn.execute(
                "SELECT id, name, company FROM crm_customers ORDER BY name"
            ).fetchall()
        ]
        proposals = []
        selected_customer = None
        if customer_id:
            row = conn.execute(
                "SELECT id, name, company FROM crm_customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
            selected_customer = dict(row) if row else None
            if selected_customer:
                proposals = _prop_list(conn, customer_id)
    return render_template(
        "crm_proposals.html",
        all_customers=all_customers,
        selected_customer=selected_customer,
        proposals=proposals,
        customer_id=customer_id,
        service_names=_svc_names,
        **_admin_page_template_kwargs(),
    )


@app.get("/crm/proposals/<int:proposal_id>/preview")
def crm_proposal_preview_page(proposal_id: int) -> Any:
    redir = _ensure_crm_session_html()
    if redir is not None:
        return redir
    from crm_proposal import get_proposal as _prop_get, get_customer_context as _prop_ctx, SERVICE_NAMES as _svc_names
    with get_connection() as conn:
        proposal = _prop_get(conn, proposal_id)
        if proposal is None:
            return "Không tìm thấy đề xuất.", 404
        ctx = _prop_ctx(conn, proposal["customer_id"])
    return render_template(
        "crm_proposal_preview.html",
        proposal=proposal,
        customer=ctx["customer"],
        service_names=_svc_names,
        **_admin_page_template_kwargs(),
    )


@app.post("/api/crm/proposals")
def api_crm_proposals_create() -> Any:
    from crm_proposal import create_proposal as _prop_create
    body = request.get_json(silent=True) or {}
    customer_id = _opt_pos_int(body.get("customer_id"))
    service_slugs = [str(s).strip() for s in body.get("service_slugs", []) if str(s).strip()]
    total_vnd = _opt_pos_int(body.get("total_vnd")) or 0
    timeline_months = _opt_pos_int(body.get("timeline_months")) or 1
    notes = str(body.get("notes", "")).strip()[:2000]
    lifecycle_id = _opt_pos_int(body.get("lifecycle_id"))
    if not customer_id or not service_slugs:
        return jsonify({"error": "Thiếu customer_id hoặc service_slugs"}), 400
    with get_connection() as conn:
        pid = _prop_create(
            conn, customer_id, service_slugs, total_vnd, timeline_months, notes,
            lifecycle_id=lifecycle_id,
        )
    return jsonify({"id": pid})


@app.post("/api/crm/proposals/<int:proposal_id>/generate")
def api_crm_proposals_generate(proposal_id: int) -> Any:
    from crm_proposal import run_proposal_ai as _prop_ai, get_proposal as _prop_get
    with get_connection() as conn:
        sections = _prop_ai(conn, proposal_id)
        if not sections:
            return jsonify({"error": "Không thể tạo nội dung AI"}), 500
        proposal = _prop_get(conn, proposal_id)
    return jsonify({**sections, "updated_at": proposal["updated_at"] if proposal else ""})


@app.delete("/api/crm/proposals/<int:proposal_id>")
def api_crm_proposals_delete(proposal_id: int) -> Any:
    from crm_proposal import delete_proposal as _prop_del
    with get_connection() as conn:
        _prop_del(conn, proposal_id)
    return jsonify({})
```

- [ ] **Step 4: Xác nhận**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_proposal.py -v
```
Expected: import OK, 12 tests PASS

---

### Task 3: `templates/crm_proposals.html` — Workspace

**Files:**
- Create: `templates/crm_proposals.html`

**Interfaces:**
- Consumes: `all_customers` (list[dict]: id, name, company), `selected_customer` (dict|None), `proposals` (list[dict] — mỗi dict có service_slugs: list, total_vnd, timeline_months, created_at, generated: bool, id), `customer_id` (int|None), `service_names` (dict[str,str])
- API: POST `/api/crm/proposals`, POST `/api/crm/proposals/<id>/generate`, DELETE `/api/crm/proposals/<id>`

**Lưu ý layout:**
- Extends `admin_layout.html`: `{% block admin_main %}` render tại line 41, `{% block admin_page_scripts %}` render tại line 52 — sau admin_main.
- Tất cả JS functions phải nằm trong `{% block admin_page_scripts %}` (không gọi function từ admin_main trước khi define).
- Service checkboxes cần `name="service_slugs"` với `value="{{ slug }}"` — nhưng vì submit bằng JS (fetch), dùng `data-slug="{{ slug }}"` trên checkbox.

- [ ] **Step 1: Tạo template**

```html
{# templates/crm_proposals.html #}
{% extends "admin_layout.html" %}
{% block title %}Đề xuất Dịch vụ{% endblock %}
{% block meta_robots %}noindex, nofollow{% endblock %}
{% block admin_page_title %}Đề xuất Dịch vụ{% endblock %}

{% block admin_main %}
<div style="max-width:1000px;margin:0 auto;padding:1rem;">

  {# Customer selector #}
  <form method="get" style="margin-bottom:1.5rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;">
    <label style="font-weight:600;font-size:.9rem;">Khách hàng:</label>
    <select name="customer_id" onchange="this.form.submit()"
            style="padding:.45rem .7rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.9rem;min-width:220px;">
      <option value="">-- Chọn khách hàng --</option>
      {% for cu in all_customers %}
      <option value="{{ cu.id }}" {% if cu.id == customer_id %}selected{% endif %}>
        {{ cu.name }}{% if cu.company %} — {{ cu.company }}{% endif %}
      </option>
      {% endfor %}
    </select>
  </form>

  {% if selected_customer %}
  {# Create form #}
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem 1.25rem;margin-bottom:1.25rem;">
    <div style="font-weight:600;font-size:.875rem;margin-bottom:.75rem;">+ Tạo đề xuất mới cho {{ selected_customer.name }}</div>

    <div style="margin-bottom:.75rem;">
      <div style="font-size:.8rem;color:#6b7280;margin-bottom:.4rem;font-weight:600;">Dịch vụ đề xuất:</div>
      <div style="display:flex;flex-wrap:wrap;gap:.4rem .75rem;">
        {% for slug, name in service_names.items() %}
        <label style="display:flex;align-items:center;gap:.3rem;font-size:.8rem;cursor:pointer;">
          <input type="checkbox" class="svc-check" data-slug="{{ slug }}" style="cursor:pointer;" />
          {{ name }}
        </label>
        {% endfor %}
      </div>
    </div>

    <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:flex-end;margin-top:.5rem;">
      <div>
        <div style="font-size:.8rem;color:#6b7280;margin-bottom:.25rem;">Tổng giá trị (VNĐ)</div>
        <input id="new-total-vnd" type="number" min="0" placeholder="5000000"
               style="padding:.4rem .6rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.875rem;width:140px;" />
      </div>
      <div>
        <div style="font-size:.8rem;color:#6b7280;margin-bottom:.25rem;">Thời hạn (tháng)</div>
        <input id="new-timeline" type="number" min="1" max="36" placeholder="3"
               style="padding:.4rem .6rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.875rem;width:90px;" />
      </div>
      <div style="flex:1;min-width:160px;">
        <div style="font-size:.8rem;color:#6b7280;margin-bottom:.25rem;">Ghi chú SP (tuỳ chọn)</div>
        <input id="new-notes" type="text" placeholder="Khách cần tư vấn thêm về..."
               style="width:100%;box-sizing:border-box;padding:.4rem .6rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.875rem;" />
      </div>
      <button onclick="createProposal({{ selected_customer.id }})"
              style="padding:.45rem 1.1rem;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-size:.875rem;cursor:pointer;white-space:nowrap;align-self:flex-end;">
        Tạo Đề xuất
      </button>
    </div>
  </div>

  {# Proposal list #}
  {% if proposals %}
  <table style="width:100%;border-collapse:collapse;font-size:.875rem;">
    <thead>
      <tr style="border-bottom:2px solid #e2e8f0;text-align:left;">
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Dịch vụ</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Giá</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Thời hạn</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Ngày tạo</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">AI</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Hành động</th>
      </tr>
    </thead>
    <tbody>
    {% for p in proposals %}
    <tr style="border-bottom:1px solid #f1f5f9;">
      <td style="padding:.6rem .75rem;max-width:280px;font-size:.8rem;">
        {% for slug in p.service_slugs %}
        <span style="display:inline-block;background:#eff6ff;color:#1e40af;padding:.1rem .4rem;border-radius:3px;font-size:.75rem;margin:.1rem .1rem .1rem 0;">
          {{ service_names.get(slug, slug) }}
        </span>
        {% endfor %}
      </td>
      <td style="padding:.6rem .75rem;white-space:nowrap;">{{ "{:,}".format(p.total_vnd) }} ₫</td>
      <td style="padding:.6rem .75rem;">{{ p.timeline_months }} tháng</td>
      <td style="padding:.6rem .75rem;color:#6b7280;font-size:.8rem;">{{ p.created_at[:10] }}</td>
      <td style="padding:.6rem .75rem;">
        {% if p.generated %}
        <span style="color:#16a34a;font-size:.8rem;font-weight:600;">✓ Đã tạo</span>
        {% else %}
        <span id="ai-badge-{{ p.id }}" style="color:#9ca3af;font-size:.8rem;">Chờ generate</span>
        {% endif %}
      </td>
      <td style="padding:.6rem .75rem;white-space:nowrap;">
        <button onclick="generateAI({{ p.id }})" id="gen-btn-{{ p.id }}"
                {% if p.generated %}style="padding:.25rem .6rem;font-size:.78rem;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;cursor:pointer;margin-right:.25rem;"
                {% else %}style="padding:.25rem .6rem;font-size:.78rem;background:#3b82f6;color:#fff;border:none;border-radius:4px;cursor:pointer;margin-right:.25rem;"{% endif %}>
          {% if p.generated %}Tạo lại AI{% else %}Tạo AI{% endif %}
        </button>
        <a href="/crm/proposals/{{ p.id }}/preview" target="_blank"
           style="display:inline-block;padding:.25rem .6rem;font-size:.78rem;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;cursor:pointer;margin-right:.25rem;text-decoration:none;color:inherit;">
          Xem / In
        </a>
        <button onclick="deleteProposal({{ p.id }})"
                style="padding:.25rem .6rem;font-size:.78rem;background:#fff;border:1px solid #fca5a5;color:#dc2626;border-radius:4px;cursor:pointer;">
          Xoá
        </button>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div style="text-align:center;padding:3rem;color:#9ca3af;font-size:.9rem;">
    Chưa có đề xuất nào. Tạo đề xuất đầu tiên ở trên.
  </div>
  {% endif %}
  {% else %}
  <div style="text-align:center;padding:3rem;color:#9ca3af;font-size:.9rem;">
    Chọn khách hàng để bắt đầu tạo đề xuất dịch vụ.
  </div>
  {% endif %}

</div>
{% endblock %}

{% block admin_page_scripts %}
<script>
function createProposal(customerId) {
  var checks = document.querySelectorAll('.svc-check:checked');
  var slugs = Array.from(checks).map(function(c) { return c.getAttribute('data-slug'); });
  if (!slugs.length) { alert('Vui lòng chọn ít nhất một dịch vụ.'); return; }
  var totalVnd = parseInt(document.getElementById('new-total-vnd').value) || 0;
  var timeline = parseInt(document.getElementById('new-timeline').value) || 1;
  var notes = document.getElementById('new-notes').value.trim();
  fetch('/api/crm/proposals', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      customer_id: customerId,
      service_slugs: slugs,
      total_vnd: totalVnd,
      timeline_months: timeline,
      notes: notes,
    }),
  }).then(function(r) { return r.json(); })
    .then(function() { location.reload(); })
    .catch(console.error);
}

function generateAI(proposalId) {
  var btn = document.getElementById('gen-btn-' + proposalId);
  var badge = document.getElementById('ai-badge-' + proposalId);
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  fetch('/api/crm/proposals/' + proposalId + '/generate', {method: 'POST'})
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.error) { alert('Lỗi: ' + data.error); if (btn) { btn.disabled = false; btn.textContent = 'Tạo AI'; } return; }
      if (badge) { badge.textContent = '✓ Đã tạo'; badge.style.color = '#16a34a'; badge.style.fontWeight = '600'; }
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Tạo lại AI';
        btn.style.background = '#f1f5f9';
        btn.style.color = 'inherit';
        btn.style.border = '1px solid #cbd5e1';
      }
    })
    .catch(function(e) { console.error(e); if (btn) { btn.disabled = false; btn.textContent = 'Tạo AI'; } });
}

function deleteProposal(proposalId) {
  if (!confirm('Xoá đề xuất này?')) return;
  fetch('/api/crm/proposals/' + proposalId, {method: 'DELETE'})
    .then(function() { location.reload(); })
    .catch(console.error);
}
</script>
{% endblock %}
```

- [ ] **Step 2: Xác nhận app import OK**

```bash
python3 -c "import app; print('OK')"
```

---

### Task 4: `templates/crm_proposal_preview.html` — Preview + Print

**Files:**
- Create: `templates/crm_proposal_preview.html`

**Interfaces:**
- Consumes: `proposal` (dict: id, service_slugs: list, total_vnd, timeline_months, notes, ai_output: dict, created_at, updated_at), `customer` (dict: name, company, address, phone, email), `service_names` (dict[str,str])
- `ai_output` keys: `problem`, `solution`, `usp`, `kpi`, `pricing_narrative` — có thể empty string nếu chưa generate

**Lưu ý:** Template này là standalone preview page — KHÔNG cần admin_layout navigation cho print. Extends admin_layout để có session/nav bình thường, nhưng thêm `@media print` CSS để ẩn nav khi in.

- [ ] **Step 1: Tạo template**

```html
{# templates/crm_proposal_preview.html #}
{% extends "admin_layout.html" %}
{% block title %}Đề xuất PRO-{{ "%04d"|format(proposal.id) }}{% endblock %}
{% block meta_robots %}noindex, nofollow{% endblock %}
{% block admin_page_title %}Xem Đề xuất{% endblock %}
{% block admin_page_breadcrumb %}
  <a href="{{ url_for('crm_proposals_page') }}">← Danh sách đề xuất</a>
{% endblock %}

{% block admin_main %}
<style>
@media print {
  nav, header, .admin-sidebar, .admin-topbar, .breadcrumb, .no-print { display: none !important; }
  .proposal-doc { max-width: 100% !important; margin: 0 !important; padding: 0 !important; }
  .proposal-section { page-break-inside: avoid; }
  body { font-size: 11pt; }
}
</style>

<div class="proposal-doc" style="max-width:800px;margin:0 auto;padding:1.5rem 1rem;">

  {# Print button #}
  <div class="no-print" style="margin-bottom:1.5rem;display:flex;justify-content:flex-end;">
    <button onclick="window.print()"
            style="padding:.5rem 1.25rem;background:#1e40af;color:#fff;border:none;border-radius:6px;font-size:.875rem;cursor:pointer;font-weight:600;">
      🖨 In / Tải PDF
    </button>
  </div>

  {# Header #}
  <div class="proposal-section" style="border:2px solid #1e40af;border-radius:8px;padding:1.25rem 1.5rem;margin-bottom:1.25rem;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:.5rem;">
      <div>
        <div style="font-size:1.3rem;font-weight:800;color:#1e40af;letter-spacing:.02em;">PTTCOM</div>
        <div style="font-size:.8rem;color:#6b7280;margin-top:.15rem;">Digital Marketing Agency</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:1rem;font-weight:700;color:#374151;">ĐỀ XUẤT DỊCH VỤ</div>
        <div style="font-size:.8rem;color:#6b7280;margin-top:.2rem;">Mã: PRO-{{ "%04d"|format(proposal.id) }}</div>
        <div style="font-size:.8rem;color:#6b7280;">Ngày: {{ proposal.created_at[:10] }}</div>
      </div>
    </div>
  </div>

  {# Customer info #}
  <div class="proposal-section" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem 1.25rem;margin-bottom:1.25rem;">
    <div style="font-weight:600;font-size:.8rem;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem;">Kính gửi</div>
    <div style="font-size:1rem;font-weight:700;color:#1e3a5f;">{{ customer.name }}</div>
    {% if customer.company %}
    <div style="font-size:.875rem;color:#374151;margin-top:.2rem;">{{ customer.company }}</div>
    {% endif %}
    {% if customer.address %}
    <div style="font-size:.8rem;color:#6b7280;margin-top:.15rem;">{{ customer.address }}</div>
    {% endif %}
    {% if customer.phone or customer.email %}
    <div style="font-size:.8rem;color:#6b7280;margin-top:.15rem;">
      {% if customer.phone %}{{ customer.phone }}{% endif %}
      {% if customer.phone and customer.email %} · {% endif %}
      {% if customer.email %}{{ customer.email }}{% endif %}
    </div>
    {% endif %}
  </div>

  {% set ao = proposal.ai_output %}

  {% if ao.problem %}
  <div class="proposal-section" style="margin-bottom:1rem;">
    <div style="font-size:.95rem;font-weight:700;color:#1e3a5f;border-left:3px solid #3b82f6;padding-left:.6rem;margin-bottom:.5rem;">
      Phân tích vấn đề
    </div>
    <div style="font-size:.875rem;line-height:1.7;color:#374151;white-space:pre-wrap;">{{ ao.problem }}</div>
  </div>
  {% endif %}

  {% if ao.solution %}
  <div class="proposal-section" style="margin-bottom:1rem;">
    <div style="font-size:.95rem;font-weight:700;color:#1e3a5f;border-left:3px solid #3b82f6;padding-left:.6rem;margin-bottom:.5rem;">
      Giải pháp đề xuất
    </div>
    <div style="font-size:.875rem;line-height:1.7;color:#374151;white-space:pre-wrap;">{{ ao.solution }}</div>
  </div>
  {% endif %}

  {% if ao.usp %}
  <div class="proposal-section" style="margin-bottom:1rem;">
    <div style="font-size:.95rem;font-weight:700;color:#1e3a5f;border-left:3px solid #3b82f6;padding-left:.6rem;margin-bottom:.5rem;">
      Tại sao chọn PTTCOM
    </div>
    <div style="font-size:.875rem;line-height:1.7;color:#374151;white-space:pre-wrap;">{{ ao.usp }}</div>
  </div>
  {% endif %}

  {% if ao.kpi %}
  <div class="proposal-section" style="margin-bottom:1rem;">
    <div style="font-size:.95rem;font-weight:700;color:#1e3a5f;border-left:3px solid #3b82f6;padding-left:.6rem;margin-bottom:.5rem;">
      Kết quả kỳ vọng
    </div>
    <div style="font-size:.875rem;line-height:1.7;color:#374151;white-space:pre-wrap;">{{ ao.kpi }}</div>
  </div>
  {% endif %}

  {% if not ao.problem and not ao.solution %}
  <div style="text-align:center;padding:2rem;color:#9ca3af;font-size:.9rem;border:1px dashed #e2e8f0;border-radius:8px;margin-bottom:1.25rem;">
    Nội dung AI chưa được tạo. Quay lại danh sách và nhấn "Tạo AI".
  </div>
  {% endif %}

  {# Pricing table #}
  <div class="proposal-section" style="background:#1e3a5f;color:#fff;border-radius:8px;padding:1rem 1.25rem;margin-bottom:1.25rem;">
    <div style="font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;opacity:.7;margin-bottom:.75rem;">Bảng giá dịch vụ</div>
    {% for slug in proposal.service_slugs %}
    <div style="display:flex;justify-content:space-between;align-items:center;padding:.3rem 0;border-bottom:1px solid rgba(255,255,255,.1);font-size:.875rem;">
      <span>• {{ service_names.get(slug, slug) }}</span>
    </div>
    {% endfor %}
    <div style="display:flex;justify-content:space-between;align-items:center;padding:.6rem 0 0;margin-top:.25rem;font-size:1rem;font-weight:700;">
      <span>Tổng cộng</span>
      <span>{{ "{:,}".format(proposal.total_vnd) }} VNĐ / {{ proposal.timeline_months }} tháng</span>
    </div>
  </div>

  {% if ao.pricing_narrative %}
  <div class="proposal-section" style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:1rem 1.25rem;margin-bottom:1.25rem;">
    <div style="font-size:.875rem;line-height:1.7;color:#1e40af;white-space:pre-wrap;font-style:italic;">{{ ao.pricing_narrative }}</div>
  </div>
  {% endif %}

  {# Footer / Terms #}
  <div class="proposal-section" style="border-top:1px solid #e2e8f0;padding-top:.75rem;font-size:.75rem;color:#9ca3af;text-align:center;">
    Báo giá có hiệu lực trong vòng <strong>30 ngày</strong> kể từ ngày phát hành.
    Mọi thay đổi về phạm vi dịch vụ sẽ được thỏa thuận lại bằng văn bản.
    <br>PTTCOM — pttcom.vn
  </div>

</div>
{% endblock %}

{% block admin_page_scripts %}
<script>
// Print shortcut: Ctrl+P / Cmd+P works natively — no extra JS needed
</script>
{% endblock %}
```

- [ ] **Step 2: Xác nhận app import OK**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_proposal.py -v
```

---

### Task 5: Proposal card trong `templates/crm_service_workflow.html`

**Files:**
- Modify: `templates/crm_service_workflow.html` (1 điểm)

**Interfaces:**
- Consumes: `lifecycle` dict đã có trong template — fields `lifecycle.stage`, `lifecycle.customer_id`, `lifecycle.id`
- Không cần thêm kwarg mới vào route — `lifecycle` đã được pass sẵn

**Lưu ý:** Hiện tại file có AEO block tại dòng 815-827, theo sau là `<script>` tại dòng 829. Chèn proposal card SAU AEO block (sau `{% endif %}` của AEO), TRƯỚC `<script>`.

- [ ] **Step 1: Xác định điểm chèn**

```bash
grep -n "AEO Monitoring\|Finance JS\|<script>" /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/templates/crm_service_workflow.html | tail -5
```

Tìm dòng có comment `// ─── Finance JS` (bên trong `<script>` tag cuối admin_main). Điểm chèn là TRƯỚC `<script>` tag đó.

- [ ] **Step 2: Chèn proposal card**

Tìm đoạn duy nhất (kết hợp AEO endif + Finance JS comment):
```
{% endif %}

<script>
// ─── Finance JS
```
(đây là `{% endif %}` cuối block AEO Monitoring, script tag với Finance JS comment bên trong)

Chèn proposal card VÀO GIỮA — sau `{% endif %}` và trước `<script>`:

```html
{% if lifecycle.stage == "proposal" %}
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem 1.25rem;margin-top:1rem;">
  <div style="font-weight:600;font-size:.875rem;color:#374151;margin-bottom:.5rem;">Đề xuất Dịch vụ</div>
  <div style="font-size:.875rem;">
    <a href="/crm/proposals?customer_id={{ lifecycle.customer_id }}&lifecycle_id={{ lifecycle.id }}"
       style="color:#3b82f6;text-decoration:none;font-weight:500;">→ Tạo / Xem Đề xuất</a>
    <span style="margin-left:.75rem;font-size:.8rem;color:#6b7280;">Lifecycle đang ở stage Báo giá</span>
  </div>
</div>
{% endif %}
```

- [ ] **Step 3: Xác nhận**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_proposal.py -v
```
Expected: import OK, 12 tests PASS

---

## Kiểm tra cuối

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_proposal.py -v
```

Test thủ công:
1. Mở `/crm/proposals` → chọn khách → check 2-3 dịch vụ → nhập giá + timeline → "Tạo Đề xuất"
2. Trong proposal list: nhấn **Tạo AI** → spinner → badge đổi thành "✓ Đã tạo"
3. Nhấn **Xem / In** → preview page mở tab mới → thấy 5 AI sections + pricing table
4. Nhấn **In / Tải PDF** → `window.print()` dialog → nav bị ẩn trong print view
5. Mở workflow page của lifecycle ở stage `proposal` → thấy card "Đề xuất Dịch vụ" với link
