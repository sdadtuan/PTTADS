# KPI Staff Performance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track Account Manager and Specialist KPI per-month with live metrics, monthly targets, and AI analysis — surfaced both in `/crm/staff-kpi` dashboard and in the lifecycle workflow page.

**Architecture:** New module `crm_svc_kpi.py` computes AM/SP metrics live from existing tables (`crm_svc_payments`, `crm_svc_expenses`, `crm_svc_tasks`, `crm_svc_risks`, `crm_service_lifecycle`). Two new tables store monthly targets and AI scan results. Routes added to `app.py`. Staff section added to the existing workflow page template.

**Tech Stack:** Python 3, Flask 3 monolith (`app.py`), SQLite with `get_connection()` context manager, `conn.row_factory = sqlite3.Row`, Anthropic SDK (`claude-haiku-4-5-20251001`), Jinja2 templates.

## Global Constraints

- Python: `from __future__ import annotations` at top of every `.py` file.
- Verify: `python3 -c "import app; print('OK')"` (no git in repo).
- Run tests: `python3 -m pytest tests/ -v` (not `pytest`).
- AI model: `claude-haiku-4-5-20251001`, synchronous, fail silent (return `""`).
- `_ts()`: `datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")`.
- Timestamps: `NOT NULL DEFAULT ''` on every table column.
- Auth in page routes: `redir = _ensure_admin_session_html(); if redir is not None: return redir`.
- Inline imports inside route functions (pattern already established).
- TDD: write failing test → verify FAIL → implement → verify PASS.
- No git commits (no git repo). Verify via `python3 -c "import app; print('OK')"`.
- `_opt_pos_int(val)` for parsing ints from JSON body.
- Template base: `{% extends "admin_layout.html" %}` + `{% block admin_main %}` + `**_admin_page_template_kwargs()`.

---

### Task 1: `crm_svc_kpi.py` + `tests/test_crm_svc_kpi.py` (TDD)

**Files:**
- Create: `crm_svc_kpi.py`
- Create: `tests/test_crm_svc_kpi.py`

**Interfaces:**
- Produces: `ensure_schema`, `get_am_metrics`, `get_sp_metrics`, `get_lifecycle_staff_metrics`, `set_target`, `get_targets`, `get_latest_kpi_scan`, `run_ai_kpi_scan` — used in Task 2 and Task 4.

---

- [ ] **Step 1: Write all failing tests**

Create `tests/test_crm_svc_kpi.py` with full content:

```python
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_svc_kpi import (
    ensure_schema,
    get_am_metrics,
    get_latest_kpi_scan,
    get_lifecycle_staff_metrics,
    get_sp_metrics,
    get_targets,
    run_ai_kpi_scan,
    set_target,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (1, 'Nguyễn AM', 1)")
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (2, 'Trần SP', 1)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount_vnd INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO crm_contracts (id, amount_vnd) VALUES (1, 10000000)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'deliver',
            status TEXT NOT NULL DEFAULT 'active',
            assigned_am INTEGER REFERENCES crm_staff(id),
            assigned_sp INTEGER REFERENCES crm_staff(id),
            contract_id INTEGER REFERENCES crm_contracts(id),
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        INSERT INTO crm_service_lifecycle
            (id, service_slug, stage, status, assigned_am, assigned_sp, contract_id,
             created_at, updated_at)
        VALUES (1, 'seo', 'deliver', 'active', 1, 2, 1,
                '2026-06-01 00:00:00', '2026-06-01 00:00:00')
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            received_on TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'khac',
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            expense_on TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            stage TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            is_done INTEGER NOT NULL DEFAULT 0,
            done_by INTEGER REFERENCES crm_staff(id),
            updated_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()
    ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_tables_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_svc_kpi_targets", tables)
        self.assertIn("crm_svc_kpi_scans", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        ensure_schema(conn)  # calling twice should not raise


class TestGetAmMetrics(unittest.TestCase):
    def test_no_data_all_zeros(self):
        conn = _setup_conn()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["received_revenue"], 0)
        self.assertEqual(result["active_services"], 1)  # lifecycle id=1 exists, active
        self.assertEqual(result["avg_margin_pct"], 0.0)
        self.assertGreaterEqual(result["outstanding"], 0)

    def test_received_revenue_correct_month(self):
        conn = _setup_conn()
        # Payment in target month — should count
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 3000000, '2026-06-10', 'received')"
        )
        # Payment in different month — should NOT count
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 1000000, '2026-05-15', 'received')"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["received_revenue"], 3000000)

    def test_pending_not_in_received_revenue(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 5000000, '2026-06-01', 'pending')"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["received_revenue"], 0)

    def test_avg_margin_pct_with_data(self):
        conn = _setup_conn()
        # received = 5M, expenses = 1M → profit = 4M → margin = 80%
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 5000000, '2026-06-01', 'received')"
        )
        conn.execute(
            "INSERT INTO crm_svc_expenses (lifecycle_id, title, category, amount_vnd, expense_on) "
            "VALUES (1, 'Chi phí', 'khac', 1000000, '2026-06-01')"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertAlmostEqual(result["avg_margin_pct"], 80.0, places=1)

    def test_outstanding_is_contract_minus_received(self):
        conn = _setup_conn()
        # contract = 10M (set in _setup_conn), received = 3M → outstanding = 7M
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 3000000, '2026-06-01', 'received')"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["outstanding"], 7000000)

    def test_no_active_lifecycles_avg_margin_zero(self):
        conn = _setup_conn()
        conn.execute(
            "UPDATE crm_service_lifecycle SET status = 'closed' WHERE id = 1"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["active_services"], 0)
        self.assertEqual(result["avg_margin_pct"], 0.0)


class TestGetSpMetrics(unittest.TestCase):
    def test_no_data_all_zeros(self):
        conn = _setup_conn()
        result = get_sp_metrics(conn, staff_id=2, year=2026, month=6)
        self.assertEqual(result["tasks_completed"], 0)
        self.assertEqual(result["tasks_pending"], 0)
        self.assertEqual(result["risks_resolved"], 0)

    def test_tasks_completed_correct_month(self):
        conn = _setup_conn()
        # Done in June — should count
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, done_by, updated_at) "
            "VALUES (1, 'deliver', 'Task A', 1, 2, '2026-06-10 10:00:00')"
        )
        # Done in May — should NOT count
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, done_by, updated_at) "
            "VALUES (1, 'deliver', 'Task B', 1, 2, '2026-05-20 10:00:00')"
        )
        conn.commit()
        result = get_sp_metrics(conn, staff_id=2, year=2026, month=6)
        self.assertEqual(result["tasks_completed"], 1)

    def test_tasks_pending_current_state(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, updated_at) "
            "VALUES (1, 'deliver', 'Pending Task', 0, '2026-06-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, done_by, updated_at) "
            "VALUES (1, 'deliver', 'Done Task', 1, 2, '2026-06-05 00:00:00')"
        )
        conn.commit()
        result = get_sp_metrics(conn, staff_id=2, year=2026, month=6)
        self.assertEqual(result["tasks_pending"], 1)

    def test_risks_resolved_correct_month(self):
        conn = _setup_conn()
        # Resolved in June — should count
        conn.execute(
            "INSERT INTO crm_svc_risks (lifecycle_id, title, is_active, updated_at) "
            "VALUES (1, 'Risk A', 0, '2026-06-15 00:00:00')"
        )
        # Resolved in May — should NOT count
        conn.execute(
            "INSERT INTO crm_svc_risks (lifecycle_id, title, is_active, updated_at) "
            "VALUES (1, 'Risk B', 0, '2026-05-10 00:00:00')"
        )
        # Still active — should NOT count
        conn.execute(
            "INSERT INTO crm_svc_risks (lifecycle_id, title, is_active, updated_at) "
            "VALUES (1, 'Risk C', 1, '2026-06-10 00:00:00')"
        )
        conn.commit()
        result = get_sp_metrics(conn, staff_id=2, year=2026, month=6)
        self.assertEqual(result["risks_resolved"], 1)


class TestGetLifecycleStaffMetrics(unittest.TestCase):
    def test_lifecycle_not_found(self):
        conn = _setup_conn()
        result = get_lifecycle_staff_metrics(conn, lifecycle_id=999)
        self.assertIsNone(result["am"])
        self.assertIsNone(result["sp"])

    def test_with_am_and_sp(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, done_by, updated_at) "
            "VALUES (1, 'deliver', 'Task', 1, 2, '2026-06-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 4000000, '2026-06-01', 'received')"
        )
        conn.execute(
            "INSERT INTO crm_svc_risks (lifecycle_id, title, is_active, updated_at) "
            "VALUES (1, 'Risk', 0, '2026-06-01 00:00:00')"
        )
        conn.commit()
        result = get_lifecycle_staff_metrics(conn, lifecycle_id=1)
        am = result["am"]
        sp = result["sp"]
        self.assertIsNotNone(am)
        self.assertEqual(am["id"], 1)
        self.assertEqual(am["name"], "Nguyễn AM")
        self.assertEqual(am["received_revenue"], 4000000)
        self.assertIsNotNone(sp)
        self.assertEqual(sp["id"], 2)
        self.assertEqual(sp["tasks_done"], 1)
        self.assertEqual(sp["risks_resolved"], 1)

    def test_no_am_no_sp(self):
        conn = _setup_conn()
        conn.execute(
            "UPDATE crm_service_lifecycle SET assigned_am = NULL, assigned_sp = NULL WHERE id = 1"
        )
        conn.commit()
        result = get_lifecycle_staff_metrics(conn, lifecycle_id=1)
        self.assertIsNone(result["am"])
        self.assertIsNone(result["sp"])


class TestTargets(unittest.TestCase):
    def test_set_and_get_target(self):
        conn = _setup_conn()
        set_target(conn, staff_id=1, role="am", metric_key="received_revenue",
                   year=2026, month=6, target_value=50000000.0)
        targets = get_targets(conn, staff_id=1, year=2026, month=6)
        self.assertAlmostEqual(targets["received_revenue"], 50000000.0)

    def test_overwrite_target(self):
        conn = _setup_conn()
        set_target(conn, 1, "am", "active_services", 2026, 6, 5.0)
        set_target(conn, 1, "am", "active_services", 2026, 6, 8.0)
        targets = get_targets(conn, 1, 2026, 6)
        self.assertAlmostEqual(targets["active_services"], 8.0)

    def test_get_targets_empty(self):
        conn = _setup_conn()
        targets = get_targets(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(targets, {})

    def test_different_month_not_returned(self):
        conn = _setup_conn()
        set_target(conn, 1, "am", "received_revenue", 2026, 5, 30000000.0)
        targets = get_targets(conn, 1, 2026, 6)
        self.assertNotIn("received_revenue", targets)


class TestGetLatestKpiScan(unittest.TestCase):
    def test_no_scan_returns_empty(self):
        conn = _setup_conn()
        result = get_latest_kpi_scan(conn, staff_id=1, role="am", year=2026, month=6)
        self.assertEqual(result, "")

    def test_returns_latest_scan(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans (staff_id, ai_output, role, year, month, created_at) "
            "VALUES (1, 'Phân tích A', 'am', 2026, 6, '2026-06-01 10:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans (staff_id, ai_output, role, year, month, created_at) "
            "VALUES (1, 'Phân tích B', 'am', 2026, 6, '2026-06-01 11:00:00')"
        )
        conn.commit()
        result = get_latest_kpi_scan(conn, staff_id=1, role="am", year=2026, month=6)
        self.assertEqual(result, "Phân tích B")

    def test_role_filter(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans (staff_id, ai_output, role, year, month, created_at) "
            "VALUES (1, 'AM scan', 'am', 2026, 6, '2026-06-01 10:00:00')"
        )
        conn.commit()
        self.assertEqual(get_latest_kpi_scan(conn, 1, "sp", 2026, 6), "")
        self.assertEqual(get_latest_kpi_scan(conn, 1, "am", 2026, 6), "AM scan")


class TestRunAiKpiScan(unittest.TestCase):
    def test_no_api_key_returns_empty(self):
        conn = _setup_conn()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_ai_kpi_scan(
            conn, staff_id=1, role="am", year=2026, month=6,
            context={
                "staff_name": "Test", "month": 6, "year": 2026,
                "received_revenue": 0, "active_services": 0,
                "avg_margin_pct": 0.0, "outstanding": 0,
                "target_received_revenue": 0, "target_active_services": 0,
                "target_avg_margin_pct": 0.0,
            },
        )
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP
python3 -m pytest tests/test_crm_svc_kpi.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'crm_svc_kpi'`

- [ ] **Step 3: Write `crm_svc_kpi.py`**

Create `/Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/crm_svc_kpi.py`:

```python
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)
_HAIKU = "claude-haiku-4-5-20251001"

_AM_PROMPT = """Bạn là chuyên gia phân tích hiệu suất nhân sự.

Nhân viên: {staff_name} (vai trò: Account Manager)
Kỳ: tháng {month}/{year}

KPI thực tế:
- Doanh thu thực nhận: {received_revenue:,} VND
- Số dịch vụ đang quản lý: {active_services}
- Biên lợi nhuận trung bình: {avg_margin_pct:.1f}%
- Công nợ tồn đọng: {outstanding:,} VND

Target tháng này:
- Doanh thu: {target_received_revenue:,} VND
- Số dịch vụ: {target_active_services}
- Biên lợi nhuận: {target_avg_margin_pct:.1f}%

Phân tích ngắn gọn (tối đa 200 từ):
1. So sánh actual vs target, highlight gap lớn nhất
2. Đánh giá điểm mạnh và điểm cần cải thiện
3. Gợi ý 2-3 hành động cụ thể cho tháng tới"""

_SP_PROMPT = """Bạn là chuyên gia phân tích hiệu suất nhân sự.

Nhân viên: {staff_name} (vai trò: Specialist/Thực thi)
Kỳ: tháng {month}/{year}

KPI thực tế:
- Tasks hoàn thành: {tasks_completed}
- Tasks đang chờ: {tasks_pending}
- Rủi ro đã xử lý: {risks_resolved}

Target tháng này:
- Tasks hoàn thành: {target_tasks_completed}
- Rủi ro xử lý: {target_risks_resolved}

Phân tích ngắn gọn (tối đa 200 từ):
1. So sánh actual vs target, highlight gap lớn nhất
2. Đánh giá tốc độ xử lý và backlog
3. Gợi ý 2-3 hành động ưu tiên cho tháng tới"""


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_kpi_targets (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id     INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
            role         TEXT NOT NULL DEFAULT 'am',
            metric_key   TEXT NOT NULL DEFAULT '',
            year         INTEGER NOT NULL,
            month        INTEGER NOT NULL,
            target_value REAL NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT '',
            UNIQUE(staff_id, metric_key, year, month)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_kpi_targets "
        "ON crm_svc_kpi_targets(staff_id, year, month)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_kpi_scans (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id   INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
            ai_output  TEXT NOT NULL DEFAULT '',
            role       TEXT NOT NULL DEFAULT 'am',
            year       INTEGER NOT NULL,
            month      INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_kpi_scans "
        "ON crm_svc_kpi_scans(staff_id, role, year, month)"
    )
    conn.commit()


def get_am_metrics(
    conn: sqlite3.Connection, staff_id: int, year: int, month: int
) -> dict[str, Any]:
    month_str = f"{year:04d}-{month:02d}"

    recv_row = conn.execute(
        """
        SELECT COALESCE(SUM(p.amount_vnd), 0)
        FROM crm_svc_payments p
        JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
        WHERE lc.assigned_am = ? AND p.status = 'received' AND p.received_on LIKE ?
        """,
        (staff_id, f"{month_str}%"),
    ).fetchone()
    received_revenue = int(recv_row[0])

    lcs = conn.execute(
        """
        SELECT lc.id, COALESCE(ct.amount_vnd, 0) AS contract_amount
        FROM crm_service_lifecycle lc
        LEFT JOIN crm_contracts ct ON ct.id = lc.contract_id
        WHERE lc.assigned_am = ? AND lc.status = 'active'
        """,
        (staff_id,),
    ).fetchall()

    active_services = len(lcs)
    total_margin = 0.0
    total_outstanding = 0

    for lc in lcs:
        lc_id = int(lc[0])
        contract_amount = int(lc[1])

        pay = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN status='received' THEN amount_vnd ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN status='pending'  THEN amount_vnd ELSE 0 END), 0)
            FROM crm_svc_payments WHERE lifecycle_id = ?
            """,
            (lc_id,),
        ).fetchone()
        recv = int(pay[0])

        exp = int(
            conn.execute(
                "SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses WHERE lifecycle_id = ?",
                (lc_id,),
            ).fetchone()[0]
        )

        profit = recv - exp
        margin = (profit / recv * 100) if recv > 0 else 0.0
        total_margin += margin
        total_outstanding += max(0, contract_amount - recv)

    avg_margin_pct = round(total_margin / active_services, 2) if active_services > 0 else 0.0

    return {
        "received_revenue": received_revenue,
        "active_services": active_services,
        "avg_margin_pct": avg_margin_pct,
        "outstanding": total_outstanding,
    }


def get_sp_metrics(
    conn: sqlite3.Connection, staff_id: int, year: int, month: int
) -> dict[str, Any]:
    month_str = f"{year:04d}-{month:02d}"

    tasks_row = conn.execute(
        """
        SELECT COUNT(*) FROM crm_svc_tasks
        WHERE done_by = ? AND is_done = 1 AND updated_at LIKE ?
        """,
        (staff_id, f"{month_str}%"),
    ).fetchone()
    tasks_completed = int(tasks_row[0])

    pending_row = conn.execute(
        """
        SELECT COUNT(*) FROM crm_svc_tasks t
        JOIN crm_service_lifecycle lc ON lc.id = t.lifecycle_id
        WHERE lc.assigned_sp = ? AND t.is_done = 0
        """,
        (staff_id,),
    ).fetchone()
    tasks_pending = int(pending_row[0])

    risks_row = conn.execute(
        """
        SELECT COUNT(*) FROM crm_svc_risks r
        JOIN crm_service_lifecycle lc ON lc.id = r.lifecycle_id
        WHERE lc.assigned_sp = ? AND r.is_active = 0 AND r.updated_at LIKE ?
        """,
        (staff_id, f"{month_str}%"),
    ).fetchone()
    risks_resolved = int(risks_row[0])

    return {
        "tasks_completed": tasks_completed,
        "tasks_pending": tasks_pending,
        "risks_resolved": risks_resolved,
    }


def get_lifecycle_staff_metrics(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, Any]:
    lc = conn.execute(
        "SELECT assigned_am, assigned_sp FROM crm_service_lifecycle WHERE id = ?",
        (lifecycle_id,),
    ).fetchone()
    if lc is None:
        return {"am": None, "sp": None}

    am_id = lc["assigned_am"]
    sp_id = lc["assigned_sp"]

    def _staff_name(sid: int | None) -> str | None:
        if sid is None:
            return None
        row = conn.execute("SELECT name FROM crm_staff WHERE id = ?", (sid,)).fetchone()
        return row["name"] if row else None

    am = None
    if am_id:
        tasks_done = int(
            conn.execute(
                "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = ? AND is_done = 1",
                (lifecycle_id,),
            ).fetchone()[0]
        )
        rev = int(
            conn.execute(
                "SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_payments "
                "WHERE lifecycle_id = ? AND status = 'received'",
                (lifecycle_id,),
            ).fetchone()[0]
        )
        am = {"id": am_id, "name": _staff_name(am_id), "tasks_done": tasks_done, "received_revenue": rev}

    sp = None
    if sp_id:
        tasks_done_sp = int(
            conn.execute(
                "SELECT COUNT(*) FROM crm_svc_tasks "
                "WHERE lifecycle_id = ? AND is_done = 1 AND done_by = ?",
                (lifecycle_id, sp_id),
            ).fetchone()[0]
        )
        risks_resolved = int(
            conn.execute(
                "SELECT COUNT(*) FROM crm_svc_risks WHERE lifecycle_id = ? AND is_active = 0",
                (lifecycle_id,),
            ).fetchone()[0]
        )
        sp = {
            "id": sp_id,
            "name": _staff_name(sp_id),
            "tasks_done": tasks_done_sp,
            "risks_resolved": risks_resolved,
        }

    return {"am": am, "sp": sp}


def set_target(
    conn: sqlite3.Connection,
    staff_id: int,
    role: str,
    metric_key: str,
    year: int,
    month: int,
    target_value: float,
) -> None:
    ts = _ts()
    conn.execute(
        """
        INSERT INTO crm_svc_kpi_targets
            (staff_id, role, metric_key, year, month, target_value, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(staff_id, metric_key, year, month)
        DO UPDATE SET target_value = excluded.target_value, updated_at = excluded.updated_at
        """,
        (staff_id, role, metric_key, year, month, target_value, ts, ts),
    )
    conn.commit()


def get_targets(
    conn: sqlite3.Connection, staff_id: int, year: int, month: int
) -> dict[str, float]:
    rows = conn.execute(
        "SELECT metric_key, target_value FROM crm_svc_kpi_targets "
        "WHERE staff_id = ? AND year = ? AND month = ?",
        (staff_id, year, month),
    ).fetchall()
    return {r["metric_key"]: r["target_value"] for r in rows}


def get_latest_kpi_scan(
    conn: sqlite3.Connection, staff_id: int, role: str, year: int, month: int
) -> str:
    row = conn.execute(
        "SELECT ai_output FROM crm_svc_kpi_scans "
        "WHERE staff_id = ? AND role = ? AND year = ? AND month = ? "
        "ORDER BY id DESC LIMIT 1",
        (staff_id, role, year, month),
    ).fetchone()
    return row["ai_output"] if row else ""


def run_ai_kpi_scan(
    conn: sqlite3.Connection,
    staff_id: int,
    role: str,
    year: int,
    month: int,
    context: dict,
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    prompt_template = _AM_PROMPT if role == "am" else _SP_PROMPT
    try:
        prompt = prompt_template.format(**context)
    except (KeyError, ValueError):
        return ""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        output = response.content[0].text.strip()
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans "
            "(staff_id, ai_output, role, year, month, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (staff_id, output, role, year, month, _ts()),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_kpi_scan error staff_id=%s: %s", staff_id, exc)
        return ""
```

