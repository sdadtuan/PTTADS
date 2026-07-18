# AEO Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây AEO Workspace cho SP/AM: query bank per customer, AI scan brand visibility + gap, generate Q&A content + FAQ schema JSON-LD, track improvement theo thời gian.

**Architecture:** Module `crm_aeo.py` với 3 bảng (queries → scans → content). Flask routes wired vào `app.py`. Full-page workspace tại `/crm/aeo`. AEO summary section trong workflow page khi lifecycle có `service_slug = "dich-vu-aeo"`.

**Tech Stack:** Python 3, Flask 3, SQLite (`get_connection()`), Anthropic SDK trực tiếp (`claude-haiku-4-5-20251001`).

## Global Constraints

- `from __future__ import annotations` ở đầu mỗi file Python mới.
- Inline imports bên trong route functions (pattern của app.py).
- Auth: page route dùng `_ensure_crm_session_html()`.
- AI model: `claude-haiku-4-5-20251001`, synchronous, fail silent (`run_scan` → `""`, `generate_content` → `{}`).
- `_ts()` = `datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")`.
- Không thêm feature ngoài spec.
- Chạy tests: `python3 -m pytest`, import: `python3 -c "import app; print('OK')"`.
- Không có git — không commit.
- `brand_visible` được parse từ chuỗi `brand_visible: yes` (case-insensitive) trong response → `1`, ngược lại `0`.
- `gap_notes` = text sau `## Content Gap` header trong scan response.
- `qa_text` = text sau `## Q&A Pairs` header trong content response (raw markdown).
- `schema_json` = text sau `## FAQ Schema JSON-LD` header trong content response (raw JSON string).

---

## File Map

| File | Loại | Nhiệm vụ |
|------|------|---------|
| `crm_aeo.py` | Tạo mới | Schema + 8 public functions |
| `tests/test_crm_aeo.py` | Tạo mới | ~14 tests TDD, SQLite in-memory |
| `app.py` | Sửa nhỏ (4 điểm) | +import dòng 337, +schema init dòng 2282, +5 routes, +aeo_stats trong workflow page |
| `templates/crm_aeo.html` | Tạo mới | AEO Workspace full-page |
| `templates/crm_service_workflow.html` | Sửa nhỏ | +AEO section trước `</div>{% endblock %}` cuối admin_main |

---

### Task 1: `crm_aeo.py` + TDD tests

**Files:**
- Create: `crm_aeo.py`
- Create: `tests/test_crm_aeo.py`

**Interfaces — Produces:**
- `ensure_schema(conn: sqlite3.Connection) -> None`
- `add_query(conn, customer_id: int, query_text: str, brand_name: str, *, lifecycle_id: int | None = None, notes: str = "") -> int`
- `list_queries(conn, customer_id: int) -> list[dict]` — mỗi dict: `{id, query_text, brand_name, notes, lifecycle_id, created_at, last_scan_date: str|None, brand_visible: int|None}`
- `delete_query(conn, query_id: int) -> None`
- `run_scan(conn, query_id: int) -> str` — fail silent → `""`
- `get_scan_history(conn, query_id: int) -> list[dict]`
- `generate_content(conn, query_id: int) -> dict` — fail silent → `{}`
- `get_latest_content(conn, query_id: int) -> dict | None`

- [ ] **Step 1: Tạo file test với failing tests**

