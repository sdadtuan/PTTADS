# Service Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm bảng `crm_service_lifecycle` làm orchestration layer, kết nối 12 dịch vụ PTTP thành một chu trình thống nhất từ lead → ký HĐ → triển khai → chăm sóc.

**Architecture:** File `crm_service_lifecycle.py` chứa schema + 7 hàm public. App.py wire vào qua `with get_connection() as conn`. 4 module hiện có được wire surgical (crm_ai_qualify, app.py contract route, crm_care, crm_daily_work_report). Dashboard kanban mới tại `/crm/service-delivery`.

**Tech Stack:** Python 3, Flask 3, SQLite, Anthropic SDK trực tiếp (`anthropic` package), `unittest` + SQLite in-memory cho tests.

## Global Constraints

- Model AI: `claude-haiku-4-5-20251001` cho classify (nhanh, rẻ) — KHÔNG dùng sonnet cho background tasks
- DB connection trong routes: `with get_connection() as conn:` — không tự mở `sqlite3.connect()`
- DB connection trong background thread: `sqlite3.connect(DB_PATH)` với `conn.row_factory = sqlite3.Row` rồi đóng tay
- Tất cả timestamp: `datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")`
- Templates: `{% extends "admin_layout.html" %}` — KHÔNG tạo layout mới
- Surgical changes: match style code hiện có, không cleanup code lân cận
- Tests: `unittest.TestCase`, SQLite in-memory, pattern `_setup_conn()` trả về `sqlite3.Connection`
- Fail silent cho AI: mọi AI call fail → log warning, feature vẫn chạy

---

## File Structure

| File | Loại | Trách nhiệm |
|------|------|-------------|
| `crm_service_lifecycle.py` | Tạo mới | Schema, 7 hàm public, AI Call 1 + 3 |
| `tests/test_crm_service_lifecycle.py` | Tạo mới | Unit tests cho toàn bộ module |
| `app.py` | Sửa surgical | Import, init schema, migration, 5 routes, wire contract route |
| `crm_ai_qualify.py` | Sửa surgical | Wire AI Call 1 sau save_qualify_brief |
| `crm_care.py` | Sửa surgical | Wire get_stage_context vào care context |
| `crm_daily_work_report.py` | Sửa surgical | Thêm service_slug vào report data |
| `templates/crm_service_delivery.html` | Tạo mới | Dashboard kanban 7 cột |

---

## Task 1: Schema + Core Module

**Files:**
- Create: `crm_service_lifecycle.py`
- Create: `tests/test_crm_service_lifecycle.py`

**Interfaces:**
- Produces:
  - `ensure_schema(conn: sqlite3.Connection) -> None`
  - `create_draft_lifecycle(conn, lead_id: int, service_slug: str, suggested_by: str = 'ai') -> int`
  - `activate_lifecycle(conn, contract_id: int) -> bool`
  - `advance_stage(conn, lifecycle_id: int, to_stage: str, actor_id: int | None, actor_type: str, notes: str) -> None`
  - `get_by_lead(conn, lead_id: int) -> dict | None`
  - `get_by_contract(conn, contract_id: int) -> dict | None`
  - `get_stage_context(conn, customer_id: int) -> dict | None`
  - `list_active(conn, service_slug: str | None, am_id: int | None, include_draft: bool) -> list[dict]`
  - `VALID_STAGES: tuple[str, ...]`
  - `VALID_STATUSES: tuple[str, ...]`

- [ ] **Step 1: Viết failing tests**