- [ ] **Step 4: Run tests — all 20 must pass**

```bash
python3 -m pytest tests/test_crm_svc_kpi.py -v
```

Expected: `20 passed`

- [ ] **Step 5: Verify app still imports (no side effects)**

```bash
python3 -c "import app; print('OK')"
```

Expected: `OK`

---

### Task 2: Wire `app.py` — import + schema init + 4 API routes + update workflow page

**Files:**
- Modify: `app.py` (lines ~334, ~2277, ~16849–16892, ~17311)

**Interfaces:**
- Consumes: `crm_svc_kpi.ensure_schema`, `get_am_metrics`, `get_sp_metrics`, `get_targets`, `get_latest_kpi_scan`, `run_ai_kpi_scan`, `get_lifecycle_staff_metrics` from Task 1.
- Produces: 4 API routes + updated `crm_service_workflow_page` with `lifecycle_staff` template var.

---

- [ ] **Step 1: Add import at line ~334**

In `app.py`, find:
```python
from crm_svc_finance import ensure_schema as _ensure_svc_finance_schema
```
Replace with:
```python
from crm_svc_finance import ensure_schema as _ensure_svc_finance_schema
from crm_svc_kpi import ensure_schema as _ensure_svc_kpi_schema
```

- [ ] **Step 2: Add schema init at line ~2277**

In `app.py`, find:
```python
    _ensure_svc_finance_schema(conn)
```
Replace with:
```python
    _ensure_svc_finance_schema(conn)
    _ensure_svc_kpi_schema(conn)
```

- [ ] **Step 3: Update `crm_service_workflow_page` to include staff metrics**

In `app.py`, find the block (inside the `with get_connection() as conn:` of `crm_service_workflow_page`):
```python
        latest_health_scan = _fin_scan(conn, lifecycle_id, "health")
        latest_forecast_scan = _fin_scan(conn, lifecycle_id, "forecast")
    return render_template(
        "crm_service_workflow.html",
```
Replace with:
```python
        latest_health_scan = _fin_scan(conn, lifecycle_id, "health")
        latest_forecast_scan = _fin_scan(conn, lifecycle_id, "forecast")
        from crm_svc_kpi import get_lifecycle_staff_metrics as _kpi_staff
        lifecycle_staff = _kpi_staff(conn, lifecycle_id)
    return render_template(
        "crm_service_workflow.html",
```

Then find `latest_forecast_scan=latest_forecast_scan,` in the `render_template` call and add `lifecycle_staff` after it:

Find:
```python
        latest_forecast_scan=latest_forecast_scan,
        **_admin_page_template_kwargs(),
    )
```
Replace with:
```python
        latest_forecast_scan=latest_forecast_scan,
        lifecycle_staff=lifecycle_staff,
        **_admin_page_template_kwargs(),
    )
```

- [ ] **Step 4: Add 4 API routes before `@app.get("/api/crm/service-lifecycle")`**

