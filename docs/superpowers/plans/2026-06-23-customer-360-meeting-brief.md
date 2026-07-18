# Customer 360 Meeting Brief — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AM/SP nhấn một nút trước cuộc họp → AI tổng hợp toàn bộ data khách hàng thành Meeting Brief: tóm tắt, điểm chú ý, câu hỏi gợi ý.

**Architecture:** Module `crm_customer_brief.py` đọc data từ 6 bảng (customers, contracts, lifecycle, payments, expenses, risks/tasks), gọi claude-haiku để tạo brief, lưu vào bảng mới `crm_customer_brief_scans`. Ba routes Flask: 1 page + 2 API. Hai template: 1 full-page + thêm drawer panel vào `crm_customers.html`.

**Tech Stack:** Python 3, Flask 3, SQLite (`get_connection()`), Anthropic SDK trực tiếp (`claude-haiku-4-5-20251001`).

## Global Constraints

- `from __future__ import annotations` ở đầu mỗi file Python mới.
- Inline imports bên trong route functions (pattern của app.py).
- Auth: page route dùng `_ensure_crm_session_html()` — khớp với `crm_customers_page`.
- AI model: `claude-haiku-4-5-20251001`, `max_tokens=800`, synchronous, fail silent (return `""`).
- `_ts()` = `datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")`.
- Không thêm feature ngoài spec.
- Chạy tests bằng `python3 -m pytest`, import app bằng `python3 -c "import app; print('OK')"`.
- Không có git — không commit.
- `SERVICE_LABELS` dict lấy từ `from crm_svc_tasks import SERVICE_LABELS`.

---

## File Map

| File | Loại | Nhiệm vụ |
|------|------|---------|
| `crm_customer_brief.py` | Tạo mới | Schema + 4 public functions |
| `tests/test_crm_customer_brief.py` | Tạo mới | ~12 tests TDD, SQLite in-memory |
| `app.py` | Sửa nhỏ (4 chỗ) | +import dòng 336, +schema init dòng 2280, +3 routes, thêm `brief_url` vào `crm_customers_page` |
| `templates/crm_customer_meeting_brief.html` | Tạo mới | Full-page brief (textarea + 3 cards + print) |
| `templates/crm_customers.html` | Sửa nhỏ (2 chỗ) | +brief button trong customer row, +drawer panel HTML, +inline JS ở `admin_page_scripts` block |

---

### Task 1: `crm_customer_brief.py` + TDD tests

**Files:**
- Create: `crm_customer_brief.py`
- Create: `tests/test_crm_customer_brief.py`

**Interfaces:**
- Produces:
  - `ensure_schema(conn: sqlite3.Connection) -> None`
  - `get_customer_snapshot(conn: sqlite3.Connection, customer_id: int) -> dict`
  - `run_brief_ai(conn: sqlite3.Connection, customer_id: int, meeting_purpose: str, snapshot: dict) -> str`
  - `get_latest_brief(conn: sqlite3.Connection, customer_id: int) -> dict | None`

- [ ] **Step 1: Tạo file test với failing tests**