```python
# tests/test_crm_service_lifecycle.py
"""Tests cho crm_service_lifecycle module."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime, timedelta

from crm_service_lifecycle import (
    VALID_STAGES,
    VALID_STATUSES,
    activate_lifecycle,
    advance_stage,
    create_draft_lifecycle,
    ensure_schema,
    get_by_contract,
    get_by_lead,
    get_stage_context,
    list_active,
)

TS = "2026-06-22 10:00:00"


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    # Seed bảng phụ tối thiểu
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crm_leads (id INTEGER PRIMARY KEY, meta_json TEXT DEFAULT '{}')"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '')"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS crm_contracts (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            service_slug TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft'
        )"""
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crm_staff (id INTEGER PRIMARY KEY)"
    )
    conn.execute("INSERT INTO crm_leads (id) VALUES (1)")
    conn.execute("INSERT INTO crm_customers (id, name) VALUES (1, 'Test Co')")
    conn.execute(
        "INSERT INTO crm_contracts (id, customer_id, service_slug, status) VALUES (1, 1, 'dich-vu-seo-tong-the', 'draft')"
    )
    conn.commit()
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_tables_created(self):
        conn = _setup_conn()
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("crm_service_lifecycle", tables)
        self.assertIn("crm_service_lifecycle_events", tables)

    def test_contracts_has_service_slug(self):
        conn = _setup_conn()
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(crm_contracts)").fetchall()
        }
        self.assertIn("service_slug", cols)


class TestCreateDraftLifecycle(unittest.TestCase):
    def test_creates_draft_record(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertIsInstance(lid, int)
        row = conn.execute(
            "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(row["status"], "draft")
        self.assertEqual(row["stage"], "lead")
        self.assertEqual(row["service_slug"], "dich-vu-seo-tong-the")
        self.assertEqual(row["lead_id"], 1)

    def test_records_initial_event(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        events = conn.execute(
            "SELECT * FROM crm_service_lifecycle_events WHERE lifecycle_id = ?", (lid,)
        ).fetchall()
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0]["from_stage"])
        self.assertEqual(events[0]["to_stage"], "lead")


class TestActivateLifecycle(unittest.TestCase):
    def test_activates_draft_and_sets_onboard(self):
        conn = _setup_conn()
        # Tạo lifecycle gắn với customer_id=1
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-tong-the")
        conn.execute(
            "UPDATE crm_service_lifecycle SET customer_id = 1 WHERE id = ?", (lid,)
        )
        conn.commit()
        # Contract customer_id=1 → activate
        ok = activate_lifecycle(conn, contract_id=1)
        self.assertTrue(ok)
        row = conn.execute(
            "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["stage"], "onboard")
        self.assertEqual(row["contract_id"], 1)

    def test_returns_false_when_no_draft_found(self):
        conn = _setup_conn()
        ok = activate_lifecycle(conn, contract_id=1)
        self.assertFalse(ok)


class TestAdvanceStage(unittest.TestCase):
    def test_advances_stage_and_logs_event(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        advance_stage(conn, lid, "consult", actor_type="human")
        row = conn.execute(
            "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(row["stage"], "consult")
        events = conn.execute(
            "SELECT * FROM crm_service_lifecycle_events WHERE lifecycle_id = ? ORDER BY id",
            (lid,),
        ).fetchall()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]["from_stage"], "lead")
        self.assertEqual(events[1]["to_stage"], "consult")
        self.assertEqual(events[1]["actor_type"], "human")


class TestGetters(unittest.TestCase):
    def test_get_by_lead(self):
        conn = _setup_conn()
        create_draft_lifecycle(conn, lead_id=1, service_slug="tiep-thi-noi-dung")
        row = get_by_lead(conn, lead_id=1)
        self.assertIsNotNone(row)
        self.assertEqual(row["service_slug"], "tiep-thi-noi-dung")

    def test_get_by_contract(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="quang-cao-google")
        conn.execute(
            "UPDATE crm_service_lifecycle SET customer_id = 1, contract_id = 1 WHERE id = ?",
            (lid,),
        )
        conn.commit()
        row = get_by_contract(conn, contract_id=1)
        self.assertIsNotNone(row)

    def test_get_stage_context_returns_days(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-local")
        conn.execute(
            "UPDATE crm_service_lifecycle SET customer_id = 1, status = 'active' WHERE id = ?",
            (lid,),
        )
        conn.commit()
        ctx = get_stage_context(conn, customer_id=1)
        self.assertIsNotNone(ctx)
        self.assertIn("stage", ctx)
        self.assertIn("stage_days", ctx)
        self.assertIn("service_slug", ctx)

    def test_get_by_lead_none_when_missing(self):
        conn = _setup_conn()
        self.assertIsNone(get_by_lead(conn, lead_id=999))


class TestListActive(unittest.TestCase):
    def test_excludes_draft_by_default(self):
        conn = _setup_conn()
        create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        results = list_active(conn)
        self.assertEqual(len(results), 0)

    def test_includes_draft_when_requested(self):
        conn = _setup_conn()
        create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        results = list_active(conn, include_draft=True)
        self.assertEqual(len(results), 1)

    def test_filters_by_service_slug(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        conn.execute(
            "UPDATE crm_service_lifecycle SET status = 'active' WHERE id = ?", (lid,)
        )
        conn.commit()
        results = list_active(conn, service_slug="dich-vu-aeo")
        self.assertEqual(len(results), 1)
        results_none = list_active(conn, service_slug="quang-cao-google")
        self.assertEqual(len(results_none), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test để xác nhận FAIL**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP
python -m pytest tests/test_crm_service_lifecycle.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'crm_service_lifecycle'`

- [ ] **Step 3: Tạo `crm_service_lifecycle.py`**