In `app.py`, find:
```python
@app.get("/api/crm/service-lifecycle")
def api_svc_lifecycle_list() -> Any:
```
Replace with the following (insert before the `@app.get` line):
```python
@app.get("/api/crm/staff-kpi/<int:staff_id>/metrics")
def api_staff_kpi_metrics(staff_id: int) -> Any:
    from crm_svc_kpi import get_am_metrics as _am_met, get_sp_metrics as _sp_met
    role = request.args.get("role", "am")
    year = _opt_pos_int(request.args.get("year")) or datetime.utcnow().year
    month = _opt_pos_int(request.args.get("month")) or datetime.utcnow().month
    with get_connection() as conn:
        staff = conn.execute(
            "SELECT id, name FROM crm_staff WHERE id = ?", (staff_id,)
        ).fetchone()
        if staff is None:
            return jsonify({"error": "Không tìm thấy staff"}), 404
        if role == "am":
            metrics = _am_met(conn, staff_id, year, month)
        else:
            metrics = _sp_met(conn, staff_id, year, month)
    return jsonify({"staff_id": staff_id, "role": role, "year": year, "month": month, **metrics})


@app.post("/api/crm/staff-kpi/<int:staff_id>/targets")
def api_staff_kpi_set_target(staff_id: int) -> Any:
    from crm_svc_kpi import set_target as _set_tgt
    payload = request.get_json(force=True) or {}
    role = str(payload.get("role", "am")).strip()
    metric_key = str(payload.get("metric_key", "")).strip()
    year = _opt_pos_int(payload.get("year"))
    month = _opt_pos_int(payload.get("month"))
    target_value = payload.get("target_value")
    if not metric_key or not year or not month or target_value is None:
        return jsonify({"error": "Cần metric_key, year, month, target_value"}), 400
    try:
        target_value = float(target_value)
    except (TypeError, ValueError):
        return jsonify({"error": "target_value phải là số"}), 400
    with get_connection() as conn:
        _set_tgt(conn, staff_id, role, metric_key, year, month, target_value)
    return jsonify({
        "ok": True, "staff_id": staff_id, "metric_key": metric_key,
        "year": year, "month": month, "target_value": target_value,
    })


@app.post("/api/crm/staff-kpi/<int:staff_id>/ai-scan")
def api_staff_kpi_ai_scan(staff_id: int) -> Any:
    from crm_svc_kpi import (
        get_am_metrics as _am_met,
        get_sp_metrics as _sp_met,
        get_targets as _get_tgt,
        run_ai_kpi_scan as _ai_scan,
    )
    payload = request.get_json(force=True) or {}
    role = str(payload.get("role", "am")).strip()
    year = _opt_pos_int(payload.get("year")) or datetime.utcnow().year
    month = _opt_pos_int(payload.get("month")) or datetime.utcnow().month
    if role not in ("am", "sp"):
        return jsonify({"error": "role phải là 'am' hoặc 'sp'"}), 400
    with get_connection() as conn:
        staff = conn.execute(
            "SELECT name FROM crm_staff WHERE id = ?", (staff_id,)
        ).fetchone()
        if staff is None:
            return jsonify({"error": "Không tìm thấy staff"}), 404
        targets = _get_tgt(conn, staff_id, year, month)
        if role == "am":
            metrics = _am_met(conn, staff_id, year, month)
            ctx = {
                "staff_name": staff["name"],
                "month": month,
                "year": year,
                "received_revenue": metrics["received_revenue"],
                "active_services": metrics["active_services"],
                "avg_margin_pct": metrics["avg_margin_pct"],
                "outstanding": metrics["outstanding"],
                "target_received_revenue": int(targets.get("received_revenue", 0)),
                "target_active_services": int(targets.get("active_services", 0)),
                "target_avg_margin_pct": float(targets.get("avg_margin_pct", 0)),
            }
        else:
            metrics = _sp_met(conn, staff_id, year, month)
            ctx = {
                "staff_name": staff["name"],
                "month": month,
                "year": year,
                "tasks_completed": metrics["tasks_completed"],
                "tasks_pending": metrics["tasks_pending"],
                "risks_resolved": metrics["risks_resolved"],
                "target_tasks_completed": int(targets.get("tasks_completed", 0)),
                "target_risks_resolved": int(targets.get("risks_resolved", 0)),
            }
        output = _ai_scan(conn, staff_id, role, year, month, ctx)
    return jsonify({"ai_output": output, "staff_id": staff_id, "role": role})


@app.get("/api/crm/svc-lifecycle/<int:lifecycle_id>/staff-metrics")
def api_svc_lifecycle_staff_metrics(lifecycle_id: int) -> Any:
    from crm_svc_kpi import get_lifecycle_staff_metrics as _lc_staff
    with get_connection() as conn:
        result = _lc_staff(conn, lifecycle_id)
    return jsonify(result)


@app.get("/api/crm/service-lifecycle")
def api_svc_lifecycle_list() -> Any:
```

- [ ] **Step 5: Verify app imports and tests still pass**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_svc_kpi.py -v 2>&1 | tail -5
```

Expected: `OK` then `20 passed`

---

### Task 3: Staff section in `crm_service_workflow.html`

**Files:**
- Modify: `templates/crm_service_workflow.html`

**Interfaces:**
- Consumes: `lifecycle_staff` template variable (dict with keys `am` and `sp`) from Task 2.
- Each key is either `None` or a dict: `{id, name, tasks_done, received_revenue}` (AM) / `{id, name, tasks_done, risks_resolved}` (SP).

---

- [ ] **Step 1: Add staff section HTML before the finance JS `<script>` block**

In `templates/crm_service_workflow.html`, find the exact string (the closing divs before the final script tag):
```
</div>
</div>

<script>
// ─── Finance JS ────────────────────────────────────────────────────────────────
```
Replace with:
```
</div>
</div>