```python
# tests/test_crm_aeo.py
from __future__ import annotations
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import crm_aeo as m


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_slug TEXT NOT NULL DEFAULT ''
        );
    """)
    m.ensure_schema(conn)
    return conn


def _seed_customer(conn: sqlite3.Connection) -> int:
    conn.execute("INSERT INTO crm_customers (name) VALUES (?)", ("Test KH",))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestEnsureSchema(unittest.TestCase):
    def test_creates_tables(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_aeo_queries", tables)
        self.assertIn("crm_aeo_scans", tables)
        self.assertIn("crm_aeo_content", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        m.ensure_schema(conn)  # second call must not raise
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crm_aeo_queries").fetchone()[0], 0)


class TestAddQuery(unittest.TestCase):
    def test_returns_int_id(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "SEO local giá?", "PTTCOM")
        self.assertIsInstance(qid, int)
        self.assertGreater(qid, 0)

    def test_lifecycle_id_nullable(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "Agency uy tín?", "PTTCOM", lifecycle_id=None)
        row = conn.execute("SELECT lifecycle_id FROM crm_aeo_queries WHERE id = ?", (qid,)).fetchone()
        self.assertIsNone(row["lifecycle_id"])

    def test_notes_stored(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "query?", "Brand", notes="note123")
        row = conn.execute("SELECT notes FROM crm_aeo_queries WHERE id = ?", (qid,)).fetchone()
        self.assertEqual(row["notes"], "note123")


class TestListQueries(unittest.TestCase):
    def test_empty_returns_empty_list(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        self.assertEqual(m.list_queries(conn, cid), [])

    def test_returns_last_scan_date_and_brand_visible(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute(
            "INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)",
            (qid, "resp", 1, "gap", "2026-06-01 00:00:00"),
        )
        conn.commit()
        rows = m.list_queries(conn, cid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["brand_visible"], 1)
        self.assertEqual(rows[0]["last_scan_date"], "2026-06-01 00:00:00")

    def test_no_scan_returns_none_fields(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        m.add_query(conn, cid, "q?", "B")
        rows = m.list_queries(conn, cid)
        self.assertIsNone(rows[0]["last_scan_date"])
        self.assertIsNone(rows[0]["brand_visible"])


class TestDeleteQuery(unittest.TestCase):
    def test_deletes_query(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        m.delete_query(conn, qid)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crm_aeo_queries WHERE id = ?", (qid,)).fetchone()[0], 0)

    def test_cascade_deletes_scans(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute(
            "INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)",
            (qid, "r", 0, "g", "2026-06-01"),
        )
        conn.commit()
        m.delete_query(conn, qid)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crm_aeo_scans WHERE query_id = ?", (qid,)).fetchone()[0], 0)


class TestRunScan(unittest.TestCase):
    def test_no_api_key_returns_empty(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = Exception("no key")
            result = m.run_scan(conn, qid)
        self.assertEqual(result, "")

    def test_saves_scan_on_success(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="## Câu trả lời AI điển hình\nAI says.\n## Phân tích Brand Visibility\nbrand_visible: yes\nB xuất hiện.\n## Content Gap\nCần thêm FAQ.")]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = m.run_scan(conn, qid)
        self.assertIn("brand_visible", result)
        row = conn.execute("SELECT brand_visible, gap_notes FROM crm_aeo_scans WHERE query_id = ?", (qid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["brand_visible"], 1)
        self.assertIn("FAQ", row["gap_notes"])


class TestGetScanHistory(unittest.TestCase):
    def test_no_scans_returns_empty(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        self.assertEqual(m.get_scan_history(conn, qid), [])

    def test_returns_order_by_id_desc(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute("INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)", (qid, "r1", 0, "g1", "2026-06-01"))
        conn.execute("INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)", (qid, "r2", 1, "g2", "2026-06-02"))
        conn.commit()
        history = m.get_scan_history(conn, qid)
        self.assertEqual(history[0]["ai_response"], "r2")


class TestGenerateContent(unittest.TestCase):
    def test_no_api_key_returns_empty_dict(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = Exception("no key")
            result = m.generate_content(conn, qid)
        self.assertEqual(result, {})

    def test_saves_content_on_success(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute("INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)", (qid, "r", 1, "Cần FAQ", "2026-06-01"))
        conn.commit()
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text='## Q&A Pairs\nQ: Hỏi?\nA: Trả lời B.\n## FAQ Schema JSON-LD\n{"@context":"https://schema.org"}')]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = m.generate_content(conn, qid)
        self.assertIn("qa_text", result)
        self.assertIn("schema_json", result)
        row = conn.execute("SELECT qa_text, schema_json FROM crm_aeo_content WHERE query_id = ?", (qid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertIn("Hỏi", row["qa_text"])


class TestGetLatestContent(unittest.TestCase):
    def test_no_content_returns_none(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        self.assertIsNone(m.get_latest_content(conn, qid))

    def test_returns_latest_by_id_desc(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute("INSERT INTO crm_aeo_content (query_id, qa_text, schema_json, created_at) VALUES (?,?,?,?)", (qid, "qa1", "{}", "2026-06-01"))
        conn.execute("INSERT INTO crm_aeo_content (query_id, qa_text, schema_json, created_at) VALUES (?,?,?,?)", (qid, "qa2", "{}", "2026-06-02"))
        conn.commit()
        result = m.get_latest_content(conn, qid)
        self.assertIsNotNone(result)
        self.assertEqual(result["qa_text"], "qa2")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận fail**

```bash
python3 -m pytest tests/test_crm_aeo.py -v
```
Expected: `ModuleNotFoundError: No module named 'crm_aeo'`

- [ ] **Step 3: Tạo `crm_aeo.py`**

```python
# crm_aeo.py
from __future__ import annotations
import re
import sqlite3
from datetime import datetime


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS crm_aeo_queries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id  INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            lifecycle_id INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE SET NULL,
            query_text   TEXT NOT NULL DEFAULT '',
            brand_name   TEXT NOT NULL DEFAULT '',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_queries_customer ON crm_aeo_queries (customer_id);

        CREATE TABLE IF NOT EXISTS crm_aeo_scans (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id      INTEGER NOT NULL REFERENCES crm_aeo_queries(id) ON DELETE CASCADE,
            ai_response   TEXT NOT NULL DEFAULT '',
            brand_visible INTEGER NOT NULL DEFAULT 0,
            gap_notes     TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_scans_query ON crm_aeo_scans (query_id);

        CREATE TABLE IF NOT EXISTS crm_aeo_content (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id    INTEGER NOT NULL REFERENCES crm_aeo_queries(id) ON DELETE CASCADE,
            qa_text     TEXT NOT NULL DEFAULT '',
            schema_json TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_content_query ON crm_aeo_content (query_id);
    """)


def add_query(
    conn: sqlite3.Connection,
    customer_id: int,
    query_text: str,
    brand_name: str,
    *,
    lifecycle_id: int | None = None,
    notes: str = "",
) -> int:
    cur = conn.execute(
        "INSERT INTO crm_aeo_queries (customer_id, lifecycle_id, query_text, brand_name, notes, created_at) VALUES (?,?,?,?,?,?)",
        (customer_id, lifecycle_id, query_text, brand_name, notes, _ts()),
    )
    conn.commit()
    return cur.lastrowid


def list_queries(conn: sqlite3.Connection, customer_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT q.id, q.query_text, q.brand_name, q.notes, q.lifecycle_id, q.created_at,
               s.created_at AS last_scan_date,
               s.brand_visible
        FROM crm_aeo_queries q
        LEFT JOIN crm_aeo_scans s ON s.id = (
            SELECT id FROM crm_aeo_scans WHERE query_id = q.id ORDER BY id DESC LIMIT 1
        )
        WHERE q.customer_id = ?
        ORDER BY q.id
        """,
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_query(conn: sqlite3.Connection, query_id: int) -> None:
    conn.execute("DELETE FROM crm_aeo_queries WHERE id = ?", (query_id,))
    conn.commit()


def _extract_section(text: str, header: str) -> str:
    pattern = rf"## {re.escape(header)}\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def run_scan(conn: sqlite3.Connection, query_id: int) -> str:
    try:
        import anthropic
        row = conn.execute(
            "SELECT query_text, brand_name, notes FROM crm_aeo_queries WHERE id = ?",
            (query_id,),
        ).fetchone()
        if row is None:
            return ""
        query_text = row["query_text"]
        brand_name = row["brand_name"]
        notes = row["notes"] or "Không có thêm thông tin"

        prompt = f"""Bạn là chuyên gia AEO phân tích cách AI engine trả lời câu hỏi.

Query: "{query_text}"
Brand cần monitor: "{brand_name}"
Thông tin brand: "{notes}"

Hãy thực hiện 3 bước sau, dùng đúng header ##:

## Câu trả lời AI điển hình
[Viết câu trả lời mà ChatGPT hoặc Perplexity thường trả lời cho query này, dựa trên kiến thức phổ biến. 3-5 câu.]

## Phân tích Brand Visibility
brand_visible: [yes/no]
[Giải thích: {brand_name} có xuất hiện trong câu trả lời trên không, và tại sao. 2-3 câu.]

## Content Gap
[Liệt kê 2-3 loại nội dung/tín hiệu mà {brand_name} đang thiếu để AI engine đề cập đến khi trả lời query này.]"""

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        output = resp.content[0].text.strip()

        visibility_section = _extract_section(output, "Phân tích Brand Visibility")
        brand_visible = 1 if re.search(r"brand_visible\s*:\s*yes", visibility_section, re.IGNORECASE) else 0
        gap_notes = _extract_section(output, "Content Gap")

        conn.execute(
            "INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)",
            (query_id, output, brand_visible, gap_notes, _ts()),
        )
        conn.commit()
        return output
    except Exception:
        return ""


def get_scan_history(conn: sqlite3.Connection, query_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, ai_response, brand_visible, gap_notes, created_at FROM crm_aeo_scans WHERE query_id = ? ORDER BY id DESC",
        (query_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def generate_content(conn: sqlite3.Connection, query_id: int) -> dict:
    try:
        import anthropic
        q_row = conn.execute(
            "SELECT query_text, brand_name FROM crm_aeo_queries WHERE id = ?",
            (query_id,),
        ).fetchone()
        if q_row is None:
            return {}
        query_text = q_row["query_text"]
        brand_name = q_row["brand_name"]

        scan = conn.execute(
            "SELECT gap_notes FROM crm_aeo_scans WHERE query_id = ? ORDER BY id DESC LIMIT 1",
            (query_id,),
        ).fetchone()
        gap_notes = scan["gap_notes"] if scan else "Không có phân tích gap"

        prompt = f"""Bạn là chuyên gia viết content AEO.

Query: "{query_text}"
Brand: "{brand_name}"
Content gap cần fill: "{gap_notes}"

Hãy tạo:

## Q&A Pairs
[3-5 cặp câu hỏi – câu trả lời, mỗi cặp giúp {brand_name} xuất hiện khi AI engine trả lời câu hỏi liên quan. Format:
Q: [câu hỏi]
A: [câu trả lời 2-3 câu, tự nhiên, có đề cập {brand_name}]]

## FAQ Schema JSON-LD
[JSON-LD hợp lệ dùng schema.org/FAQPage, bao gồm tất cả Q&A pairs ở trên. Chỉ trả về JSON thuần, không thêm markdown code block.]"""

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        output = resp.content[0].text.strip()

        qa_text = _extract_section(output, "Q&A Pairs")
        schema_json = _extract_section(output, "FAQ Schema JSON-LD")

        ts = _ts()
        conn.execute(
            "INSERT INTO crm_aeo_content (query_id, qa_text, schema_json, created_at) VALUES (?,?,?,?)",
            (query_id, qa_text, schema_json, ts),
        )
        conn.commit()
        return {"qa_text": qa_text, "schema_json": schema_json, "created_at": ts}
    except Exception:
        return {}


def get_latest_content(conn: sqlite3.Connection, query_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, qa_text, schema_json, created_at FROM crm_aeo_content WHERE query_id = ? ORDER BY id DESC LIMIT 1",
        (query_id,),
    ).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 4: Chạy tests để xác nhận pass**

```bash
python3 -m pytest tests/test_crm_aeo.py -v
```
Expected: 14 tests PASS

- [ ] **Step 5: Xác nhận import sạch**

```bash
python3 -c "import crm_aeo; print('OK')"
```

---

### Task 2: Wire `app.py` — import + schema init + 5 routes + aeo_stats trong workflow

**Files:**
- Modify: `app.py` (4 điểm độc lập)

**Interfaces:**
- Consumes từ Task 1:
  - `crm_aeo.ensure_schema(conn)`
  - `crm_aeo.add_query(conn, customer_id, query_text, brand_name, *, lifecycle_id, notes) -> int`
  - `crm_aeo.list_queries(conn, customer_id) -> list[dict]`
  - `crm_aeo.delete_query(conn, query_id) -> None`
  - `crm_aeo.run_scan(conn, query_id) -> str`
  - `crm_aeo.generate_content(conn, query_id) -> dict`

- [ ] **Step 1: Thêm import tại dòng 337 (sau `_ensure_customer_brief_schema`)**

Tìm:
```python
from crm_customer_brief import ensure_schema as _ensure_customer_brief_schema
```
Thêm ngay sau:
```python
from crm_aeo import ensure_schema as _ensure_aeo_schema
```

- [ ] **Step 2: Thêm schema init tại dòng ~2282 (sau `_ensure_customer_brief_schema(conn)`)**

Tìm:
```python
    _ensure_customer_brief_schema(conn)
```
Thêm ngay sau:
```python
    _ensure_aeo_schema(conn)
```

- [ ] **Step 3: Thêm page route `/crm/aeo`**

Thêm sau `api_crm_customer_brief_latest` (khoảng dòng 4953). Route này load tất cả customers cho dropdown và queries của customer đang chọn:

```python
@app.get("/crm/aeo")
def crm_aeo_page() -> Any:
    redir = _ensure_crm_session_html()
    if redir is not None:
        return redir
    from crm_aeo import list_queries as _aeo_list
    customer_id = _opt_pos_int(request.args.get("customer_id"))
    with get_connection() as conn:
        all_customers = [
            dict(r) for r in conn.execute(
                "SELECT id, name, company FROM crm_customers ORDER BY name"
            ).fetchall()
        ]
        queries = []
        selected_customer = None
        if customer_id:
            row = conn.execute(
                "SELECT id, name, company FROM crm_customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
            selected_customer = dict(row) if row else None
            if selected_customer:
                queries = _aeo_list(conn, customer_id)
    return render_template(
        "crm_aeo.html",
        all_customers=all_customers,
        selected_customer=selected_customer,
        queries=queries,
        customer_id=customer_id,
        **_admin_page_template_kwargs(),
    )
```

- [ ] **Step 4: Thêm 4 API routes**

Thêm ngay sau page route vừa tạo:

```python
@app.post("/api/crm/aeo/queries")
def api_crm_aeo_add_query() -> Any:
    from crm_aeo import add_query as _aeo_add
    body = request.get_json(silent=True) or {}
    customer_id = _opt_pos_int(body.get("customer_id"))
    query_text = str(body.get("query_text", "")).strip()[:500]
    brand_name = str(body.get("brand_name", "")).strip()[:200]
    lifecycle_id = _opt_pos_int(body.get("lifecycle_id"))
    notes = str(body.get("notes", "")).strip()[:1000]
    if not customer_id or not query_text or not brand_name:
        return jsonify({"error": "Thiếu customer_id, query_text hoặc brand_name"}), 400
    with get_connection() as conn:
        qid = _aeo_add(conn, customer_id, query_text, brand_name, lifecycle_id=lifecycle_id, notes=notes)
    return jsonify({"id": qid})


@app.delete("/api/crm/aeo/queries/<int:query_id>")
def api_crm_aeo_delete_query(query_id: int) -> Any:
    from crm_aeo import delete_query as _aeo_del
    with get_connection() as conn:
        _aeo_del(conn, query_id)
    return jsonify({})


@app.post("/api/crm/aeo/queries/<int:query_id>/scan")
def api_crm_aeo_scan(query_id: int) -> Any:
    from crm_aeo import run_scan as _aeo_scan, get_scan_history as _aeo_history
    with get_connection() as conn:
        output = _aeo_scan(conn, query_id)
        history = _aeo_history(conn, query_id)
    latest = history[0] if history else {}
    return jsonify({
        "ai_response": output,
        "brand_visible": latest.get("brand_visible", 0),
        "gap_notes": latest.get("gap_notes", ""),
        "created_at": latest.get("created_at", ""),
    })


@app.post("/api/crm/aeo/queries/<int:query_id>/content")
def api_crm_aeo_content(query_id: int) -> Any:
    from crm_aeo import generate_content as _aeo_gen
    with get_connection() as conn:
        result = _aeo_gen(conn, query_id)
    return jsonify(result)
```

- [ ] **Step 5: Thêm `aeo_stats` vào `crm_service_workflow_page`**

Trong hàm `crm_service_workflow_page` (line ~16859), tìm dòng:
```python
        from crm_svc_kpi import get_lifecycle_staff_metrics as _kpi_staff
        lifecycle_staff = _kpi_staff(conn, lifecycle_id)
```
Thêm ngay sau (trước khi đóng `with get_connection()`):
```python
        aeo_stats = None
        if lc["service_slug"] == "dich-vu-aeo":
            from crm_aeo import list_queries as _aeo_list
            aeo_qs = _aeo_list(conn, lc["customer_id"]) if lc.get("customer_id") else []
            total_q = len(aeo_qs)
            visible_q = sum(1 for q in aeo_qs if q.get("brand_visible") == 1)
            aeo_stats = {"total": total_q, "visible": visible_q}
```

Trong `render_template("crm_service_workflow.html", ...)` (line ~16917), thêm:
```python
        aeo_stats=aeo_stats,
```
vào danh sách kwargs.

- [ ] **Step 6: Xác nhận**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_aeo.py -v
```
Expected: import OK, 14 tests PASS

---

### Task 3: `crm_aeo.html` — AEO Workspace full-page

**Files:**
- Create: `templates/crm_aeo.html`

**Interfaces:**
- Consumes: `all_customers` (list[dict]: id, name, company), `selected_customer` (dict|None), `queries` (list[dict]), `customer_id` (int|None)
- API: POST `/api/crm/aeo/queries`, DELETE `/api/crm/aeo/queries/<id>`, POST `/api/crm/aeo/queries/<id>/scan`, POST `/api/crm/aeo/queries/<id>/content`

- [ ] **Step 1: Tạo template**

```html
{# templates/crm_aeo.html #}
{% extends "admin_layout.html" %}
{% block title %}AEO Workspace{% endblock %}
{% block meta_robots %}noindex, nofollow{% endblock %}
{% block admin_page_title %}AEO Workspace{% endblock %}

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
  {# Add query form #}
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem 1.25rem;margin-bottom:1.25rem;">
    <div style="font-weight:600;font-size:.875rem;margin-bottom:.6rem;">+ Thêm câu hỏi mới</div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:flex-start;">
      <input id="new-query-text" type="text" placeholder="Câu hỏi người dùng hay hỏi AI..."
             style="flex:2;min-width:200px;padding:.45rem .7rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.875rem;" />
      <input id="new-brand-name" type="text" placeholder="Tên brand cần monitor"
             style="flex:1;min-width:140px;padding:.45rem .7rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.875rem;" />
      <input id="new-query-notes" type="text" placeholder="Ghi chú thêm về brand (tuỳ chọn)"
             style="flex:1;min-width:140px;padding:.45rem .7rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.875rem;" />
      <button onclick="addQuery({{ selected_customer.id }})"
              style="padding:.45rem 1rem;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-size:.875rem;cursor:pointer;white-space:nowrap;">
        Thêm
      </button>
    </div>
  </div>

  {# Query list #}
  {% if queries %}
  {# Summary bar #}
  {% set visible_count = queries | selectattr('brand_visible', 'equalto', 1) | list | length %}
  {% set scanned_count = queries | selectattr('last_scan_date') | list | length %}
  <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:.6rem 1rem;margin-bottom:.75rem;font-size:.85rem;color:#1e40af;">
    Brand visible: <strong>{{ visible_count }}/{{ queries|length }}</strong> queries đã scan
    &nbsp;·&nbsp; Chưa scan: <strong>{{ queries|length - scanned_count }}</strong>
  </div>

  <table style="width:100%;border-collapse:collapse;font-size:.875rem;">
    <thead>
      <tr style="border-bottom:2px solid #e2e8f0;text-align:left;">
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Câu hỏi</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Brand</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Lần scan</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Visibility</th>
        <th style="padding:.5rem .75rem;color:#6b7280;font-weight:600;">Hành động</th>
      </tr>
    </thead>
    <tbody id="aeo-query-list">
    {% for q in queries %}
    <tr id="row-{{ q.id }}" style="border-bottom:1px solid #f1f5f9;">
      <td style="padding:.6rem .75rem;max-width:300px;">{{ q.query_text }}</td>
      <td style="padding:.6rem .75rem;color:#6b7280;">{{ q.brand_name }}</td>
      <td style="padding:.6rem .75rem;color:#6b7280;font-size:.8rem;">
        {{ q.last_scan_date or 'Chưa scan' }}
      </td>
      <td style="padding:.6rem .75rem;">
        {% if q.last_scan_date is none %}
        <span style="color:#9ca3af;">—</span>
        {% elif q.brand_visible == 1 %}
        <span style="color:#16a34a;font-weight:600;">✓ Có</span>
        {% else %}
        <span style="color:#dc2626;font-weight:600;">✗ Chưa</span>
        {% endif %}
      </td>
      <td style="padding:.6rem .75rem;white-space:nowrap;">
        <button onclick="scanQuery({{ q.id }})" id="scan-btn-{{ q.id }}"
                style="padding:.25rem .6rem;font-size:.78rem;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;cursor:pointer;margin-right:.25rem;">
          {% if q.last_scan_date %}Scan lại{% else %}Scan{% endif %}
        </button>
        <button onclick="toggleResult({{ q.id }})"
                style="padding:.25rem .6rem;font-size:.78rem;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;cursor:pointer;margin-right:.25rem;">
          Kết quả
        </button>
        <button onclick="generateContent({{ q.id }})" id="content-btn-{{ q.id }}"
                style="padding:.25rem .6rem;font-size:.78rem;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;cursor:pointer;margin-right:.25rem;">
          Content
        </button>
        <button onclick="deleteQuery({{ q.id }})"
                style="padding:.25rem .6rem;font-size:.78rem;background:#fff;border:1px solid #fca5a5;color:#dc2626;border-radius:4px;cursor:pointer;">
          Xoá
        </button>
      </td>
    </tr>
    {# Result slide-down #}
    <tr id="result-{{ q.id }}" hidden>
      <td colspan="5" style="padding:0 .75rem .75rem;">
        <div id="result-body-{{ q.id }}" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:.75rem;font-size:.8rem;"></div>
      </td>
    </tr>
    {# Content slide-down #}
    <tr id="content-{{ q.id }}" hidden>
      <td colspan="5" style="padding:0 .75rem .75rem;">
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:.75rem;font-size:.8rem;">
          <div style="font-weight:600;color:#14532d;margin-bottom:.5rem;">Q&A Pairs</div>
          <pre id="content-qa-{{ q.id }}" style="white-space:pre-wrap;margin:0 0 .75rem;font-family:inherit;"></pre>
          <div style="font-weight:600;color:#14532d;margin-bottom:.5rem;">FAQ Schema JSON-LD
            <button onclick="copySchema({{ q.id }})"
                    style="margin-left:.5rem;padding:.15rem .5rem;font-size:.75rem;background:#fff;border:1px solid #bbf7d0;border-radius:3px;cursor:pointer;">
              Copy Schema
            </button>
          </div>
          <pre id="content-schema-{{ q.id }}" style="white-space:pre-wrap;margin:0;font-family:monospace;font-size:.75rem;background:#fff;padding:.5rem;border-radius:4px;"></pre>
        </div>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div style="text-align:center;padding:3rem;color:#9ca3af;font-size:.9rem;">
    Chưa có câu hỏi nào. Thêm câu hỏi đầu tiên ở trên.
  </div>
  {% endif %}
  {% else %}
  <div style="text-align:center;padding:3rem;color:#9ca3af;font-size:.9rem;">
    Chọn khách hàng để bắt đầu quản lý AEO queries.
  </div>
  {% endif %}

</div>
{% endblock %}

{% block admin_page_scripts %}
<script>
function addQuery(customerId) {
  var qt = document.getElementById('new-query-text').value.trim();
  var bn = document.getElementById('new-brand-name').value.trim();
  var notes = document.getElementById('new-query-notes').value.trim();
  if (!qt || !bn) { alert('Vui lòng nhập câu hỏi và tên brand.'); return; }
  fetch('/api/crm/aeo/queries', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({customer_id: customerId, query_text: qt, brand_name: bn, notes: notes}),
  }).then(function(r) { return r.json(); }).then(function() { location.reload(); }).catch(console.error);
}

function deleteQuery(queryId) {
  if (!confirm('Xoá câu hỏi này?')) return;
  fetch('/api/crm/aeo/queries/' + queryId, {method: 'DELETE'})
    .then(function() { location.reload(); }).catch(console.error);
}

function scanQuery(queryId) {
  var btn = document.getElementById('scan-btn-' + queryId);
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  fetch('/api/crm/aeo/queries/' + queryId + '/scan', {method: 'POST'})
    .then(function(r) { return r.json(); })
    .then(function(data) {
      renderResult(queryId, data);
      location.reload();
    })
    .catch(function(e) { console.error(e); if (btn) { btn.disabled = false; btn.textContent = 'Scan'; } });
}

function toggleResult(queryId) {
  var row = document.getElementById('result-' + queryId);
  if (!row) return;
  if (row.hidden) {
    var body = document.getElementById('result-body-' + queryId);
    if (body && !body.textContent.trim()) {
      body.textContent = 'Chưa có kết quả scan. Nhấn "Scan" để tạo kết quả.';
    }
    row.removeAttribute('hidden');
  } else {
    row.setAttribute('hidden', '');
  }
}

function renderResult(queryId, data) {
  var body = document.getElementById('result-body-' + queryId);
  if (!body) return;
  var text = data.ai_response || '';
  var visibility = data.brand_visible === 1 ? '✓ Brand XUẤT HIỆN' : '✗ Brand CHƯA xuất hiện';
  body.innerHTML = '<strong style="color:' + (data.brand_visible ? '#16a34a' : '#dc2626') + '">' + visibility + '</strong><br><br>' +
    '<pre style="white-space:pre-wrap;font-size:.78rem;margin:0;">' + escHtml(text) + '</pre>';
  var row = document.getElementById('result-' + queryId);
  if (row) row.removeAttribute('hidden');
}

function generateContent(queryId) {
  var btn = document.getElementById('content-btn-' + queryId);
  if (btn) { btn.disabled = true; btn.textContent = '⏳'; }
  fetch('/api/crm/aeo/queries/' + queryId + '/content', {method: 'POST'})
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var qaEl = document.getElementById('content-qa-' + queryId);
      var schemaEl = document.getElementById('content-schema-' + queryId);
      if (qaEl) qaEl.textContent = data.qa_text || '';
      if (schemaEl) schemaEl.textContent = data.schema_json || '';
      var row = document.getElementById('content-' + queryId);
      if (row) row.removeAttribute('hidden');
      if (btn) { btn.disabled = false; btn.textContent = 'Content'; }
    })
    .catch(function(e) { console.error(e); if (btn) { btn.disabled = false; btn.textContent = 'Content'; } });
}

function copySchema(queryId) {
  var el = document.getElementById('content-schema-' + queryId);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(function() { alert('Đã copy schema!'); }).catch(console.error);
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
</script>
{% endblock %}
```

- [ ] **Step 2: Xác nhận app import OK**

```bash
python3 -c "import app; print('OK')"
```

---

### Task 4: AEO section trong `crm_service_workflow.html`

**Files:**
- Modify: `templates/crm_service_workflow.html` (1 điểm — chèn trước `</script>` cuối file)

**Interfaces:**
- Consumes: `aeo_stats` từ route (dict `{total, visible}` hoặc `None`)
- Consumes: `lifecycle.customer_id` (từ `lifecycle` dict đã có trong template)
- Consumes: `lifecycle.service_slug` (để điều kiện hiển thị)

**Lưu ý:** Template hiện 931 dòng, kết thúc bằng `</script>` ở dòng 930. Phần HTML của admin_main kết thúc trước khối `<script>`. Tìm dòng bắt đầu khối script `// ─── Finance JS` hoặc `<script>` cuối — chèn HTML section AEO VÀO TRƯỚC đoạn `<script>`.

- [ ] **Step 1: Đọc cuối file để xác định chỗ chèn**

```bash
grep -n "<script>\|</div>.*endblock\|{% endblock %}" /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/templates/crm_service_workflow.html | tail -10
```

- [ ] **Step 2: Chèn AEO section vào template**

Tìm block staff section (dòng ~755-820 — phần `Nhân sự phụ trách`). Chèn ngay SAU phần staff section (trước `<script>` tag cuối cùng):

```html
{% if aeo_stats is not none %}
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem 1.25rem;margin-top:1rem;">
  <div style="font-weight:600;font-size:.875rem;color:#374151;margin-bottom:.6rem;">AEO Monitoring</div>
  <div style="display:flex;align-items:center;gap:1.5rem;font-size:.875rem;">
    <span>Queries đang track: <strong>{{ aeo_stats.total }}</strong></span>
    <span>Brand visible: <strong style="color:{% if aeo_stats.total > 0 and aeo_stats.visible == aeo_stats.total %}#16a34a{% elif aeo_stats.visible > 0 %}#d97706{% else %}#dc2626{% endif %};">
      {{ aeo_stats.visible }}/{{ aeo_stats.total }}
    </strong></span>
    <a href="/crm/aeo?customer_id={{ lifecycle.customer_id }}"
       style="font-size:.8rem;color:#3b82f6;text-decoration:none;">→ Mở AEO Workspace</a>
  </div>
</div>
{% endif %}
```

- [ ] **Step 3: Xác nhận**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_aeo.py -v
```
Expected: import OK, 14 tests PASS

---

## Kiểm tra cuối

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_aeo.py -v
```

Test thủ công:
1. Mở `/crm/aeo` → chọn khách hàng → thêm câu hỏi + brand
2. Click **Scan** → spinner → kết quả hiện ra (brand visible badge + AI response)
3. Click **Content** → Q&A pairs + schema JSON-LD + Copy Schema button
4. Mở workflow page của lifecycle `dich-vu-aeo` → thấy AEO Monitoring section với link workspace