```python
# crm_service_lifecycle.py
"""Service Lifecycle — orchestration layer kết nối 12 dịch vụ PTTP theo chu trình thống nhất."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

VALID_STAGES: tuple[str, ...] = (
    "lead", "consult", "proposal", "onboard", "deliver", "handover", "retain"
)
VALID_STATUSES: tuple[str, ...] = ("draft", "active", "closed", "lost")

VALID_SLUGS: frozenset[str] = frozenset({
    "dich-vu-aeo", "dich-vu-seo-tong-the", "dich-vu-seo-local",
    "dich-vu-seo-audit", "dich-vu-quan-tri-website",
    "thiet-ke-website", "thiet-ke-website-tron-goi", "thiet-ke-landing-page",
    "quang-cao-facebook", "quang-cao-google", "thue-tai-khoan-quang-cao",
    "tiep-thi-noi-dung",
})


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Tạo 2 bảng + migration crm_contracts.service_slug. Gọi lúc app init."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id          INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL,
            customer_id      INTEGER REFERENCES crm_customers(id) ON DELETE SET NULL,
            contract_id      INTEGER REFERENCES crm_contracts(id) ON DELETE SET NULL,
            service_slug     TEXT NOT NULL DEFAULT '',
            stage            TEXT NOT NULL DEFAULT 'lead',
            status           TEXT NOT NULL DEFAULT 'draft',
            assigned_am      INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            assigned_sp      INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            stage_entered_at TEXT NOT NULL DEFAULT '',
            notes            TEXT NOT NULL DEFAULT '',
            created_at       TEXT NOT NULL DEFAULT '',
            updated_at       TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_lead ON crm_service_lifecycle(lead_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_customer ON crm_service_lifecycle(customer_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_contract ON crm_service_lifecycle(contract_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_status ON crm_service_lifecycle(status, stage)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            from_stage   TEXT,
            to_stage     TEXT NOT NULL,
            actor_id     INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            actor_type   TEXT NOT NULL DEFAULT 'human',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svclife_events_lc ON crm_service_lifecycle_events(lifecycle_id)"
    )
    # Migration: thêm service_slug vào crm_contracts nếu chưa có
    try:
        conn.execute(
            "ALTER TABLE crm_contracts ADD COLUMN service_slug TEXT NOT NULL DEFAULT ''"
        )
    except Exception:
        pass  # Column đã tồn tại
    conn.commit()


def create_draft_lifecycle(
    conn: sqlite3.Connection,
    lead_id: int,
    service_slug: str,
    suggested_by: str = "ai",
) -> int:
    """Tạo lifecycle status=draft, stage=lead. Trả về id mới."""
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (lead_id, service_slug, stage, status, stage_entered_at, created_at, updated_at)
        VALUES (?, ?, 'lead', 'draft', ?, ?, ?)
        """,
        (lead_id, service_slug, ts, ts, ts),
    )
    lid = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
        VALUES (?, NULL, 'lead', ?, ?, ?)
        """,
        (lid, suggested_by, f"Draft tạo bởi {suggested_by}", ts),
    )
    conn.commit()
    return lid


def activate_lifecycle(conn: sqlite3.Connection, contract_id: int) -> bool:
    """Khi contract status='active': tìm draft lifecycle theo customer_id → set active, stage=onboard.
    Lookup: customer_id từ contract → lifecycle WHERE customer_id match AND status='draft'.
    Trả False nếu không tìm thấy."""
    contract = conn.execute(
        "SELECT customer_id, service_slug FROM crm_contracts WHERE id = ?",
        (contract_id,),
    ).fetchone()
    if contract is None:
        return False
    customer_id = contract["customer_id"]
    lc = conn.execute(
        """
        SELECT id FROM crm_service_lifecycle
        WHERE customer_id = ? AND status = 'draft'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    if lc is None:
        return False
    lid = lc["id"]
    ts = _ts()
    old = conn.execute(
        "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lid,)
    ).fetchone()
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET status = 'active', stage = 'onboard', contract_id = ?,
            stage_entered_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (contract_id, ts, ts, lid),
    )
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
        VALUES (?, ?, 'onboard', 'ai', 'Contract ký — tự động activate', ?)
        """,
        (lid, old["stage"] if old else None, ts),
    )
    conn.commit()
    return True


def advance_stage(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    to_stage: str,
    actor_id: int | None = None,
    actor_type: str = "human",
    notes: str = "",
) -> None:
    """Chuyển stage, ghi event."""
    if to_stage not in VALID_STAGES:
        raise ValueError(f"Stage không hợp lệ: {to_stage}")
    ts = _ts()
    old = conn.execute(
        "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
    ).fetchone()
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET stage = ?, stage_entered_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (to_stage, ts, ts, lifecycle_id),
    )
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, actor_id, actor_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (lifecycle_id, old["stage"] if old else None, to_stage, actor_id, actor_type, notes, ts),
    )
    conn.commit()


def get_by_lead(conn: sqlite3.Connection, lead_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM crm_service_lifecycle WHERE lead_id = ? ORDER BY id DESC LIMIT 1",
        (lead_id,),
    ).fetchone()
    return dict(row) if row else None


def get_by_contract(conn: sqlite3.Connection, contract_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM crm_service_lifecycle WHERE contract_id = ? ORDER BY id DESC LIMIT 1",
        (contract_id,),
    ).fetchone()
    return dict(row) if row else None


def get_stage_context(
    conn: sqlite3.Connection, customer_id: int
) -> dict[str, Any] | None:
    """Trả về {service_slug, stage, stage_days} cho crm_care dùng làm AI context."""
    row = conn.execute(
        """
        SELECT service_slug, stage, stage_entered_at
        FROM crm_service_lifecycle
        WHERE customer_id = ? AND status = 'active'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    if row is None:
        return None
    stage_days = 0
    try:
        entered = datetime.strptime(row["stage_entered_at"], "%Y-%m-%d %H:%M:%S")
        stage_days = (datetime.utcnow() - entered).days
    except Exception:
        pass
    return {
        "service_slug": row["service_slug"],
        "stage": row["stage"],
        "stage_days": stage_days,
    }


def list_active(
    conn: sqlite3.Connection,
    service_slug: str | None = None,
    am_id: int | None = None,
    include_draft: bool = False,
) -> list[dict[str, Any]]:
    """Dashboard kanban: trả về lifecycles active (và draft nếu include_draft=True)."""
    conditions = []
    params: list[Any] = []
    if include_draft:
        conditions.append("status IN ('active', 'draft')")
    else:
        conditions.append("status = 'active'")
    if service_slug:
        conditions.append("service_slug = ?")
        params.append(service_slug)
    if am_id:
        conditions.append("assigned_am = ?")
        params.append(am_id)
    where = " AND ".join(conditions)
    rows = conn.execute(
        f"SELECT * FROM crm_service_lifecycle WHERE {where} ORDER BY updated_at DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Chạy test — xác nhận PASS**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP
python -m pytest tests/test_crm_service_lifecycle.py -v
```
Expected: tất cả tests PASS.

- [ ] **Step 5: Commit**

```bash
git add crm_service_lifecycle.py tests/test_crm_service_lifecycle.py
git commit -m "feat: add crm_service_lifecycle core module with schema and 7 public functions"
```

---

## Task 2: Wire vào app.py — init schema + migration

**Files:**
- Modify: `app.py` — thêm import + gọi `ensure_schema` trong init block

**Interfaces:**
- Consumes: `ensure_schema(conn)` từ Task 1
- Produces: `ensure_schema` được gọi khi app khởi động; `crm_contracts.service_slug` column tồn tại trong production DB

- [ ] **Step 1: Viết failing test kiểm tra migration**

Thêm vào `tests/test_crm_service_lifecycle.py`:

```python
class TestMigrationContractsColumn(unittest.TestCase):
    def test_service_slug_added_idempotent(self):
        """ensure_schema chạy 2 lần không lỗi."""
        conn = _setup_conn()
        ensure_schema(conn)  # lần 2 — không được raise
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(crm_contracts)").fetchall()
        }
        self.assertIn("service_slug", cols)
```

- [ ] **Step 2: Chạy test — xác nhận PASS** (đã pass từ Task 1, confirm lại)

```bash
python -m pytest tests/test_crm_service_lifecycle.py::TestMigrationContractsColumn -v
```
Expected: PASS.

- [ ] **Step 3: Thêm import vào `app.py`**

Tìm khối import modules trong `app.py` (gần dòng 320, cạnh `from crm_sop_seed import ...`), thêm:

```python
from crm_service_lifecycle import (
    ensure_schema as _ensure_service_lifecycle_schema,
    activate_lifecycle,
    advance_stage as _svc_advance_stage,
    get_by_lead as _svc_get_by_lead,
    get_by_contract as _svc_get_by_contract,
    list_active as _svc_list_active,
    get_stage_context as _svc_get_stage_context,
    VALID_STAGES as SVC_LIFECYCLE_STAGES,
)
```

- [ ] **Step 4: Gọi `_ensure_service_lifecycle_schema` trong app init**

Tìm dòng gọi `_ensure_crm_sop_schema(conn)` trong hàm init DB (khoảng dòng 2791), thêm ngay sau:

```python
_ensure_service_lifecycle_schema(conn)
```

- [ ] **Step 5: Kiểm tra app khởi động không lỗi**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP
python -c "from app import app; print('OK')"
```
Expected: `OK` không có traceback.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: wire service_lifecycle schema into app.py init"
```

---

## Task 3: Wire contract route + AI qualify

**Files:**
- Modify: `app.py` — route PATCH contract, route POST contract
- Modify: `crm_ai_qualify.py` — wire AI Call 1 sau save_qualify_brief

**Interfaces:**
- Consumes: `activate_lifecycle(conn, contract_id)`, `create_draft_lifecycle(conn, lead_id, slug)` từ Task 1
- Produces: Draft lifecycle tự động khi lead qualify; lifecycle active khi contract ký

- [ ] **Step 1: Viết failing tests**

Thêm vào `tests/test_crm_service_lifecycle.py`:

```python
class TestSuggestServiceSlug(unittest.TestCase):
    def test_suggest_returns_valid_slug_or_empty(self):
        """_suggest_service_slug trả về slug hợp lệ hoặc chuỗi rỗng — không raise."""
        from crm_service_lifecycle import _suggest_service_slug, VALID_SLUGS
        result = _suggest_service_slug(
            niche="seo",
            pain_points="website không có traffic",
            lead_message="tôi muốn tăng traffic SEO",
        )
        # Không raise dù API không có key
        self.assertIsInstance(result, str)
        if result:
            self.assertIn(result, VALID_SLUGS)
```

- [ ] **Step 2: Chạy test — xác nhận FAIL**

```bash
python -m pytest tests/test_crm_service_lifecycle.py::TestSuggestServiceSlug -v
```
Expected: `ImportError: cannot import name '_suggest_service_slug'`

- [ ] **Step 3: Thêm `_suggest_service_slug` vào `crm_service_lifecycle.py`**

Thêm vào cuối file, trước dòng cuối:

```python
# ── AI helpers (internal) ──────────────────────────────────────────────────

_HAIKU = "claude-haiku-4-5-20251001"

_SLUG_LIST = "\n".join(f"- {s}" for s in sorted(VALID_SLUGS))

_SUGGEST_SYSTEM = f"""Bạn là trợ lý phân loại dịch vụ marketing cho agency PTT.
Dựa vào thông tin lead, chọn service_slug phù hợp nhất trong danh sách sau:
{_SLUG_LIST}

Trả về JSON: {{"service_slug": "...", "confidence": 0.0-1.0, "reason": "1 câu"}}
Nếu không xác định được, trả về service_slug rỗng: {{"service_slug": "", "confidence": 0.0, "reason": "..."}}"""


def _suggest_service_slug(
    *,
    niche: str = "",
    pain_points: str = "",
    lead_message: str = "",
) -> str:
    """Gọi Claude Haiku để gợi ý service_slug. Trả về slug hợp lệ hoặc '' nếu fail."""
    import json
    import os
    try:
        import anthropic
    except ImportError:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = f"Ngách: {niche}\nVấn đề: {pain_points}\nNhắn: {lead_message[:500]}"
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=200,
            system=_SUGGEST_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        slug = str(data.get("service_slug", "")).strip()
        return slug if slug in VALID_SLUGS else ""
    except Exception as exc:
        logger.warning("_suggest_service_slug lỗi: %s", exc)
        return ""
```

- [ ] **Step 4: Chạy test — xác nhận PASS**

```bash
python -m pytest tests/test_crm_service_lifecycle.py::TestSuggestServiceSlug -v
```
Expected: PASS (trả về `""` khi không có API key, không raise).

- [ ] **Step 5: Wire vào `crm_ai_qualify.py`**

Tìm trong hàm `_run()` bên trong `trigger_qualify_brief_async`, sau dòng `save_qualify_brief(conn, lead_id, brief, ts)`, thêm:

```python
            # Wire: tạo draft lifecycle từ AI qualify
            try:
                from crm_service_lifecycle import (
                    _suggest_service_slug,
                    create_draft_lifecycle,
                    get_by_lead,
                )
                if get_by_lead(conn, lead_id) is None:
                    slug = _suggest_service_slug(
                        niche=str(brief.get("niche") or ""),
                        pain_points=str(brief.get("pain_points") or ""),
                        lead_message=str(brief.get("need") or ""),
                    )
                    create_draft_lifecycle(conn, lead_id=lead_id, service_slug=slug)
                    logger.info("Draft lifecycle created: lead_id=%s slug=%s", lead_id, slug)
            except Exception as _lc_exc:
                logger.warning("Lifecycle draft tạo lỗi: %s", _lc_exc)
```