{# ─── Staff Section ─────────────────────────────────────────────────────────── #}
<div style="margin-top:2rem;border-top:2px solid #e0e7ff;padding-top:1.5rem;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;">
    <h3 style="margin:0;font-size:.95rem;font-weight:700;color:#4338ca;">
      Nhân sự phụ trách
    </h3>
    <a href="/crm/staff-kpi" style="font-size:.75rem;color:#6366f1;text-decoration:none;">
      Xem KPI dashboard →
    </a>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
    {% if lifecycle_staff.am %}
    {% set am = lifecycle_staff.am %}
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:1rem;">
      <div style="font-size:.7rem;color:#3b82f6;font-weight:600;margin-bottom:.25rem;text-transform:uppercase;letter-spacing:.05em;">Account Manager</div>
      <div style="font-size:.95rem;font-weight:700;color:#1e40af;margin-bottom:.75rem;">{{ am.name }}</div>
      <div style="display:flex;gap:1.5rem;font-size:.8rem;">
        <div>
          <div style="color:#93c5fd;font-size:.7rem;">Tasks done</div>
          <div style="font-weight:600;color:#1e40af;">{{ am.tasks_done }}</div>
        </div>
        <div>
          <div style="color:#93c5fd;font-size:.7rem;">Doanh thu</div>
          <div style="font-weight:600;color:#15803d;">{{ "{:,.0f}".format(am.received_revenue) }} ₫</div>
        </div>
      </div>
    </div>
    {% else %}
    <div style="background:#f9fafb;border:1px dashed #d1d5db;border-radius:8px;padding:1rem;
                display:flex;align-items:center;justify-content:center;">
      <span style="font-size:.8rem;color:#9ca3af;">Chưa phân công AM</span>
    </div>
    {% endif %}

    {% if lifecycle_staff.sp %}
    {% set sp = lifecycle_staff.sp %}
    <div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:8px;padding:1rem;">
      <div style="font-size:.7rem;color:#7c3aed;font-weight:600;margin-bottom:.25rem;text-transform:uppercase;letter-spacing:.05em;">Specialist</div>
      <div style="font-size:.95rem;font-weight:700;color:#5b21b6;margin-bottom:.75rem;">{{ sp.name }}</div>
      <div style="display:flex;gap:1.5rem;font-size:.8rem;">
        <div>
          <div style="color:#c4b5fd;font-size:.7rem;">Tasks done</div>
          <div style="font-weight:600;color:#5b21b6;">{{ sp.tasks_done }}</div>
        </div>
        <div>
          <div style="color:#c4b5fd;font-size:.7rem;">Rủi ro xử lý</div>
          <div style="font-weight:600;color:#15803d;">{{ sp.risks_resolved }}</div>
        </div>
      </div>
    </div>
    {% else %}
    <div style="background:#f9fafb;border:1px dashed #d1d5db;border-radius:8px;padding:1rem;
                display:flex;align-items:center;justify-content:center;">
      <span style="font-size:.8rem;color:#9ca3af;">Chưa phân công SP</span>
    </div>
    {% endif %}
  </div>
</div>

<script>
// ─── Finance JS ────────────────────────────────────────────────────────────────
```

- [ ] **Step 2: Verify import still works**

```bash
python3 -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verify test suite still passes**

```bash
python3 -m pytest tests/test_crm_svc_kpi.py -v 2>&1 | tail -3
```

Expected: `20 passed`

---

### Task 4: `crm_staff_kpi.html` + `/crm/staff-kpi` page route in `app.py`

**Files:**
- Create: `templates/crm_staff_kpi.html`
- Modify: `app.py` (add page route after `/crm/financials` route at line ~17074)

**Interfaces:**
- Consumes: `get_am_metrics`, `get_sp_metrics`, `get_targets`, `get_latest_kpi_scan` from Task 1.
- Template variables: `all_staff` (list of dicts), `selected_staff` (dict or None), `selected_staff_id` (int or None), `year` (int), `month` (int), `am_metrics` (dict or None), `sp_metrics` (dict or None), `targets` (dict), `latest_am_scan` (str), `latest_sp_scan` (str).

---

- [ ] **Step 1: Add `/crm/staff-kpi` page route to `app.py`**

In `app.py`, find:
```python
@app.get("/api/crm/svc-finance/<int:lifecycle_id>/summary")
def api_svc_finance_summary(lifecycle_id: int) -> Any:
```
Insert BEFORE that line:
```python
@app.get("/crm/staff-kpi")
def crm_staff_kpi_page() -> Any:
    redir = _ensure_admin_session_html()
    if redir is not None:
        return redir
    from crm_svc_kpi import (
        get_am_metrics as _am_met,
        get_sp_metrics as _sp_met,
        get_targets as _get_tgt,
        get_latest_kpi_scan as _latest_scan,
    )
    now = datetime.utcnow()
    staff_id = _opt_pos_int(request.args.get("staff_id"))
    year = _opt_pos_int(request.args.get("year")) or now.year
    month = _opt_pos_int(request.args.get("month")) or now.month

    with get_connection() as conn:
        all_staff = [
            dict(r) for r in conn.execute(
                "SELECT id, name FROM crm_staff WHERE active = 1 ORDER BY name"
            ).fetchall()
        ]
        selected_staff = None
        am_metrics = None
        sp_metrics = None
        targets: dict = {}
        latest_am_scan = ""
        latest_sp_scan = ""

        if staff_id:
            row = conn.execute(
                "SELECT id, name FROM crm_staff WHERE id = ?", (staff_id,)
            ).fetchone()
            if row:
                selected_staff = dict(row)
                am_metrics = _am_met(conn, staff_id, year, month)
                sp_metrics = _sp_met(conn, staff_id, year, month)
                targets = _get_tgt(conn, staff_id, year, month)
                latest_am_scan = _latest_scan(conn, staff_id, "am", year, month)
                latest_sp_scan = _latest_scan(conn, staff_id, "sp", year, month)

    return render_template(
        "crm_staff_kpi.html",
        all_staff=all_staff,
        selected_staff=selected_staff,
        selected_staff_id=staff_id,
        year=year,
        month=month,
        am_metrics=am_metrics,
        sp_metrics=sp_metrics,
        targets=targets,
        latest_am_scan=latest_am_scan,
        latest_sp_scan=latest_sp_scan,
        **_admin_page_template_kwargs(),
    )


@app.get("/api/crm/svc-finance/<int:lifecycle_id>/summary")
def api_svc_finance_summary(lifecycle_id: int) -> Any:
```

- [ ] **Step 2: Create `templates/crm_staff_kpi.html`**

Create the file with this full content:

```html
{% extends "admin_layout.html" %}
{% block admin_main %}
<div style="padding:1rem 1.5rem;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;">
    <h2 style="margin:0;font-size:1.1rem;font-weight:700;color:#1e293b;">KPI Nhân sự</h2>
    <a href="/crm/service-delivery" style="font-size:.8rem;color:#6366f1;text-decoration:none;">← Dịch vụ</a>
  </div>

  <form method="get" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
       padding:1rem;margin-bottom:1.5rem;display:flex;gap:1rem;align-items:flex-end;flex-wrap:wrap;">
    <div>
      <label style="display:block;font-size:.75rem;color:#64748b;margin-bottom:.25rem;">Nhân viên</label>
      <select name="staff_id" style="border:1px solid #cbd5e1;border-radius:6px;padding:.4rem .6rem;
              font-size:.85rem;" onchange="this.form.submit()">
        <option value="">-- Chọn nhân viên --</option>
        {% for s in all_staff %}
        <option value="{{ s.id }}" {% if selected_staff_id == s.id %}selected{% endif %}>{{ s.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label style="display:block;font-size:.75rem;color:#64748b;margin-bottom:.25rem;">Tháng</label>
      <input type="number" name="month" min="1" max="12" value="{{ month }}"
             style="border:1px solid #cbd5e1;border-radius:6px;padding:.4rem .6rem;font-size:.85rem;width:4rem;">
    </div>
    <div>
      <label style="display:block;font-size:.75rem;color:#64748b;margin-bottom:.25rem;">Năm</label>
      <input type="number" name="year" min="2020" max="2099" value="{{ year }}"
             style="border:1px solid #cbd5e1;border-radius:6px;padding:.4rem .6rem;font-size:.85rem;width:5rem;">
    </div>
    <button type="submit" style="background:#6366f1;color:#fff;border:none;border-radius:6px;
            padding:.4rem .9rem;font-size:.85rem;cursor:pointer;">Xem</button>
  </form>

  {% if not selected_staff %}
  <div style="text-align:center;color:#9ca3af;padding:3rem 0;font-size:.9rem;">
    Chọn nhân viên để xem KPI tháng {{ month }}/{{ year }}
  </div>
  {% else %}

  {% set _sid = selected_staff.id %}
  {% set _y = year %}
  {% set _m = month %}

  {# ─── AM Section ─────────────────────────────────────────────────────── #}
  <div style="margin-bottom:2.5rem;">
    <h3 style="font-size:.9rem;color:#1d4ed8;font-weight:700;margin:0 0 1rem;
        border-bottom:2px solid #bfdbfe;padding-bottom:.5rem;">
      Account Manager — Tháng {{ month }}/{{ year }}
    </h3>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1rem;">

      {# Card: received_revenue #}
      {% set am_recv = (am_metrics.received_revenue if am_metrics else 0)|int %}
      {% set t_recv = (targets.get('received_revenue', 0))|int %}
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;">
        <div style="font-size:.7rem;color:#64748b;margin-bottom:.25rem;">Doanh thu thực nhận</div>
        <div style="font-size:1.15rem;font-weight:700;color:#1e293b;">{{ "{:,.0f}".format(am_recv) }} ₫</div>
        <div style="display:flex;align-items:center;gap:.4rem;margin-top:.5rem;">
          <span style="font-size:.7rem;color:#94a3b8;">Target:</span>
          <input type="number" min="0" step="500000" value="{{ t_recv }}"
                 style="width:7rem;border:1px solid #cbd5e1;border-radius:4px;padding:.2rem .4rem;font-size:.75rem;"
                 onblur="setTarget({{ _sid }}, 'am', 'received_revenue', {{ _y }}, {{ _m }}, this.value)">
        </div>
        {% if t_recv > 0 %}
        <div style="margin-top:.25rem;font-size:.7rem;
            color:{{ '#16a34a' if am_recv >= t_recv else '#dc2626' }}">
          {% if am_recv >= t_recv %}✓ Đạt{% else %}✗ {{ "{:.0f}".format(am_recv / t_recv * 100) }}%{% endif %}
        </div>
        {% endif %}
      </div>

      {# Card: active_services #}
      {% set am_svc = (am_metrics.active_services if am_metrics else 0)|int %}
      {% set t_svc = (targets.get('active_services', 0))|int %}
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;">
        <div style="font-size:.7rem;color:#64748b;margin-bottom:.25rem;">Dịch vụ đang quản lý</div>
        <div style="font-size:1.15rem;font-weight:700;color:#1e293b;">{{ am_svc }}</div>
        <div style="display:flex;align-items:center;gap:.4rem;margin-top:.5rem;">
          <span style="font-size:.7rem;color:#94a3b8;">Target:</span>
          <input type="number" min="0" value="{{ t_svc }}"
                 style="width:4rem;border:1px solid #cbd5e1;border-radius:4px;padding:.2rem .4rem;font-size:.75rem;"
                 onblur="setTarget({{ _sid }}, 'am', 'active_services', {{ _y }}, {{ _m }}, this.value)">
        </div>
        {% if t_svc > 0 %}
        <div style="margin-top:.25rem;font-size:.7rem;
            color:{{ '#16a34a' if am_svc >= t_svc else '#dc2626' }}">
          {{ '✓ Đạt' if am_svc >= t_svc else '✗ Chưa đạt' }}
        </div>
        {% endif %}
      </div>

      {# Card: avg_margin_pct #}
      {% set am_margin = (am_metrics.avg_margin_pct if am_metrics else 0)|float %}
      {% set t_margin = (targets.get('avg_margin_pct', 0))|float %}
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;">
        <div style="font-size:.7rem;color:#64748b;margin-bottom:.25rem;">Biên lợi nhuận TB</div>
        <div style="font-size:1.15rem;font-weight:700;
            color:{{ '#16a34a' if am_margin >= 30 else ('#f59e0b' if am_margin >= 15 else '#dc2626') }}">
          {{ "%.1f"|format(am_margin) }}%
        </div>
        <div style="display:flex;align-items:center;gap:.4rem;margin-top:.5rem;">
          <span style="font-size:.7rem;color:#94a3b8;">Target:</span>
          <input type="number" min="0" max="100" step="1" value="{{ "%.1f"|format(t_margin) }}"
                 style="width:4rem;border:1px solid #cbd5e1;border-radius:4px;padding:.2rem .4rem;font-size:.75rem;"
                 onblur="setTarget({{ _sid }}, 'am', 'avg_margin_pct', {{ _y }}, {{ _m }}, this.value)">
          <span style="font-size:.7rem;color:#94a3b8;">%</span>
        </div>
        {% if t_margin > 0 %}
        <div style="margin-top:.25rem;font-size:.7rem;
            color:{{ '#16a34a' if am_margin >= t_margin else '#dc2626' }}">
          {{ '✓ Đạt' if am_margin >= t_margin else '✗ Chưa đạt' }}
        </div>
        {% endif %}
      </div>

      {# Card: outstanding (no target) #}
      {% set am_out = (am_metrics.outstanding if am_metrics else 0)|int %}
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;">
        <div style="font-size:.7rem;color:#64748b;margin-bottom:.25rem;">Công nợ tồn đọng</div>
        <div style="font-size:1.15rem;font-weight:700;
            color:{{ '#dc2626' if am_out > 10000000 else '#1e293b' }}">
          {{ "{:,.0f}".format(am_out) }} ₫
        </div>
        <div style="font-size:.7rem;color:#94a3b8;margin-top:.75rem;">Tổng dịch vụ active</div>
      </div>

    </div>

    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:.75rem;">
      <button onclick="kpiAiScan({{ _sid }}, 'am', {{ _y }}, {{ _m }})"
              id="kpi-am-scan-btn"
              style="background:#eff6ff;border:1px solid #bfdbfe;color:#1d4ed8;border-radius:6px;
                     padding:.4rem .8rem;font-size:.8rem;cursor:pointer;">
        AI Phân tích AM
      </button>
      <span id="kpi-am-scan-status" style="font-size:.8rem;color:#6366f1;"></span>
    </div>
    {% if latest_am_scan %}
    <div id="kpi-am-scan-output"
         style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:.75rem;
                font-size:.8rem;white-space:pre-wrap;line-height:1.6;">{{ latest_am_scan }}</div>
    {% else %}
    <div id="kpi-am-scan-output"
         style="display:none;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;
                padding:.75rem;font-size:.8rem;white-space:pre-wrap;line-height:1.6;"></div>
    {% endif %}
  </div>

  {# ─── SP Section ─────────────────────────────────────────────────────── #}
  <div>
    <h3 style="font-size:.9rem;color:#6d28d9;font-weight:700;margin:0 0 1rem;
        border-bottom:2px solid #ddd6fe;padding-bottom:.5rem;">
      Specialist — Tháng {{ month }}/{{ year }}
    </h3>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1rem;">

      {# Card: tasks_completed #}
      {% set sp_done = (sp_metrics.tasks_completed if sp_metrics else 0)|int %}
      {% set t_done = (targets.get('tasks_completed', 0))|int %}
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;">
        <div style="font-size:.7rem;color:#64748b;margin-bottom:.25rem;">Tasks hoàn thành</div>
        <div style="font-size:1.15rem;font-weight:700;color:#1e293b;">{{ sp_done }}</div>
        <div style="display:flex;align-items:center;gap:.4rem;margin-top:.5rem;">
          <span style="font-size:.7rem;color:#94a3b8;">Target:</span>
          <input type="number" min="0" value="{{ t_done }}"
                 style="width:4rem;border:1px solid #cbd5e1;border-radius:4px;padding:.2rem .4rem;font-size:.75rem;"
                 onblur="setTarget({{ _sid }}, 'sp', 'tasks_completed', {{ _y }}, {{ _m }}, this.value)">
        </div>
        {% if t_done > 0 %}
        <div style="margin-top:.25rem;font-size:.7rem;
            color:{{ '#16a34a' if sp_done >= t_done else '#dc2626' }}">
          {{ '✓ Đạt' if sp_done >= t_done else '✗ Chưa đạt' }}
        </div>
        {% endif %}
      </div>

      {# Card: tasks_pending (no target — lower is better) #}
      {% set sp_pend = (sp_metrics.tasks_pending if sp_metrics else 0)|int %}
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;">
        <div style="font-size:.7rem;color:#64748b;margin-bottom:.25rem;">Tasks đang chờ</div>
        <div style="font-size:1.15rem;font-weight:700;
            color:{{ '#f59e0b' if sp_pend > 5 else '#1e293b' }}">{{ sp_pend }}</div>
        <div style="font-size:.7rem;color:#94a3b8;margin-top:.75rem;">Backlog hiện tại</div>
      </div>

      {# Card: risks_resolved #}
      {% set sp_risks = (sp_metrics.risks_resolved if sp_metrics else 0)|int %}
      {% set t_risks = (targets.get('risks_resolved', 0))|int %}
      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;">
        <div style="font-size:.7rem;color:#64748b;margin-bottom:.25rem;">Rủi ro đã xử lý</div>
        <div style="font-size:1.15rem;font-weight:700;color:#1e293b;">{{ sp_risks }}</div>
        <div style="display:flex;align-items:center;gap:.4rem;margin-top:.5rem;">
          <span style="font-size:.7rem;color:#94a3b8;">Target:</span>
          <input type="number" min="0" value="{{ t_risks }}"
                 style="width:4rem;border:1px solid #cbd5e1;border-radius:4px;padding:.2rem .4rem;font-size:.75rem;"
                 onblur="setTarget({{ _sid }}, 'sp', 'risks_resolved', {{ _y }}, {{ _m }}, this.value)">
        </div>
        {% if t_risks > 0 %}
        <div style="margin-top:.25rem;font-size:.7rem;
            color:{{ '#16a34a' if sp_risks >= t_risks else '#dc2626' }}">
          {{ '✓ Đạt' if sp_risks >= t_risks else '✗ Chưa đạt' }}
        </div>
        {% endif %}
      </div>

    </div>

    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:.75rem;">
      <button onclick="kpiAiScan({{ _sid }}, 'sp', {{ _y }}, {{ _m }})"
              id="kpi-sp-scan-btn"
              style="background:#f5f3ff;border:1px solid #ddd6fe;color:#6d28d9;border-radius:6px;
                     padding:.4rem .8rem;font-size:.8rem;cursor:pointer;">
        AI Phân tích SP
      </button>
      <span id="kpi-sp-scan-status" style="font-size:.8rem;color:#7c3aed;"></span>
    </div>
    {% if latest_sp_scan %}
    <div id="kpi-sp-scan-output"
         style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:6px;padding:.75rem;
                font-size:.8rem;white-space:pre-wrap;line-height:1.6;">{{ latest_sp_scan }}</div>
    {% else %}
    <div id="kpi-sp-scan-output"
         style="display:none;background:#f5f3ff;border:1px solid #ddd6fe;border-radius:6px;
                padding:.75rem;font-size:.8rem;white-space:pre-wrap;line-height:1.6;"></div>
    {% endif %}
  </div>

  {% endif %}
</div>

<script>
function setTarget(staffId, role, metricKey, year, month, value) {
  const val = parseFloat(value);
  if (isNaN(val) || val < 0) return;
  fetch('/api/crm/staff-kpi/' + staffId + '/targets', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({role: role, metric_key: metricKey, year: year, month: month, target_value: val}),
  }).catch(function(err) { console.error('setTarget error:', err); });
}

function kpiAiScan(staffId, role, year, month) {
  var btnId = 'kpi-' + role + '-scan-btn';
  var outId = 'kpi-' + role + '-scan-output';
  var statusId = 'kpi-' + role + '-scan-status';
  var btn = document.getElementById(btnId);
  var out = document.getElementById(outId);
  var status = document.getElementById(statusId);
  if (btn) btn.disabled = true;
  if (status) status.textContent = 'AI đang phân tích...';
  fetch('/api/crm/staff-kpi/' + staffId + '/ai-scan', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({role: role, year: year, month: month}),
  }).then(function(r) { return r.json(); }).then(function(data) {
    if (out) {
      out.textContent = data.ai_output || '(Không có kết quả)';
      out.style.display = 'block';
    }
    if (status) status.textContent = '';
    if (btn) btn.disabled = false;
  }).catch(function(err) {
    if (status) status.textContent = 'Lỗi: ' + err;
    if (btn) btn.disabled = false;
  });
}
</script>
{% endblock %}
```

- [ ] **Step 3: Verify app imports and tests pass**

```bash
python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_svc_kpi.py -v 2>&1 | tail -3
```

Expected: `OK` then `20 passed`

- [ ] **Step 4: Update progress ledger**

Append to `.superpowers/sdd/progress.md`:
```
## Phase 4 Tasks (KPI Staff Performance)
Plan: docs/superpowers/plans/2026-06-23-kpi-staff-performance.md
- [ ] Task 1: crm_svc_kpi.py + tests (TDD)
- [ ] Task 2: Wire app.py — import + schema init + 4 routes + update workflow page
- [ ] Task 3: Staff section in crm_service_workflow.html
- [ ] Task 4: crm_staff_kpi.html + /crm/staff-kpi page route
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `crm_svc_kpi_targets` table | Task 1 `ensure_schema` |
| `crm_svc_kpi_scans` table | Task 1 `ensure_schema` |
| `get_am_metrics` — 4 return keys | Task 1 |
| `get_sp_metrics` — 3 return keys | Task 1 |
| `get_lifecycle_staff_metrics` | Task 1 |
| `set_target` / `get_targets` | Task 1 |
| `get_latest_kpi_scan` with `role` param | Task 1 |
| `run_ai_kpi_scan` fail-silent | Task 1 |
| Import + schema init in app.py | Task 2 |
| `lifecycle_staff` kwarg to workflow page | Task 2 |
| GET `/api/crm/staff-kpi/<id>/metrics` | Task 2 |
| POST `/api/crm/staff-kpi/<id>/targets` | Task 2 |
| POST `/api/crm/staff-kpi/<id>/ai-scan` | Task 2 |
| GET `/api/crm/svc-lifecycle/<id>/staff-metrics` | Task 2 |
| Staff section in workflow template | Task 3 |
| `crm_staff_kpi.html` with staff selector + month/year filter | Task 4 |
| AM section: 4 cards + targets + AI button/output | Task 4 |
| SP section: 3 cards + targets + AI button/output | Task 4 |
| GET `/crm/staff-kpi` page route | Task 4 |
| `setTarget` JS saves target on blur | Task 4 |
| `kpiAiScan` JS calls AI and updates output | Task 4 |
| ~20 tests | Task 1 (20 tests written) |

**Placeholder scan:** No TBD, TODO, or "similar to Task N" patterns found.

**Type consistency:**
- `get_am_metrics` returns `{received_revenue: int, active_services: int, avg_margin_pct: float, outstanding: int}` — consistent across Task 1, Task 2 route context building, and Task 4 template vars.
- `get_lifecycle_staff_metrics` returns `{am: dict|None, sp: dict|None}` — consumed correctly in Task 2 (passes to template as `lifecycle_staff`) and Task 3 (`lifecycle_staff.am`, `lifecycle_staff.sp`).
- `get_targets` returns `dict[str, float]` — `.get('received_revenue', 0)` calls in Task 4 template are consistent.
- `get_latest_kpi_scan(conn, staff_id, role, year, month)` — 5-arg signature used correctly in Task 2 route and Task 4 page route.