```python
# tests/test_crm_customer_brief.py
from __future__ import annotations
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import crm_customer_brief as m


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            company TEXT NOT NULL DEFAULT '',
            occupation TEXT NOT NULL DEFAULT '',
            lead_source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            assigned_am INTEGER,
            assigned_sp INTEGER
        );
        CREATE TABLE crm_svc_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            received_on TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_svc_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE crm_svc_risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE crm_svc_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            is_done INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT ''
        );
    """)
    m.ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_creates_table(self):
        conn = _setup_conn()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crm_customer_brief_scans'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_idempotent(self):
        conn = _setup_conn()
        m.ensure_schema(conn)  # second call should not raise
        row = conn.execute("SELECT COUNT(*) FROM crm_customer_brief_scans").fetchone()
        self.assertEqual(row[0], 0)


class TestGetCustomerSnapshot(unittest.TestCase):
    def _seed_customer(self, conn, *, created_at="2024-01-15 00:00:00"):
        conn.execute(
            "INSERT INTO crm_customers (name, company, occupation, lead_source, created_at) VALUES (?,?,?,?,?)",
            ("Nguyễn A", "Cty ABC", "Giám đốc", "facebook", created_at),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_no_data_returns_zeros(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(snap["total_contract_vnd"], 0)
        self.assertEqual(snap["active_lifecycles"], [])
        self.assertEqual(snap["open_issues"], 0)

    def test_customer_fields(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn, created_at="2024-01-15 00:00:00")
        snap = m.get_customer_snapshot(conn, cid)
        c = snap["customer"]
        self.assertEqual(c["name"], "Nguyễn A")
        self.assertEqual(c["company"], "Cty ABC")
        self.assertEqual(c["occupation"], "Giám đốc")
        self.assertIsInstance(c["months_as_customer"], int)
        self.assertGreaterEqual(c["months_as_customer"], 0)

    def test_total_contract_vnd(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_contracts (customer_id, amount_vnd, status) VALUES (?,?,?)", (cid, 10_000_000, "active"))
        conn.execute("INSERT INTO crm_contracts (customer_id, amount_vnd, status) VALUES (?,?,?)", (cid, 5_000_000, "active"))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(snap["total_contract_vnd"], 15_000_000)

    def test_active_lifecycles_populated(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status) VALUES (?,?,?,?)", (cid, "seo", "onboarding", "active"))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(len(snap["active_lifecycles"]), 1)
        lc = snap["active_lifecycles"][0]
        self.assertEqual(lc["service_slug"], "seo")
        self.assertEqual(lc["stage"], "onboarding")

    def test_margin_pct_calculation(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status) VALUES (?,?,?,?)", (cid, "seo", "active", "active"))
        conn.commit()
        lc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, status) VALUES (?,?,?)", (lc_id, 10_000_000, "received"))
        conn.execute("INSERT INTO crm_svc_expenses (lifecycle_id, amount_vnd) VALUES (?,?)", (lc_id, 2_000_000))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        lc = snap["active_lifecycles"][0]
        self.assertAlmostEqual(lc["margin_pct"], 80.0, places=1)

    def test_outstanding_calculation(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_contracts (customer_id, amount_vnd, status) VALUES (?,?,?)", (cid, 20_000_000, "active"))
        conn.commit()
        ct_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status, contract_id) VALUES (?,?,?,?,?)", (cid, "seo", "active", "active", ct_id))
        conn.commit()
        lc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, status) VALUES (?,?,?)", (lc_id, 5_000_000, "received"))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        lc = snap["active_lifecycles"][0]
        self.assertEqual(lc["outstanding"], 15_000_000)

    def test_pending_tasks_count(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status) VALUES (?,?,?,?)", (cid, "seo", "active", "active"))
        conn.commit()
        lc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_svc_tasks (lifecycle_id, is_done) VALUES (?,?)", (lc_id, 0))
        conn.execute("INSERT INTO crm_svc_tasks (lifecycle_id, is_done) VALUES (?,?)", (lc_id, 0))
        conn.execute("INSERT INTO crm_svc_tasks (lifecycle_id, is_done) VALUES (?,?)", (lc_id, 1))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(snap["active_lifecycles"][0]["pending_tasks"], 2)

    def test_active_risks_count(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status) VALUES (?,?,?,?)", (cid, "seo", "active", "active"))
        conn.commit()
        lc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_svc_risks (lifecycle_id, is_active) VALUES (?,?)", (lc_id, 1))
        conn.execute("INSERT INTO crm_svc_risks (lifecycle_id, is_active) VALUES (?,?)", (lc_id, 0))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(snap["active_lifecycles"][0]["active_risks"], 1)


class TestGetLatestBrief(unittest.TestCase):
    def _seed_customer(self, conn):
        conn.execute("INSERT INTO crm_customers (name) VALUES (?)", ("Test",))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_no_brief_returns_none(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        self.assertIsNone(m.get_latest_brief(conn, cid))

    def test_returns_latest_by_id_desc(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute(
            "INSERT INTO crm_customer_brief_scans (customer_id, meeting_purpose, ai_output, created_at) VALUES (?,?,?,?)",
            (cid, "first", "output1", "2026-01-01 00:00:00"),
        )
        conn.execute(
            "INSERT INTO crm_customer_brief_scans (customer_id, meeting_purpose, ai_output, created_at) VALUES (?,?,?,?)",
            (cid, "second", "output2", "2026-01-02 00:00:00"),
        )
        conn.commit()
        brief = m.get_latest_brief(conn, cid)
        self.assertIsNotNone(brief)
        self.assertEqual(brief["meeting_purpose"], "second")
        self.assertEqual(brief["ai_output"], "output2")


class TestRunBriefAi(unittest.TestCase):
    def _seed_customer(self, conn):
        conn.execute("INSERT INTO crm_customers (name) VALUES (?)", ("Test",))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_no_api_key_returns_empty(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        snap = {"customer": {"name": "Test", "company": "", "occupation": "", "months_as_customer": 1}, "total_contract_vnd": 0, "active_lifecycles": [], "open_issues": 0}
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = Exception("no key")
            result = m.run_brief_ai(conn, cid, "", snap)
        self.assertEqual(result, "")

    def test_saves_to_scans_on_success(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        snap = {"customer": {"name": "Test", "company": "", "occupation": "", "months_as_customer": 1}, "total_contract_vnd": 0, "active_lifecycles": [], "open_issues": 0}
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="## Tóm tắt\nTest")]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = m.run_brief_ai(conn, cid, "upsell", snap)
        self.assertIn("Tóm tắt", result)
        row = conn.execute("SELECT * FROM crm_customer_brief_scans WHERE customer_id = ?", (cid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["meeting_purpose"], "upsell")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

```bash
python3 -m pytest tests/test_crm_customer_brief.py -v
```
Expected: nhiều lỗi `ModuleNotFoundError: No module named 'crm_customer_brief'`

- [ ] **Step 3: Tạo `crm_customer_brief.py`**

```python
# crm_customer_brief.py
from __future__ import annotations
import sqlite3
from datetime import datetime


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS crm_customer_brief_scans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            meeting_purpose TEXT NOT NULL DEFAULT '',
            ai_output       TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_brief_scans_customer
            ON crm_customer_brief_scans (customer_id);
    """)


def get_customer_snapshot(conn: sqlite3.Connection, customer_id: int) -> dict:
    customer = conn.execute(
        "SELECT id, name, company, occupation, lead_source, created_at FROM crm_customers WHERE id = ?",
        (customer_id,),
    ).fetchone()
    if customer is None:
        return {"customer": {}, "contracts": [], "total_contract_vnd": 0, "active_lifecycles": [], "open_issues": 0}

    now = datetime.utcnow()
    try:
        created = datetime.strptime(customer["created_at"][:10], "%Y-%m-%d")
        months = (now.year - created.year) * 12 + (now.month - created.month)
    except Exception:
        months = 0

    contracts = [
        dict(r) for r in conn.execute(
            "SELECT id, amount_vnd, status FROM crm_contracts WHERE customer_id = ?",
            (customer_id,),
        ).fetchall()
    ]
    total_contract_vnd = sum(c["amount_vnd"] for c in contracts)

    lifecycles = conn.execute(
        """SELECT id, service_slug, stage, assigned_am, assigned_sp, contract_id
           FROM crm_service_lifecycle
           WHERE customer_id = ? AND status = 'active'""",
        (customer_id,),
    ).fetchall()

    try:
        from crm_svc_tasks import SERVICE_LABELS as _svc_labels
    except Exception:
        _svc_labels = {}

    active_lifecycles = []
    for lc in lifecycles:
        lc_id = lc["id"]

        received = conn.execute(
            "SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_payments WHERE lifecycle_id = ? AND status = 'received'",
            (lc_id,),
        ).fetchone()[0]
        expenses = conn.execute(
            "SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses WHERE lifecycle_id = ?",
            (lc_id,),
        ).fetchone()[0]
        margin_pct = ((received - expenses) / received * 100.0) if received > 0 else 0.0

        contract_amount = 0
        if lc["contract_id"]:
            row = conn.execute("SELECT amount_vnd FROM crm_contracts WHERE id = ?", (lc["contract_id"],)).fetchone()
            if row:
                contract_amount = row["amount_vnd"]
        outstanding = max(0, contract_amount - received)

        last_payment = conn.execute(
            "SELECT received_on FROM crm_svc_payments WHERE lifecycle_id = ? AND status = 'received' ORDER BY id DESC LIMIT 1",
            (lc_id,),
        ).fetchone()

        active_risks = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_risks WHERE lifecycle_id = ? AND is_active = 1",
            (lc_id,),
        ).fetchone()[0]
        pending_tasks = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = ? AND is_done = 0",
            (lc_id,),
        ).fetchone()[0]

        am_name = ""
        sp_name = ""
        if lc["assigned_am"]:
            row = conn.execute("SELECT name FROM crm_staff WHERE id = ?", (lc["assigned_am"],)).fetchone()
            if row:
                am_name = row["name"]
        if lc["assigned_sp"]:
            row = conn.execute("SELECT name FROM crm_staff WHERE id = ?", (lc["assigned_sp"],)).fetchone()
            if row:
                sp_name = row["name"]

        active_lifecycles.append({
            "id": lc_id,
            "service_slug": lc["service_slug"],
            "service_label": _svc_labels.get(lc["service_slug"], lc["service_slug"]),
            "stage": lc["stage"],
            "am_name": am_name,
            "sp_name": sp_name,
            "margin_pct": round(margin_pct, 1),
            "outstanding": outstanding,
            "last_payment_date": last_payment["received_on"] if last_payment else "",
            "active_risks": active_risks,
            "pending_tasks": pending_tasks,
        })

    open_issues = 0
    try:
        from crm_customer_360 import fetch_customer_issues
        issues = fetch_customer_issues(conn, customer_id)
        open_statuses = {"moi", "dang_xu_ly", "cho_khach", "cho_xu_ly"}
        open_issues = sum(1 for i in issues if i.get("status") in open_statuses)
    except Exception:
        pass

    return {
        "customer": {
            "id": customer["id"],
            "name": customer["name"],
            "company": customer["company"],
            "occupation": customer["occupation"],
            "lead_source": customer["lead_source"],
            "created_at": customer["created_at"],
            "months_as_customer": months,
        },
        "contracts": contracts,
        "total_contract_vnd": total_contract_vnd,
        "active_lifecycles": active_lifecycles,
        "open_issues": open_issues,
    }


def run_brief_ai(
    conn: sqlite3.Connection,
    customer_id: int,
    meeting_purpose: str,
    snapshot: dict,
) -> str:
    try:
        import anthropic
        c = snapshot["customer"]
        purpose_str = meeting_purpose.strip() or "Không xác định — tạo brief tổng quát"
        lc_lines = ""
        for lc in snapshot.get("active_lifecycles", []):
            lc_lines += (
                f"- {lc['service_label']}: stage={lc['stage']}, "
                f"margin={lc['margin_pct']:.1f}%, công nợ={lc['outstanding']:,} VND, "
                f"AM={lc['am_name'] or 'chưa phân công'}, SP={lc['sp_name'] or 'chưa phân công'}, "
                f"risks active={lc['active_risks']}, tasks chưa xong={lc['pending_tasks']}\n"
            )
        if not lc_lines:
            lc_lines = "  (không có dịch vụ đang triển khai)\n"

        prompt = f"""Bạn là chuyên gia tư vấn chiến lược khách hàng B2B.