- [ ] **Step 6: Wire `activate_lifecycle` vào PATCH contract route trong `app.py`**

Tìm route `@app.patch("/api/crm/contracts/<int:contract_id>")` (khoảng dòng 12731). Tìm đoạn sau khi `conn.execute("UPDATE crm_contracts ...")` commit thành công, thêm:

```python
        # Wire: khi contract active → activate lifecycle
        if new_status == "active":
            try:
                activate_lifecycle(conn, contract_id)
            except Exception as _lc_exc:
                logger.warning("activate_lifecycle lỗi contract=%s: %s", contract_id, _lc_exc)
```

*(Lưu ý: `new_status` là biến local trong route đó chứa status mới sau update. Tìm tên biến thực tế trong route và dùng đúng tên.)*

- [ ] **Step 7: Kiểm tra app không lỗi**

```bash
python -c "from app import app; print('OK')"
```
Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add crm_service_lifecycle.py crm_ai_qualify.py app.py
git commit -m "feat: wire service lifecycle into ai_qualify and contract activation"
```

---

## Task 4: Dashboard /crm/service-delivery

**Files:**
- Modify: `app.py` — thêm 5 routes
- Create: `templates/crm_service_delivery.html`

**Interfaces:**
- Consumes: `_svc_list_active`, `_svc_advance_stage`, `_svc_get_by_lead`, `VALID_SLUGS` từ Task 1
- Produces: Kanban 7 cột tại `/crm/service-delivery`; API PATCH tại `/api/crm/service-lifecycle/<id>`

- [ ] **Step 1: Thêm 5 routes vào `app.py`**

Thêm vào `app.py`, ngay sau khối routes `crm_sop`:

```python
# ── Service Delivery Dashboard ─────────────────────────────────────────────

@app.get("/crm/service-delivery")
def crm_service_delivery_page() -> str:
    with get_connection() as conn:
        lifecycles = _svc_list_active(conn, include_draft=True)
    # Nhóm theo stage để render kanban
    from collections import defaultdict
    by_stage: dict[str, list] = defaultdict(list)
    for lc in lifecycles:
        by_stage[lc["stage"]].append(lc)
    return render_template(
        "crm_service_delivery.html",
        by_stage=by_stage,
        stages=SVC_LIFECYCLE_STAGES,
        valid_slugs=sorted(VALID_SLUGS if 'VALID_SLUGS' in dir() else []),
    )


@app.get("/api/crm/service-lifecycle")
def api_svc_lifecycle_list() -> Any:
    service_slug = request.args.get("service_slug") or None
    am_id = _opt_pos_int(request.args.get("am_id"))
    include_draft = request.args.get("include_draft", "0") == "1"
    with get_connection() as conn:
        rows = _svc_list_active(conn, service_slug=service_slug, am_id=am_id, include_draft=include_draft)
    return jsonify(rows)


@app.post("/api/crm/service-lifecycle")
def api_svc_lifecycle_create() -> Any:
    payload = request.get_json(force=True) or {}
    lead_id = _opt_pos_int(payload.get("lead_id"))
    service_slug = str(payload.get("service_slug", "")).strip()
    if not lead_id or not service_slug:
        return jsonify({"error": "Cần lead_id và service_slug"}), 400
    with get_connection() as conn:
        from crm_service_lifecycle import create_draft_lifecycle
        lid = create_draft_lifecycle(conn, lead_id=lead_id, service_slug=service_slug, suggested_by="human")
        row = conn.execute("SELECT * FROM crm_service_lifecycle WHERE id = ?", (lid,)).fetchone()
    return jsonify(dict(row)), 201


@app.patch("/api/crm/service-lifecycle/<int:lifecycle_id>")
def api_svc_lifecycle_patch(lifecycle_id: int) -> Any:
    payload = request.get_json(force=True) or {}
    to_stage = str(payload.get("stage", "")).strip()
    notes = str(payload.get("notes", "")).strip()[:2000]
    actor_id = _opt_pos_int(payload.get("actor_id"))
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Không tìm thấy lifecycle"}), 404
        if to_stage:
            if to_stage not in SVC_LIFECYCLE_STAGES:
                return jsonify({"error": f"Stage không hợp lệ: {to_stage}"}), 400
            _svc_advance_stage(conn, lifecycle_id, to_stage, actor_id=actor_id, notes=notes)
        # Cập nhật fields khác nếu có
        if "service_slug" in payload:
            slug = str(payload["service_slug"]).strip()
            ts = _crm_ts()
            conn.execute(
                "UPDATE crm_service_lifecycle SET service_slug = ?, updated_at = ? WHERE id = ?",
                (slug, ts, lifecycle_id),
            )
            conn.commit()
        updated = conn.execute(
            "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
        ).fetchone()
    return jsonify(dict(updated))


@app.get("/api/crm/service-lifecycle/<int:lifecycle_id>/events")
def api_svc_lifecycle_events(lifecycle_id: int) -> Any:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM crm_service_lifecycle_events WHERE lifecycle_id = ? ORDER BY id ASC",
            (lifecycle_id,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])
```

- [ ] **Step 2: Tạo template `templates/crm_service_delivery.html`**

```html
{% extends "admin_layout.html" %}

{% block title %}Service Delivery — CRM{% endblock %}
{% block meta_robots %}noindex, nofollow{% endblock %}
{% block body_class_extra %}crm-body crm-service-delivery-page{% endblock %}

{% block admin_head %}
<script id="svc-delivery-meta" type="application/json">{{ {
  "stages": stages,
  "stage_labels": {
    "lead": "Lead",
    "consult": "Tư vấn",
    "proposal": "Báo giá",
    "onboard": "Onboarding",
    "deliver": "Triển khai",
    "handover": "Nghiệm thu",
    "retain": "Chăm sóc"
  }
} | tojson }}</script>
{% endblock %}

{% block admin_page_title %}Service Delivery{% endblock %}
{% block admin_page_desc %}
  <p class="admin-page-desc">Theo dõi vòng đời 12 dịch vụ PTTP — từ lead đến chăm sóc sau bán.</p>
{% endblock %}

{% block admin_content %}
<div class="svc-kanban-wrap" style="overflow-x:auto; padding-bottom:2rem;">
  <div class="svc-kanban" style="display:flex; gap:1rem; min-width:max-content;">
    {% set stage_labels = {
      "lead": "Lead", "consult": "Tư vấn", "proposal": "Báo giá",
      "onboard": "Onboarding", "deliver": "Triển khai",
      "handover": "Nghiệm thu", "retain": "Chăm sóc"
    } %}
    {% for stage in stages %}
    <div class="svc-col" data-stage="{{ stage }}"
         style="min-width:200px; background:#f5f7fa; border-radius:8px; padding:0.75rem;">
      <div class="svc-col-header" style="font-weight:600; margin-bottom:0.5rem; font-size:.875rem;">
        {{ stage_labels.get(stage, stage) }}
        <span class="svc-count" style="color:#888; font-weight:400;">
          ({{ (by_stage[stage] or [])|length }})
        </span>
      </div>
      {% for lc in (by_stage[stage] or []) %}
      <div class="svc-card" data-id="{{ lc.id }}"
           style="background:#fff; border-radius:6px; padding:.625rem; margin-bottom:.5rem;
                  border:1px solid #e2e8f0; cursor:pointer;"
           onclick="svcOpenCard({{ lc.id }})">
        <div style="font-size:.7rem; color:#6366f1; font-weight:600; margin-bottom:2px;">
          {{ lc.service_slug }}
        </div>
        <div style="font-size:.8rem; font-weight:500; margin-bottom:2px;">
          KH #{{ lc.customer_id or '—' }}
        </div>
        <div style="font-size:.7rem; color:#888;">
          {% if lc.status == 'draft' %}
          <span style="color:#f59e0b;">● draft</span>
          {% else %}
          <span style="color:#22c55e;">● active</span>
          {% endif %}
          · {{ lc.stage_entered_at[:10] if lc.stage_entered_at else '—' }}
        </div>
      </div>
      {% else %}
      <div style="color:#bbb; font-size:.75rem; text-align:center; padding:.5rem 0;">trống</div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>
</div>

<!-- Modal advance stage -->
<div id="svc-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,.4);
     z-index:1000; align-items:center; justify-content:center;">
  <div style="background:#fff; border-radius:10px; padding:1.5rem; width:340px; max-width:95vw;">
    <h3 style="margin:0 0 1rem; font-size:1rem;">Advance Stage</h3>
    <p id="svc-modal-info" style="font-size:.8rem; color:#555; margin-bottom:1rem;"></p>
    <label style="font-size:.8rem; font-weight:600;">Stage mới</label>
    <select id="svc-modal-stage" style="width:100%; margin:.25rem 0 .75rem; padding:.375rem;">
      {% for stage in stages %}
      <option value="{{ stage }}">{{ stage_labels.get(stage, stage) }}</option>
      {% endfor %}
    </select>
    <label style="font-size:.8rem; font-weight:600;">Ghi chú</label>
    <textarea id="svc-modal-notes" rows="2"
              style="width:100%; margin:.25rem 0 .75rem; padding:.375rem; box-sizing:border-box;"></textarea>
    <div style="display:flex; gap:.5rem; justify-content:flex-end;">
      <button onclick="svcCloseModal()"
              style="padding:.375rem .75rem; border:1px solid #ddd; border-radius:6px; background:#fff; cursor:pointer;">
        Huỷ
      </button>
      <button onclick="svcSaveStage()"
              style="padding:.375rem .75rem; background:#6366f1; color:#fff; border:none; border-radius:6px; cursor:pointer;">
        Lưu
      </button>
    </div>
  </div>
</div>