Mục đích cuộc họp: {purpose_str}

=== DATA KHÁCH HÀNG ===
Tên: {c['name']} | Công ty: {c['company']} | Vị trí: {c['occupation']} | Gắn bó: {c['months_as_customer']} tháng
Tổng giá trị hợp đồng: {snapshot['total_contract_vnd']:,} VND

Dịch vụ đang triển khai:
{lc_lines}
Issues/khiếu nại đang mở: {snapshot['open_issues']}

=== YÊU CẦU ===
Tạo Meeting Brief ngắn gọn với đúng 3 phần sau (dùng header ##):

## Tóm tắt khách hàng
[3-4 dòng: profile, thời gian gắn bó, dịch vụ đang dùng, tổng giá trị]

## Điểm cần chú ý
[Tối đa 3 bullet, mỗi bullet 1 vấn đề nổi bật nhất dựa trên data: margin thấp, risk active, task trễ, công nợ cao, khiếu nại mở]

## Câu hỏi gợi ý
[3-4 câu AM nên hỏi khách trong buổi họp này, phù hợp với mục đích và tình trạng thực tế]"""

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        output = resp.content[0].text.strip()
        ts = _ts()
        conn.execute(
            "INSERT INTO crm_customer_brief_scans (customer_id, meeting_purpose, ai_output, created_at) VALUES (?,?,?,?)",
            (customer_id, meeting_purpose, output, ts),
        )
        conn.commit()
        return output
    except Exception:
        return ""


def get_latest_brief(conn: sqlite3.Connection, customer_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, meeting_purpose, ai_output, created_at FROM crm_customer_brief_scans WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
        (customer_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)
```

- [ ] **Step 4: Chạy tests để xác nhận pass**

```bash
python3 -m pytest tests/test_crm_customer_brief.py -v
```
Expected: 12 tests PASS

- [ ] **Step 5: Xác nhận import sạch**

```bash
python3 -c "import crm_customer_brief; print('OK')"
```

---

### Task 2: Wire `app.py` — import + schema init + 3 routes

**Files:**
- Modify: `app.py` (4 điểm thay đổi độc lập)

**Interfaces:**
- Consumes:
  - `crm_customer_brief.ensure_schema(conn)`
  - `crm_customer_brief.get_customer_snapshot(conn, customer_id)`
  - `crm_customer_brief.run_brief_ai(conn, customer_id, meeting_purpose, snapshot)`
  - `crm_customer_brief.get_latest_brief(conn, customer_id)`

- [ ] **Step 1: Thêm import tại dòng 336 (sau `_ensure_svc_kpi_schema`)**

Tìm block:
```python
from crm_svc_kpi import ensure_schema as _ensure_svc_kpi_schema
```
Thêm ngay sau:
```python
from crm_customer_brief import ensure_schema as _ensure_customer_brief_schema
```

- [ ] **Step 2: Thêm schema init tại dòng ~2280 (sau `_ensure_svc_kpi_schema(conn)`)**

Tìm block:
```python
    _ensure_svc_kpi_schema(conn)
```
Thêm ngay sau:
```python
    _ensure_customer_brief_schema(conn)
```

- [ ] **Step 3: Thêm page route `/crm/customer/<id>/meeting-brief`**

Thêm route này ngay sau `crm_customers_page()` (khoảng dòng 4907):
```python
@app.get("/crm/customer/<int:customer_id>/meeting-brief")
def crm_customer_meeting_brief_page(customer_id: int) -> str:
    redir = _ensure_crm_session_html()
    if redir is not None:
        return redir
    with get_connection() as conn:
        from crm_customer_brief import get_customer_snapshot as _snap, get_latest_brief as _latest
        customer = conn.execute(
            "SELECT id, name, company FROM crm_customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        if customer is None:
            return "Không tìm thấy khách hàng", 404
        latest = _latest(conn, customer_id)
    return render_template(
        "crm_customer_meeting_brief.html",
        customer=dict(customer),
        latest_brief=latest,
        **_admin_page_template_kwargs(),
    )
```

- [ ] **Step 4: Thêm API route POST `/api/crm/customers/<id>/brief/generate`**

Thêm sau route vừa tạo ở step 3:
```python
@app.post("/api/crm/customers/<int:customer_id>/brief/generate")
def api_crm_customer_brief_generate(customer_id: int) -> str:
    import json
    from flask import request as req
    with get_connection() as conn:
        from crm_customer_brief import get_customer_snapshot as _snap, run_brief_ai as _run
        body = req.get_json(silent=True) or {}
        meeting_purpose = str(body.get("meeting_purpose", ""))[:500]
        snapshot = _snap(conn, customer_id)
        output = _run(conn, customer_id, meeting_purpose, snapshot)
    from datetime import datetime
    return json.dumps({"ai_output": output, "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")})
```

- [ ] **Step 5: Thêm API route GET `/api/crm/customers/<id>/brief/latest`**

Thêm sau route vừa tạo ở step 4:
```python
@app.get("/api/crm/customers/<int:customer_id>/brief/latest")
def api_crm_customer_brief_latest(customer_id: int) -> str:
    import json
    with get_connection() as conn:
        from crm_customer_brief import get_latest_brief as _latest
        brief = _latest(conn, customer_id)
    return json.dumps(brief or {})
```

- [ ] **Step 6: Xác nhận import app OK và tests cũ vẫn pass**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_customer_brief.py -v
```
Expected: import OK, 12 tests PASS

---

### Task 3: Full-page template `crm_customer_meeting_brief.html`

**Files:**
- Create: `templates/crm_customer_meeting_brief.html`

**Interfaces:**
- Consumes từ route: `customer` (dict: id, name, company), `latest_brief` (dict | None)
- JS: `generateBrief()` POST `/api/crm/customers/<id>/brief/generate`, render 3 cards từ ai_output

- [ ] **Step 1: Tạo template**

```html
{# templates/crm_customer_meeting_brief.html #}
{% extends "admin_layout.html" %}
{% block title %}Meeting Brief — {{ customer.name }}{% endblock %}
{% block meta_robots %}noindex, nofollow{% endblock %}

{% block admin_page_title %}Meeting Brief{% endblock %}
{% block admin_page_breadcrumb %}
  <a href="{{ url_for('crm_customers_page') }}">← Danh sách khách</a>
{% endblock %}

{% block admin_main %}
<div class="brief-page" style="max-width:860px;margin:0 auto;padding:1.5rem 1rem;">

  <div class="brief-header" style="margin-bottom:1.5rem;">
    <h2 style="margin:0 0 .25rem;font-size:1.4rem;">{{ customer.name }}</h2>
    {% if customer.company %}
    <p style="margin:0;color:#666;font-size:.9rem;">{{ customer.company }}</p>
    {% endif %}
  </div>

  <div class="brief-input-section panel" style="padding:1.25rem;margin-bottom:1.25rem;border:1px solid #e2e8f0;border-radius:8px;">
    <label style="display:block;font-weight:600;margin-bottom:.5rem;font-size:.9rem;">
      Mục đích cuộc họp hôm nay
    </label>
    <textarea id="brief-purpose"
              rows="2"
              style="width:100%;box-sizing:border-box;padding:.6rem .75rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.9rem;resize:vertical;"
              placeholder="VD: upsell SEO Local, giải quyết khiếu nại tiến độ, review tháng...">{% if latest_brief %}{{ latest_brief.meeting_purpose }}{% endif %}</textarea>
    <div style="margin-top:.75rem;display:flex;align-items:center;gap:.75rem;">
      <button id="brief-btn" onclick="generateBrief({{ customer.id }})"
              style="padding:.55rem 1.25rem;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-size:.875rem;cursor:pointer;font-weight:600;">
        Tạo Brief
      </button>
      <span id="brief-spinner" hidden style="color:#6b7280;font-size:.85rem;">⏳ Đang tạo...</span>
    </div>
  </div>

  <div id="brief-output" {% if not latest_brief %}hidden{% endif %}>
    <div id="brief-card-summary"
         style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:1.25rem;margin-bottom:.75rem;">
      <h3 style="margin:0 0 .6rem;font-size:1rem;color:#1e40af;">Tóm tắt khách hàng</h3>
      <div id="brief-text-summary" style="font-size:.875rem;line-height:1.6;white-space:pre-wrap;"></div>
    </div>
    <div id="brief-card-points"
         style="background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:1.25rem;margin-bottom:.75rem;">
      <h3 style="margin:0 0 .6rem;font-size:1rem;color:#92400e;">Điểm cần chú ý</h3>
      <div id="brief-text-points" style="font-size:.875rem;line-height:1.6;white-space:pre-wrap;"></div>
    </div>
    <div id="brief-card-questions"
         style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:1.25rem;margin-bottom:1rem;">
      <h3 style="margin:0 0 .6rem;font-size:1rem;color:#14532d;">Câu hỏi gợi ý</h3>
      <div id="brief-text-questions" style="font-size:.875rem;line-height:1.6;white-space:pre-wrap;"></div>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;font-size:.8rem;color:#9ca3af;">
      <span>Brief tạo lúc: <span id="brief-created-at">{% if latest_brief %}{{ latest_brief.created_at }}{% endif %}</span></span>
      <button onclick="window.print()"
              style="padding:.4rem .9rem;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:5px;cursor:pointer;font-size:.8rem;">
        In Brief
      </button>
    </div>
  </div>

  {% if latest_brief and latest_brief.ai_output %}
  <script>
    (function() {
      var output = {{ latest_brief.ai_output | tojson }};
      renderBriefCards(output);
    })();
  </script>
  {% endif %}

</div>
{% endblock %}

{% block admin_page_scripts %}
<script>
function parseBriefSections(text) {
  var sections = { summary: '', points: '', questions: '' };
  var parts = text.split(/^## /m);
  for (var i = 0; i < parts.length; i++) {
    var p = parts[i];
    if (p.startsWith('Tóm tắt')) sections.summary = p.replace(/^Tóm tắt[^\n]*\n/, '').trim();
    else if (p.startsWith('Điểm')) sections.points = p.replace(/^Điểm[^\n]*\n/, '').trim();
    else if (p.startsWith('Câu hỏi')) sections.questions = p.replace(/^Câu hỏi[^\n]*\n/, '').trim();
  }
  return sections;
}

function renderBriefCards(text) {
  var s = parseBriefSections(text);
  document.getElementById('brief-text-summary').textContent = s.summary || text;
  document.getElementById('brief-text-points').textContent = s.points;
  document.getElementById('brief-text-questions').textContent = s.questions;
  document.getElementById('brief-output').removeAttribute('hidden');
}

function generateBrief(customerId) {
  var purpose = document.getElementById('brief-purpose').value.trim();
  var btn = document.getElementById('brief-btn');
  var spinner = document.getElementById('brief-spinner');
  btn.disabled = true;
  spinner.removeAttribute('hidden');
  fetch('/api/crm/customers/' + customerId + '/brief/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ meeting_purpose: purpose })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.ai_output) {
      renderBriefCards(data.ai_output);
      document.getElementById('brief-created-at').textContent = data.created_at || '';
    }
  })
  .catch(function(e) { console.error(e); })
  .finally(function() {
    btn.disabled = false;
    spinner.setAttribute('hidden', '');
  });
}
</script>
{% endblock %}
```

- [ ] **Step 2: Xác nhận app import OK (template không cần test riêng)**

```bash
python3 -c "import app; print('OK')"
```

---

### Task 4: Update `crm_customers.html` — brief button + drawer panel + inline JS

**Files:**
- Modify: `templates/crm_customers.html`

**Interfaces:**
- Consumes: `GET /api/crm/customers/<id>/brief/latest`, `POST /api/crm/customers/<id>/brief/generate`
- Pattern: drawer được thêm mới (không thuộc `crm-cu-drawer` hiện có), position fixed overlay riêng

**Lưu ý quan trọng:**
- File hiện có 449 dòng, dùng external JS `crm_customers.js`.
- KHÔNG sửa `crm_customers.js` — thêm inline JS trong `{% block admin_page_scripts %}`.
- Brief drawer là overlay riêng biệt (không phải tab trong `crm-cu-drawer` hiện có).

- [ ] **Step 1: Tìm chỗ render customer row để thêm brief button**

Đọc file `templates/crm_customers.html` để tìm vị trí render customer rows trong danh sách (JavaScript trong `crm_customers.js` dùng innerHTML để render rows, nên button có thể được thêm qua JS template trong file HTML).

Grep để tìm vị trí:
```bash
grep -n "openCustomer\|crm-cu-row\|data-customer" /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/static/crm_customers.js | head -20
```

- [ ] **Step 2: Thêm brief drawer HTML vào cuối `{% block admin_main %}` (trước `{% endblock %}`)**

Tìm dòng:
```
</div>
{% endblock %}
```
(dòng 440-441 trong file hiện tại)

Thêm HTML drawer ngay trước `{% endblock %}`:
```html

  <!-- Brief Quick Panel -->
  <div id="brief-panel-overlay"
       style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:900;"
       onclick="closeBriefPanel()"></div>
  <div id="brief-panel"
       style="display:none;position:fixed;top:0;right:0;width:420px;max-width:100vw;height:100vh;background:#fff;box-shadow:-4px 0 24px rgba(0,0,0,.15);z-index:901;overflow-y:auto;flex-direction:column;">
    <div style="padding:1rem 1.25rem;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;justify-content:space-between;">
      <div>
        <div id="brief-panel-name" style="font-weight:700;font-size:1rem;"></div>
        <a id="brief-panel-fulllink" href="#" style="font-size:.78rem;color:#3b82f6;">Xem đầy đủ →</a>
      </div>
      <button onclick="closeBriefPanel()" style="background:none;border:none;font-size:1.4rem;cursor:pointer;color:#6b7280;">×</button>
    </div>
    <div style="padding:1rem 1.25rem;">
      <div style="margin-bottom:.75rem;">
        <input id="brief-panel-purpose"
               type="text"
               placeholder="Mục đích cuộc họp (tuỳ chọn)"
               style="width:100%;box-sizing:border-box;padding:.5rem .7rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.85rem;" />
      </div>
      <button id="brief-panel-gen-btn" onclick="briefPanelGenerate()"
              style="width:100%;padding:.55rem;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-size:.875rem;cursor:pointer;font-weight:600;margin-bottom:1rem;">
        Tạo Brief
      </button>
      <div id="brief-panel-loading" hidden style="text-align:center;color:#6b7280;font-size:.85rem;margin-bottom:.75rem;">⏳ Đang tạo...</div>
      <div id="brief-panel-content">
        <div id="brief-panel-empty" style="text-align:center;color:#9ca3af;padding:2rem 0;font-size:.875rem;">Chưa có brief — nhấn "Tạo Brief" để tạo</div>
        <div id="brief-panel-cards" hidden>
          <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:.75rem;margin-bottom:.5rem;">
            <div style="font-weight:600;font-size:.8rem;color:#1e40af;margin-bottom:.3rem;">Tóm tắt</div>
            <div id="brief-panel-summary" style="font-size:.8rem;line-height:1.5;white-space:pre-wrap;"></div>
          </div>
          <div style="background:#fefce8;border:1px solid #fde68a;border-radius:6px;padding:.75rem;margin-bottom:.5rem;">
            <div style="font-weight:600;font-size:.8rem;color:#92400e;margin-bottom:.3rem;">Điểm chú ý</div>
            <div id="brief-panel-points" style="font-size:.8rem;line-height:1.5;white-space:pre-wrap;"></div>
          </div>
          <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:.75rem;margin-bottom:.75rem;">
            <div style="font-weight:600;font-size:.8rem;color:#14532d;margin-bottom:.3rem;">Câu hỏi gợi ý</div>
            <div id="brief-panel-questions" style="font-size:.8rem;line-height:1.5;white-space:pre-wrap;"></div>
          </div>
          <div style="font-size:.75rem;color:#9ca3af;">
            Tạo lúc: <span id="brief-panel-date"></span>
          </div>
        </div>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: Thêm inline JS vào `{% block admin_page_scripts %}` (sau script tag của crm_customers.js)**

Tìm dòng cuối của block (dòng 448-449 hiện tại):
```
<script src="{{ url_for('static', filename=_jcu) }}?v={{ static_v(_jcu) }}"></script>
```

Thêm ngay sau (trước `{% endblock %}`):
```html
<script>
(function() {
  var _briefCustomerId = null;

  function parseBriefSections(text) {
    var s = { summary: '', points: '', questions: '' };
    var parts = text.split(/^## /m);
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (p.startsWith('Tóm tắt')) s.summary = p.replace(/^Tóm tắt[^\n]*\n/, '').trim();
      else if (p.startsWith('Điểm')) s.points = p.replace(/^Điểm[^\n]*\n/, '').trim();
      else if (p.startsWith('Câu hỏi')) s.questions = p.replace(/^Câu hỏi[^\n]*\n/, '').trim();
    }
    return s;
  }

  function renderPanelBrief(data) {
    if (!data || !data.ai_output) {
      document.getElementById('brief-panel-empty').removeAttribute('hidden');
      document.getElementById('brief-panel-cards').setAttribute('hidden', '');
      return;
    }
    var s = parseBriefSections(data.ai_output);
    document.getElementById('brief-panel-summary').textContent = s.summary || data.ai_output;
    document.getElementById('brief-panel-points').textContent = s.points;
    document.getElementById('brief-panel-questions').textContent = s.questions;
    document.getElementById('brief-panel-date').textContent = data.created_at || '';
    document.getElementById('brief-panel-empty').setAttribute('hidden', '');
    document.getElementById('brief-panel-cards').removeAttribute('hidden');
  }

  window.openBriefPanel = function(customerId, customerName) {
    _briefCustomerId = customerId;
    document.getElementById('brief-panel-name').textContent = customerName;
    document.getElementById('brief-panel-fulllink').href = '/crm/customer/' + customerId + '/meeting-brief';
    document.getElementById('brief-panel-purpose').value = '';
    document.getElementById('brief-panel-empty').removeAttribute('hidden');
    document.getElementById('brief-panel-cards').setAttribute('hidden', '');
    document.getElementById('brief-panel-overlay').style.display = 'block';
    document.getElementById('brief-panel').style.display = 'flex';
    fetch('/api/crm/customers/' + customerId + '/brief/latest')
      .then(function(r) { return r.json(); })
      .then(function(data) { renderPanelBrief(data); })
      .catch(function() {});
  };

  window.closeBriefPanel = function() {
    document.getElementById('brief-panel-overlay').style.display = 'none';
    document.getElementById('brief-panel').style.display = 'none';
    _briefCustomerId = null;
  };

  window.briefPanelGenerate = function() {
    if (!_briefCustomerId) return;
    var purpose = document.getElementById('brief-panel-purpose').value.trim();
    var btn = document.getElementById('brief-panel-gen-btn');
    var loading = document.getElementById('brief-panel-loading');
    btn.disabled = true;
    loading.removeAttribute('hidden');
    fetch('/api/crm/customers/' + _briefCustomerId + '/brief/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meeting_purpose: purpose })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) { renderPanelBrief(data); })
    .catch(function(e) { console.error(e); })
    .finally(function() {
      btn.disabled = false;
      loading.setAttribute('hidden', '');
    });
  };
})();
</script>
```

- [ ] **Step 4: Thêm brief button vào customer row trong JS template**

Tìm trong `static/crm_customers.js` chỗ render customer row buttons (thường là `openCustomer` call):
```bash
grep -n "openCustomer\|data-id\|btn.*open\|action.*btn" /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/static/crm_customers.js | head -20
```

Nếu rows được render từ JS (innerHTML), tìm template string có button row và thêm brief button:
- Pattern để tìm: `openCustomer(` trong chuỗi innerHTML
- Thêm sau button hiện có: `<button class="btn btn--sm" onclick="openBriefPanel(${c.id}, ${JSON.stringify(c.name)})" title="Meeting Brief">📋</button>`

Nếu rows được render từ Jinja2 (HTML template trực tiếp), tìm vòng lặp `{% for customer in ... %}` trong template và thêm button tương tự.

- [ ] **Step 5: Xác nhận app import OK**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_customer_brief.py -v
```
Expected: import OK, 12 tests vẫn PASS

---

## Kiểm tra cuối

Sau khi hoàn thành tất cả 4 tasks:

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_customer_brief.py -v
```

Test thủ công:
1. Mở `/crm/customers` → thấy button `📋` trong customer row
2. Click `📋` → brief panel mở, gọi `/api/crm/customers/<id>/brief/latest`
3. Nhập mục đích họp → click "Tạo Brief" → 3 cards xuất hiện
4. Mở `/crm/customer/<id>/meeting-brief` → full-page với textarea + cards + Print button