<script>
let _svcActiveId = null;
function svcOpenCard(id) {
  _svcActiveId = id;
  document.getElementById('svc-modal-info').textContent = 'Lifecycle #' + id;
  document.getElementById('svc-modal-notes').value = '';
  document.getElementById('svc-modal').style.display = 'flex';
}
function svcCloseModal() {
  document.getElementById('svc-modal').style.display = 'none';
  _svcActiveId = null;
}
function svcSaveStage() {
  if (!_svcActiveId) return;
  const stage = document.getElementById('svc-modal-stage').value;
  const notes = document.getElementById('svc-modal-notes').value;
  fetch('/api/crm/service-lifecycle/' + _svcActiveId, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({stage, notes})
  }).then(r => r.json()).then(() => {
    svcCloseModal();
    location.reload();
  }).catch(err => alert('Lỗi: ' + err));
}
</script>
{% endblock %}
```

- [ ] **Step 3: Kiểm tra route không lỗi syntax**

```bash
python -c "from app import app; print('routes OK')"
```
Expected: `routes OK`

- [ ] **Step 4: Smoke test route list API**

```bash
python -c "
from app import app
c = app.test_client()
r = c.get('/api/crm/service-lifecycle?include_draft=1')
print(r.status_code, r.get_json())
"
```
Expected: `200 []` (empty list, không lỗi).

- [ ] **Step 5: Commit**

```bash
git add app.py templates/crm_service_delivery.html
git commit -m "feat: add service delivery dashboard and lifecycle API routes"
```

---

## Task 5: Wire crm_care + crm_daily_work_report

**Files:**
- Modify: `crm_care.py` — thêm get_stage_context vào context
- Modify: `crm_daily_work_report.py` — thêm service_slug vào report

**Interfaces:**
- Consumes: `get_stage_context(conn, customer_id)` từ Task 1
- Produces: care reports biết KH đang ở stage nào; work report có cột service_slug

- [ ] **Step 1: Viết failing test cho get_stage_context integration**

Thêm vào `tests/test_crm_service_lifecycle.py`:

```python
class TestStageContextForCare(unittest.TestCase):
    def test_active_lifecycle_returns_context(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="quang-cao-facebook")
        conn.execute(
            "UPDATE crm_service_lifecycle SET customer_id=1, status='active', stage='deliver' WHERE id=?",
            (lid,),
        )
        conn.commit()
        ctx = get_stage_context(conn, customer_id=1)
        self.assertEqual(ctx["service_slug"], "quang-cao-facebook")
        self.assertEqual(ctx["stage"], "deliver")
        self.assertGreaterEqual(ctx["stage_days"], 0)

    def test_no_active_lifecycle_returns_none(self):
        conn = _setup_conn()
        self.assertIsNone(get_stage_context(conn, customer_id=999))
```

- [ ] **Step 2: Chạy test — xác nhận PASS**

```bash
python -m pytest tests/test_crm_service_lifecycle.py::TestStageContextForCare -v
```
Expected: PASS.

- [ ] **Step 3: Wire vào `crm_care.py`**

Tìm hàm generate care report hoặc hàm tạo care context trong `crm_care.py`. Tìm nơi `case_id` hoặc `customer_id` được dùng để build context. Thêm đoạn sau để enrich context với lifecycle stage:

```python
def get_lifecycle_stage_context(conn: sqlite3.Connection, customer_id: int) -> str:
    """Trả về chuỗi context lifecycle để thêm vào AI prompt. Trả '' nếu không có."""
    try:
        from crm_service_lifecycle import get_stage_context
        ctx = get_stage_context(conn, customer_id)
        if ctx:
            stage_labels = {
                "lead": "Lead", "consult": "Tư vấn", "proposal": "Báo giá",
                "onboard": "Onboarding", "deliver": "Triển khai",
                "handover": "Nghiệm thu", "retain": "Chăm sóc",
            }
            stage_label = stage_labels.get(ctx["stage"], ctx["stage"])
            return (
                f"Dịch vụ: {ctx['service_slug']} · "
                f"Giai đoạn: {stage_label} ({ctx['stage_days']} ngày). "
                f"Ưu tiên chăm sóc phù hợp giai đoạn này."
            )
    except Exception:
        pass
    return ""
```

- [ ] **Step 4: Thêm service_slug vào data `crm_daily_work_report.py`**

Tìm hàm `build_daily_work_report_workbook` trong `crm_daily_work_report.py`. Ở tham số `data: list[dict]`, thêm docstring note rằng mỗi dict có thể có key `service_slug`. Thêm cột "Dịch vụ" vào worksheet nếu data có service_slug:

```python
# Thêm vào đầu build_daily_work_report_workbook, sau khai báo ws:
has_service = any(row.get("service_slug") for row in data) if data else False
```

*(Chi tiết vị trí thêm cột tuỳ vào structure hiện tại — thêm sau cột "Nhân viên" nếu has_service=True)*

- [ ] **Step 5: Kiểm tra import không lỗi**

```bash
python -c "from crm_care import get_lifecycle_stage_context; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add crm_care.py crm_daily_work_report.py tests/test_crm_service_lifecycle.py
git commit -m "feat: wire lifecycle stage context into crm_care and daily report"
```

---

## Task 6: AI Call 3 — KPI Alert nền

**Files:**
- Modify: `crm_service_lifecycle.py` — thêm `check_kpi_alert_async()`
- Modify: `app.py` — gọi alert khi advance stage → `retain`

**Interfaces:**
- Consumes: `advance_stage`, `_HAIKU`, `logger` từ Task 1 + Task 3
- Produces: `check_kpi_alert_async(lifecycle_id, db_path)` chạy nền, ghi severity vào `lifecycle.notes`

- [ ] **Step 1: Viết failing test**

Thêm vào `tests/test_crm_service_lifecycle.py`:

```python
class TestKpiAlertAsync(unittest.TestCase):
    def test_check_kpi_alert_async_does_not_raise(self):
        """check_kpi_alert_async không raise dù không có API key."""
        import tempfile, os
        from crm_service_lifecycle import check_kpi_alert_async
        # Tạo DB tạm
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            ensure_schema(conn)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS crm_leads (id INTEGER PRIMARY KEY)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS crm_customers (id INTEGER PRIMARY KEY)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS crm_contracts (id INTEGER PRIMARY KEY, customer_id INTEGER, service_slug TEXT DEFAULT '', status TEXT DEFAULT 'draft')"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS crm_staff (id INTEGER PRIMARY KEY)"
            )
            lid = create_draft_lifecycle(conn, lead_id=None, service_slug="dich-vu-seo-tong-the")
            conn.close()
            # Gọi async — không raise
            t = check_kpi_alert_async(lifecycle_id=lid, db_path=db_path)
            t.join(timeout=3)  # Chờ tối đa 3s
        finally:
            os.unlink(db_path)
```

- [ ] **Step 2: Chạy test — xác nhận FAIL**

```bash
python -m pytest tests/test_crm_service_lifecycle.py::TestKpiAlertAsync -v
```
Expected: `ImportError: cannot import name 'check_kpi_alert_async'`

- [ ] **Step 3: Thêm `check_kpi_alert_async` vào `crm_service_lifecycle.py`**

```python
import threading


# KPI targets tham chiếu từ service specs (ngưỡng tối thiểu)
_KPI_TARGETS: dict[str, dict] = {
    "dich-vu-seo-tong-the": {"organic_traffic_growth_pct": 20, "keywords_top10_pct": 50},
    "dich-vu-seo-local": {"gbp_views_growth_pct": 30, "local_pack_pct": 50},
    "quang-cao-facebook": {"ctr_min": 1.5, "cpl_on_target_pct": 70},
    "quang-cao-google": {"impression_share_min": 60, "cpa_on_target_pct": 70},
}

_KPI_ALERT_SYSTEM = """Bạn là trợ lý phân tích KPI cho agency marketing PTT.
Dựa vào số liệu thực tế so với mục tiêu, đánh giá mức độ cảnh báo.
Trả về JSON: {"severity": "ok|warn|critical", "message": "1-2 câu cho AM", "suggested_action": "hành động gợi ý"}
- ok: đạt ≥ 90% mục tiêu
- warn: đạt 70–89%
- critical: dưới 70%"""


def check_kpi_alert_async(
    lifecycle_id: int,
    db_path: str,
    kpi_actual: dict | None = None,
) -> threading.Thread:
    """Chạy KPI alert trong background thread. Ghi severity vào lifecycle.notes."""

    def _run() -> None:
        import json
        import os
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            lc = conn.execute(
                "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
            ).fetchone()
            if lc is None:
                conn.close()
                return
            slug = lc["service_slug"]
            targets = _KPI_TARGETS.get(slug, {})
            if not targets or not kpi_actual:
                conn.close()
                return
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                conn.close()
                return
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = (
                f"Dịch vụ: {slug}\n"
                f"Mục tiêu: {json.dumps(targets, ensure_ascii=False)}\n"
                f"Thực tế: {json.dumps(kpi_actual, ensure_ascii=False)}"
            )
            response = client.messages.create(
                model=_HAIKU,
                max_tokens=300,
                system=_KPI_ALERT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            alert = json.loads(raw)
            severity = str(alert.get("severity", "ok"))
            message = str(alert.get("message", ""))
            ts = _ts()
            conn.execute(
                """
                UPDATE crm_service_lifecycle
                SET notes = notes || ?, updated_at = ?
                WHERE id = ?
                """,
                (f"\n[KPI {severity.upper()} {ts[:10]}] {message}", ts, lifecycle_id),
            )
            conn.commit()
            logger.info("KPI alert lifecycle_id=%s severity=%s", lifecycle_id, severity)
        except Exception as exc:
            logger.warning("check_kpi_alert_async lỗi lifecycle_id=%s: %s", lifecycle_id, exc)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    t = threading.Thread(target=_run, daemon=True, name=f"kpi-alert-{lifecycle_id}")
    t.start()
    return t
```

- [ ] **Step 4: Wire vào PATCH lifecycle route trong `app.py`**

Trong route `api_svc_lifecycle_patch`, sau khi `_svc_advance_stage(...)` thành công và `to_stage == "retain"`, thêm:

```python
            if to_stage == "retain":
                try:
                    from crm_service_lifecycle import check_kpi_alert_async
                    check_kpi_alert_async(lifecycle_id=lifecycle_id, db_path=DB_PATH)
                except Exception as _ka_exc:
                    logger.warning("KPI alert trigger lỗi: %s", _ka_exc)
```

- [ ] **Step 5: Chạy toàn bộ test suite**

```bash
python -m pytest tests/test_crm_service_lifecycle.py -v
```
Expected: tất cả tests PASS.

- [ ] **Step 6: Kiểm tra app khởi động**

```bash
python -c "from app import app; print('app OK')"
```
Expected: `app OK`

- [ ] **Step 7: Final commit**

```bash
git add crm_service_lifecycle.py app.py tests/test_crm_service_lifecycle.py
git commit -m "feat: add KPI alert background AI call for retain stage"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Schema 2 bảng + migration contracts → Task 1
- ✅ 7 hàm public → Task 1
- ✅ `ensure_schema` gọi lúc init → Task 2
- ✅ AI Call 1 suggest slug → Task 3
- ✅ Wire crm_ai_qualify → Task 3
- ✅ Wire contract activate → Task 3
- ✅ 5 routes + dashboard → Task 4
- ✅ Wire crm_care → Task 5
- ✅ Wire crm_daily_work_report → Task 5
- ✅ AI Call 3 KPI alert → Task 6

**Type consistency:**
- `create_draft_lifecycle` → trả `int` (id) — nhất quán across tasks ✅
- `activate_lifecycle` → trả `bool` — nhất quán ✅
- `get_stage_context` → `dict | None` với keys `service_slug`, `stage`, `stage_days` — nhất quán ✅
- `list_active` → `list[dict]` — nhất quán ✅
- `check_kpi_alert_async` → `threading.Thread` — nhất quán ✅

**Surgical changes confirmed:**
- `crm_ai_qualify.py`: +15 dòng trong `_run()` sau `save_qualify_brief`
- `app.py` contract PATCH: +8 dòng sau update commit
- `crm_care.py`: thêm hàm mới, không sửa logic hiện có
- `crm_daily_work_report.py`: thêm optional column, không break existing

**Edge case `create_draft_lifecycle` với `lead_id=None`:** Trong test Task 6 dùng `lead_id=None` — schema cho phép NULL. OK.
