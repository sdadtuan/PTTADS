# Profit & Cost Tracking — Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track doanh thu (payments), chi phí (expenses), và lợi nhuận per service lifecycle; thêm AI health check + burn rate forecast; trang `/crm/financials` tổng hợp toàn bộ.

**Architecture:** Module `crm_svc_finance.py` (3 bảng, 11 functions); 8 API routes + 1 page route trong `app.py`; finance section thêm vào `crm_service_workflow.html`; trang mới `crm_financials.html`.

**Tech Stack:** Flask 3 + SQLite + Anthropic SDK (`claude-haiku-4-5-20251001`), no git repository.

## Global Constraints

- Working directory: `/Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP`
- No git — skip all commit steps; verify bằng `python3 -c "import ..."` và `python3 -m pytest`
- `python3` và `python3 -m pytest` (không phải `python` hay `pytest`)
- `from __future__ import annotations` ở đầu mỗi file Python
- AI model: `claude-haiku-4-5-20251001`, synchronous, fail silent (return `""`)
- Timestamps: `datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")`
- Auth pattern: `redir = _ensure_admin_session_html(); if redir is not None: return redir`
- Template extends `admin_layout.html`, block `admin_main`, pass `**_admin_page_template_kwargs()`
- `_opt_pos_int(val)` cho parsing int từ JSON params
- `get_connection()` context manager, `conn.row_factory = sqlite3.Row`
- Inline local imports bên trong route functions (đừng import ở top-level ngoài line ~333)
- Spec: `docs/superpowers/specs/2026-06-23-profit-cost-tracking-design.md`

---

## File Map

| File | Action | Nội dung |
|------|--------|---------|
| `crm_svc_finance.py` | Tạo mới | 3 bảng schema + 11 functions |
| `tests/test_crm_svc_finance.py` | Tạo mới | ~25 tests TDD |
| `app.py` | Sửa (3 chỗ) | import line 334, init line 2276, 8 routes + update workflow page |
| `templates/crm_service_workflow.html` | Sửa cuối file | Finance section (metrics + payments + expenses + AI) |
| `templates/crm_financials.html` | Tạo mới | Trang tổng hợp tất cả lifecycles |

---

## Task 1: crm_svc_finance.py + TDD tests

**Files:**
- Create: `crm_svc_finance.py`
- Create: `tests/test_crm_svc_finance.py`

**Interfaces produced:**
- `ensure_schema(conn)` → None
- `get_summary(conn, lifecycle_id, contract_amount_vnd)` → dict (keys: expected_revenue, received_revenue, pending_revenue, total_expenses, profit, margin_pct, outstanding)
- `list_payments(conn, lifecycle_id)` → list[dict] (ORDER BY received_on DESC, id DESC)
- `create_payment(conn, lifecycle_id, amount_vnd, received_on, status='pending', notes='')` → int (payment_id)
- `update_payment(conn, payment_id, *, amount_vnd=None, received_on=None, status=None, notes=None)` → None
- `delete_payment(conn, payment_id)` → bool
- `list_expenses(conn, lifecycle_id)` → list[dict] (ORDER BY expense_on DESC, id DESC)
- `create_expense(conn, lifecycle_id, title, category, amount_vnd, expense_on, notes='')` → int
- `update_expense(conn, expense_id, *, title=None, category=None, amount_vnd=None, expense_on=None, notes=None)` → None
- `delete_expense(conn, expense_id)` → bool
- `get_latest_finance_scan(conn, lifecycle_id, scan_type)` → str
- `run_ai_finance_scan(conn, lifecycle_id, scan_type, context)` → str

- [ ] **Step 1: Viết tests trước (TDD)**

Tạo `tests/test_crm_svc_finance.py`:

```python
# tests/test_crm_svc_finance.py
"""Tests cho crm_svc_finance module."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_svc_finance import (
    create_expense,
    create_payment,
    delete_expense,
    delete_payment,
    ensure_schema,
    get_latest_finance_scan,
    get_summary,
    list_expenses,
    list_payments,
    run_ai_finance_scan,
    update_expense,
    update_payment,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'active',
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        INSERT INTO crm_service_lifecycle
            (id, service_slug, stage, status, stage_entered_at, created_at, updated_at)
        VALUES (1, 'dich-vu-seo-tong-the', 'deliver', 'active',
                '2026-06-23 00:00:00', '2026-06-23 00:00:00', '2026-06-23 00:00:00')
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
        self.assertIn("crm_svc_payments", tables)
        self.assertIn("crm_svc_expenses", tables)
        self.assertIn("crm_svc_finance_scans", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        ensure_schema(conn)
        ensure_schema(conn)


class TestGetSummary(unittest.TestCase):
    def test_no_data_returns_zeros(self):
        conn = _setup_conn()
        s = get_summary(conn, 1, 0)
        self.assertEqual(s["expected_revenue"], 0)
        self.assertEqual(s["received_revenue"], 0)
        self.assertEqual(s["pending_revenue"], 0)
        self.assertEqual(s["total_expenses"], 0)
        self.assertEqual(s["profit"], 0)
        self.assertEqual(s["margin_pct"], 0.0)
        self.assertEqual(s["outstanding"], 0)

    def test_received_only(self):
        conn = _setup_conn()
        create_payment(conn, 1, 5_000_000, "2026-06-01", status="received")
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["received_revenue"], 5_000_000)
        self.assertEqual(s["outstanding"], 5_000_000)

    def test_pending_not_counted_in_received(self):
        conn = _setup_conn()
        create_payment(conn, 1, 3_000_000, "2026-06-01", status="pending")
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["received_revenue"], 0)
        self.assertEqual(s["pending_revenue"], 3_000_000)

    def test_cancelled_excluded_from_both(self):
        conn = _setup_conn()
        create_payment(conn, 1, 2_000_000, "2026-06-01", status="cancelled")
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["received_revenue"], 0)
        self.assertEqual(s["pending_revenue"], 0)

    def test_profit_calculation(self):
        conn = _setup_conn()
        create_payment(conn, 1, 10_000_000, "2026-06-01", status="received")
        create_expense(conn, 1, "Chi phí A", "nhan-cong", 3_000_000, "2026-06-05")
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["profit"], 7_000_000)

    def test_margin_pct_calculation(self):
        conn = _setup_conn()
        create_payment(conn, 1, 10_000_000, "2026-06-01", status="received")
        create_expense(conn, 1, "Chi phí", "khac", 2_000_000, "2026-06-05")
        s = get_summary(conn, 1, 10_000_000)
        self.assertAlmostEqual(s["margin_pct"], 80.0, places=1)

    def test_division_by_zero_guard_when_received_zero(self):
        conn = _setup_conn()
        create_expense(conn, 1, "Chi phí", "khac", 1_000_000, "2026-06-05")
        s = get_summary(conn, 1, 0)
        self.assertEqual(s["margin_pct"], 0.0)


class TestPayments(unittest.TestCase):
    def test_create_returns_positive_id(self):
        conn = _setup_conn()
        pid = create_payment(conn, 1, 5_000_000, "2026-06-01")
        self.assertIsInstance(pid, int)
        self.assertGreater(pid, 0)

    def test_list_ordered_newest_first(self):
        conn = _setup_conn()
        create_payment(conn, 1, 1_000_000, "2026-06-01", status="received")
        create_payment(conn, 1, 2_000_000, "2026-06-15", status="received")
        payments = list_payments(conn, 1)
        self.assertEqual(payments[0]["received_on"], "2026-06-15")
        self.assertEqual(payments[1]["received_on"], "2026-06-01")

    def test_update_amount(self):
        conn = _setup_conn()
        pid = create_payment(conn, 1, 5_000_000, "2026-06-01")
        update_payment(conn, pid, amount_vnd=7_000_000)
        row = conn.execute(
            "SELECT amount_vnd FROM crm_svc_payments WHERE id = ?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], 7_000_000)

    def test_update_status(self):
        conn = _setup_conn()
        pid = create_payment(conn, 1, 5_000_000, "2026-06-01")
        update_payment(conn, pid, status="received")
        row = conn.execute(
            "SELECT status FROM crm_svc_payments WHERE id = ?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "received")

    def test_delete_existing_returns_true(self):
        conn = _setup_conn()
        pid = create_payment(conn, 1, 5_000_000, "2026-06-01")
        self.assertTrue(delete_payment(conn, pid))
        self.assertIsNone(
            conn.execute(
                "SELECT id FROM crm_svc_payments WHERE id = ?", (pid,)
            ).fetchone()
        )

    def test_delete_nonexistent_returns_false(self):
        conn = _setup_conn()
        self.assertFalse(delete_payment(conn, 99999))


class TestExpenses(unittest.TestCase):
    def test_create_returns_positive_id(self):
        conn = _setup_conn()
        eid = create_expense(conn, 1, "Chi phí content", "nhan-cong", 2_000_000, "2026-06-05")
        self.assertIsInstance(eid, int)
        self.assertGreater(eid, 0)

    def test_list_ordered_newest_first(self):
        conn = _setup_conn()
        create_expense(conn, 1, "Chi A", "khac", 1_000_000, "2026-06-01")
        create_expense(conn, 1, "Chi B", "khac", 2_000_000, "2026-06-15")
        expenses = list_expenses(conn, 1)
        self.assertEqual(expenses[0]["expense_on"], "2026-06-15")
        self.assertEqual(expenses[1]["expense_on"], "2026-06-01")

    def test_update_title_and_category(self):
        conn = _setup_conn()
        eid = create_expense(conn, 1, "Cũ", "khac", 1_000_000, "2026-06-01")
        update_expense(conn, eid, title="Mới", category="outsource")
        row = conn.execute(
            "SELECT title, category FROM crm_svc_expenses WHERE id = ?", (eid,)
        ).fetchone()
        self.assertEqual(row[0], "Mới")
        self.assertEqual(row[1], "outsource")

    def test_update_amount_and_date(self):
        conn = _setup_conn()
        eid = create_expense(conn, 1, "Chi phí", "khac", 1_000_000, "2026-06-01")
        update_expense(conn, eid, amount_vnd=3_000_000, expense_on="2026-06-20")
        row = conn.execute(
            "SELECT amount_vnd, expense_on FROM crm_svc_expenses WHERE id = ?", (eid,)
        ).fetchone()
        self.assertEqual(row[0], 3_000_000)
        self.assertEqual(row[1], "2026-06-20")

    def test_delete_existing_returns_true(self):
        conn = _setup_conn()
        eid = create_expense(conn, 1, "Chi phí", "khac", 1_000_000, "2026-06-01")
        self.assertTrue(delete_expense(conn, eid))
        self.assertIsNone(
            conn.execute(
                "SELECT id FROM crm_svc_expenses WHERE id = ?", (eid,)
            ).fetchone()
        )

    def test_delete_nonexistent_returns_false(self):
        conn = _setup_conn()
        self.assertFalse(delete_expense(conn, 99999))


class TestGetLatestFinanceScan(unittest.TestCase):
    def test_no_scan_returns_empty_string(self):
        conn = _setup_conn()
        self.assertEqual(get_latest_finance_scan(conn, 1, "health"), "")

    def test_returns_latest_not_first(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_finance_scans (lifecycle_id, ai_output, scan_type, created_at) "
            "VALUES (1, 'health cũ', 'health', '2026-06-23 08:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_finance_scans (lifecycle_id, ai_output, scan_type, created_at) "
            "VALUES (1, 'health mới', 'health', '2026-06-23 09:00:00')"
        )
        conn.commit()
        self.assertEqual(get_latest_finance_scan(conn, 1, "health"), "health mới")

    def test_scan_types_isolated(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_finance_scans (lifecycle_id, ai_output, scan_type, created_at) "
            "VALUES (1, 'health result', 'health', '2026-06-23 08:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_finance_scans (lifecycle_id, ai_output, scan_type, created_at) "
            "VALUES (1, 'forecast result', 'forecast', '2026-06-23 08:00:00')"
        )
        conn.commit()
        self.assertEqual(get_latest_finance_scan(conn, 1, "health"), "health result")
        self.assertEqual(get_latest_finance_scan(conn, 1, "forecast"), "forecast result")


class TestRunAiFinanceScan(unittest.TestCase):
    def test_no_api_key_returns_empty_string(self):
        conn = _setup_conn()
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = run_ai_finance_scan(conn, 1, "health", {
                "service_name": "SEO Tổng thể",
                "customer_name": "KH Test",
                "contract_amount_vnd": 10_000_000,
                "received_revenue": 5_000_000,
                "total_expenses": 2_000_000,
                "profit": 3_000_000,
                "margin_pct": 60.0,
            })
            self.assertEqual(result, "")
        finally:
            if old_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy tests — xác nhận FAIL (module chưa tồn tại)**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -m pytest tests/test_crm_svc_finance.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'crm_svc_finance'`

- [ ] **Step 3: Tạo `crm_svc_finance.py`**

```python
# crm_svc_finance.py
"""Profit & cost tracking per-lifecycle cho PTTP."""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)
_HAIKU = "claude-haiku-4-5-20251001"

_HEALTH_PROMPT = """Bạn là chuyên gia phân tích tài chính dịch vụ digital marketing.

Dịch vụ: {service_name}
Khách hàng: {customer_name}
Doanh thu kỳ vọng (HĐ): {contract_amount_vnd:,} VND
Doanh thu thực nhận: {received_revenue:,} VND
Chi phí phát sinh: {total_expenses:,} VND
Lợi nhuận: {profit:,} VND
Biên lợi nhuận: {margin_pct:.1f}%

Phân tích ngắn gọn (tối đa 200 từ):
1. Đánh giá tình trạng tài chính hiện tại
2. Cảnh báo nếu chi phí > 70% doanh thu thực nhận
3. Gợi ý cụ thể để cải thiện margin"""

_FORECAST_PROMPT = """Bạn là chuyên gia phân tích tài chính dịch vụ digital marketing.

Dịch vụ: {service_name}
Khách hàng: {customer_name}
Doanh thu kỳ vọng (HĐ): {contract_amount_vnd:,} VND
Doanh thu thực nhận: {received_revenue:,} VND
Chi phí đến nay: {total_expenses:,} VND
Lợi nhuận hiện tại: {profit:,} VND
Biên lợi nhuận: {margin_pct:.1f}%
Số ngày đã triển khai: {days_elapsed} ngày
Tổng thời gian HĐ: {contract_days} ngày

Dự báo ngắn gọn (tối đa 200 từ):
1. Burn rate hiện tại = chi phí / ngày
2. Ước tính tổng chi phí đến cuối HĐ
3. Ước tính lợi nhuận và margin cuối kỳ
4. Cảnh báo nếu dự báo margin < 20%"""


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            amount_vnd   INTEGER NOT NULL DEFAULT 0,
            received_on  TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'pending',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_payments_lifecycle ON crm_svc_payments(lifecycle_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_expenses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            title        TEXT NOT NULL DEFAULT '',
            category     TEXT NOT NULL DEFAULT 'khac',
            amount_vnd   INTEGER NOT NULL DEFAULT 0,
            expense_on   TEXT NOT NULL DEFAULT '',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_expenses_lifecycle ON crm_svc_expenses(lifecycle_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_finance_scans (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            ai_output    TEXT NOT NULL DEFAULT '',
            scan_type    TEXT NOT NULL DEFAULT 'health',
            created_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()


def get_summary(
    conn: sqlite3.Connection, lifecycle_id: int, contract_amount_vnd: int
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN status = 'received' THEN amount_vnd ELSE 0 END), 0) AS received_revenue,
            COALESCE(SUM(CASE WHEN status = 'pending'  THEN amount_vnd ELSE 0 END), 0) AS pending_revenue
        FROM crm_svc_payments WHERE lifecycle_id = ?
        """,
        (lifecycle_id,),
    ).fetchone()
    received = int(row[0])
    pending = int(row[1])

    exp_row = conn.execute(
        "SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses WHERE lifecycle_id = ?",
        (lifecycle_id,),
    ).fetchone()
    total_expenses = int(exp_row[0])

    profit = received - total_expenses
    margin_pct = (profit / received * 100) if received > 0 else 0.0
    outstanding = contract_amount_vnd - received

    return {
        "expected_revenue": contract_amount_vnd,
        "received_revenue": received,
        "pending_revenue": pending,
        "total_expenses": total_expenses,
        "profit": profit,
        "margin_pct": round(margin_pct, 2),
        "outstanding": outstanding,
    }


def list_payments(conn: sqlite3.Connection, lifecycle_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_svc_payments WHERE lifecycle_id = ? ORDER BY received_on DESC, id DESC",
        (lifecycle_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_payment(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    amount_vnd: int,
    received_on: str,
    status: str = "pending",
    notes: str = "",
) -> int:
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_svc_payments
            (lifecycle_id, amount_vnd, received_on, status, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (lifecycle_id, amount_vnd, received_on, status, notes, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_payment(
    conn: sqlite3.Connection,
    payment_id: int,
    *,
    amount_vnd: int | None = None,
    received_on: str | None = None,
    status: str | None = None,
    notes: str | None = None,
) -> None:
    ts = _ts()
    sets = ["updated_at = ?"]
    params: list[Any] = [ts]
    if amount_vnd is not None:
        sets.append("amount_vnd = ?")
        params.append(amount_vnd)
    if received_on is not None:
        sets.append("received_on = ?")
        params.append(received_on)
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes)
    params.append(payment_id)
    conn.execute(f"UPDATE crm_svc_payments SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()


def delete_payment(conn: sqlite3.Connection, payment_id: int) -> bool:
    cur = conn.execute("DELETE FROM crm_svc_payments WHERE id = ?", (payment_id,))
    conn.commit()
    return cur.rowcount > 0


def list_expenses(conn: sqlite3.Connection, lifecycle_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_svc_expenses WHERE lifecycle_id = ? ORDER BY expense_on DESC, id DESC",
        (lifecycle_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_expense(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    title: str,
    category: str,
    amount_vnd: int,
    expense_on: str,
    notes: str = "",
) -> int:
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_svc_expenses
            (lifecycle_id, title, category, amount_vnd, expense_on, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (lifecycle_id, title, category, amount_vnd, expense_on, notes, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_expense(
    conn: sqlite3.Connection,
    expense_id: int,
    *,
    title: str | None = None,
    category: str | None = None,
    amount_vnd: int | None = None,
    expense_on: str | None = None,
    notes: str | None = None,
) -> None:
    ts = _ts()
    sets = ["updated_at = ?"]
    params: list[Any] = [ts]
    if title is not None:
        sets.append("title = ?")
        params.append(title)
    if category is not None:
        sets.append("category = ?")
        params.append(category)
    if amount_vnd is not None:
        sets.append("amount_vnd = ?")
        params.append(amount_vnd)
    if expense_on is not None:
        sets.append("expense_on = ?")
        params.append(expense_on)
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes)
    params.append(expense_id)
    conn.execute(f"UPDATE crm_svc_expenses SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()


def delete_expense(conn: sqlite3.Connection, expense_id: int) -> bool:
    cur = conn.execute("DELETE FROM crm_svc_expenses WHERE id = ?", (expense_id,))
    conn.commit()
    return cur.rowcount > 0


def get_latest_finance_scan(
    conn: sqlite3.Connection, lifecycle_id: int, scan_type: str
) -> str:
    row = conn.execute(
        "SELECT ai_output FROM crm_svc_finance_scans "
        "WHERE lifecycle_id = ? AND scan_type = ? ORDER BY id DESC LIMIT 1",
        (lifecycle_id, scan_type),
    ).fetchone()
    return row[0] if row else ""


def run_ai_finance_scan(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    scan_type: str,
    context: dict,
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    prompt_template = _HEALTH_PROMPT if scan_type == "health" else _FORECAST_PROMPT
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
            "INSERT INTO crm_svc_finance_scans "
            "(lifecycle_id, ai_output, scan_type, created_at) VALUES (?, ?, ?, ?)",
            (lifecycle_id, output, scan_type, _ts()),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_finance_scan lỗi lifecycle_id=%s: %s", lifecycle_id, exc)
        return ""
```

- [ ] **Step 4: Chạy tests — xác nhận PASS**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -m pytest tests/test_crm_svc_finance.py -v
```

Expected: tất cả tests PASS. Ghi số tests vào report.

- [ ] **Step 5: Xác nhận import OK**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -c "import crm_svc_finance; print('OK')"
```

Expected: `OK`

---

## Task 2: Wire app.py — import + schema init + 8 routes + update workflow page

**Files:**
- Modify: `app.py` (3 vị trí khác nhau)

**Consumes từ Task 1:**
- `ensure_schema` (alias `_ensure_svc_finance_schema`)
- `get_summary`, `list_payments`, `list_expenses`, `get_latest_finance_scan`, `run_ai_finance_scan`
- `create_payment`, `update_payment`, `delete_payment`
- `create_expense`, `update_expense`, `delete_expense`

- [ ] **Step 1: Thêm import ở line 334 (sau `from crm_svc_risk import ...`)**

Tìm dòng này trong `app.py`:
```python
from crm_svc_risk import ensure_schema as _ensure_svc_risk_schema
```

Thêm ngay sau:
```python
from crm_svc_finance import ensure_schema as _ensure_svc_finance_schema
```

- [ ] **Step 2: Thêm schema init ở line ~2276 (sau `_ensure_svc_risk_schema(conn)`)**

Tìm dòng này:
```python
    _ensure_svc_risk_schema(conn)
```

Thêm ngay sau:
```python
    _ensure_svc_finance_schema(conn)
```

- [ ] **Step 3: Cập nhật `crm_service_workflow_page` — thêm finance data**

Tìm đoạn này trong `crm_service_workflow_page`:
```python
        risks = _risk_list(conn, lifecycle_id=lifecycle_id)
        latest_risk_scan = _risk_latest_scan(conn, lifecycle_id=lifecycle_id)
        tasks_by_stage = _svc_list_tasks(conn, lifecycle_id=lifecycle_id)
        progress = _svc_progress(conn, lifecycle_id=lifecycle_id)
        customer = None
        if lc.get("customer_id"):
            row = conn.execute(
                "SELECT * FROM crm_customers WHERE id = ?", (lc["customer_id"],)
            ).fetchone()
            customer = dict(row) if row else None
```

Thay bằng:
```python
        risks = _risk_list(conn, lifecycle_id=lifecycle_id)
        latest_risk_scan = _risk_latest_scan(conn, lifecycle_id=lifecycle_id)
        tasks_by_stage = _svc_list_tasks(conn, lifecycle_id=lifecycle_id)
        progress = _svc_progress(conn, lifecycle_id=lifecycle_id)
        customer = None
        if lc.get("customer_id"):
            row = conn.execute(
                "SELECT * FROM crm_customers WHERE id = ?", (lc["customer_id"],)
            ).fetchone()
            customer = dict(row) if row else None
        # Finance data
        from crm_svc_finance import (
            get_summary as _fin_summary,
            list_payments as _fin_payments,
            list_expenses as _fin_expenses,
            get_latest_finance_scan as _fin_scan,
        )
        contract_amount_vnd = 0
        if lc.get("contract_id"):
            c_row = conn.execute(
                "SELECT amount_vnd FROM crm_contracts WHERE id = ?",
                (lc["contract_id"],),
            ).fetchone()
            if c_row:
                contract_amount_vnd = int(c_row["amount_vnd"] or 0)
        finance_summary = _fin_summary(conn, lifecycle_id, contract_amount_vnd)
        payments = _fin_payments(conn, lifecycle_id)
        expenses = _fin_expenses(conn, lifecycle_id)
        latest_health_scan = _fin_scan(conn, lifecycle_id, "health")
        latest_forecast_scan = _fin_scan(conn, lifecycle_id, "forecast")
```

- [ ] **Step 4: Thêm các finance fields vào `render_template` call trong `crm_service_workflow_page`**

Tìm đoạn:
```python
        risks=risks,
        latest_risk_scan=latest_risk_scan,
        **_admin_page_template_kwargs(),
```

Thay bằng:
```python
        risks=risks,
        latest_risk_scan=latest_risk_scan,
        finance_summary=finance_summary,
        payments=payments,
        expenses=expenses,
        latest_health_scan=latest_health_scan,
        latest_forecast_scan=latest_forecast_scan,
        **_admin_page_template_kwargs(),
```

- [ ] **Step 5: Thêm 8 routes API sau `api_svc_risk_ai_scan`**

Tìm dòng bắt đầu:
```python
@app.get("/api/crm/service-lifecycle")
def api_svc_lifecycle_list() -> Any:
```

Chèn TRƯỚC dòng đó (sau kết thúc của `api_svc_risk_ai_scan`):

```python

# ── Service Finance Tracking ─────────────────────────────────────────────────

@app.get("/api/crm/svc-finance/<int:lifecycle_id>/summary")
def api_svc_finance_summary(lifecycle_id: int) -> Any:
    from crm_svc_finance import get_summary as _fin_sum
    with get_connection() as conn:
        lc_row = conn.execute(
            "SELECT contract_id FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
        ).fetchone()
        if lc_row is None:
            return jsonify({"error": "Không tìm thấy lifecycle"}), 404
        contract_amount_vnd = 0
        if lc_row["contract_id"]:
            c_row = conn.execute(
                "SELECT amount_vnd FROM crm_contracts WHERE id = ?",
                (lc_row["contract_id"],),
            ).fetchone()
            if c_row:
                contract_amount_vnd = int(c_row["amount_vnd"] or 0)
        summary = _fin_sum(conn, lifecycle_id, contract_amount_vnd)
    return jsonify(summary)


@app.post("/api/crm/svc-payments")
def api_svc_payment_create() -> Any:
    from crm_svc_finance import create_payment as _pay_create
    payload = request.get_json(force=True) or {}
    lifecycle_id = _opt_pos_int(payload.get("lifecycle_id"))
    amount_vnd = _opt_pos_int(payload.get("amount_vnd"))
    received_on = str(payload.get("received_on", "")).strip()[:10]
    status = str(payload.get("status", "pending")).strip()
    notes = str(payload.get("notes", "")).strip()
    if not lifecycle_id or amount_vnd is None or not received_on:
        return jsonify({"error": "Cần lifecycle_id, amount_vnd, received_on"}), 400
    with get_connection() as conn:
        pid = _pay_create(conn, lifecycle_id, amount_vnd, received_on, status, notes)
        row = conn.execute(
            "SELECT * FROM crm_svc_payments WHERE id = ?", (pid,)
        ).fetchone()
    return jsonify(dict(row)), 201


@app.patch("/api/crm/svc-payments/<int:payment_id>")
def api_svc_payment_patch(payment_id: int) -> Any:
    from crm_svc_finance import update_payment as _pay_update
    payload = request.get_json(force=True) or {}
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM crm_svc_payments WHERE id = ?", (payment_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Không tìm thấy payment"}), 404
        amount_vnd = _opt_pos_int(payload.get("amount_vnd")) if "amount_vnd" in payload else None
        _pay_update(
            conn, payment_id,
            amount_vnd=amount_vnd,
            received_on=str(payload["received_on"])[:10] if "received_on" in payload else None,
            status=str(payload["status"]) if "status" in payload else None,
            notes=str(payload["notes"]) if "notes" in payload else None,
        )
        updated = conn.execute(
            "SELECT * FROM crm_svc_payments WHERE id = ?", (payment_id,)
        ).fetchone()
    return jsonify(dict(updated))


@app.delete("/api/crm/svc-payments/<int:payment_id>")
def api_svc_payment_delete(payment_id: int) -> Any:
    from crm_svc_finance import delete_payment as _pay_del
    with get_connection() as conn:
        ok = _pay_del(conn, payment_id)
    if not ok:
        return jsonify({"error": "Không tìm thấy payment"}), 404
    return jsonify({"ok": True})


@app.post("/api/crm/svc-expenses")
def api_svc_expense_create() -> Any:
    from crm_svc_finance import create_expense as _exp_create
    payload = request.get_json(force=True) or {}
    lifecycle_id = _opt_pos_int(payload.get("lifecycle_id"))
    title = str(payload.get("title", "")).strip()[:500]
    category = str(payload.get("category", "khac")).strip()
    amount_vnd = _opt_pos_int(payload.get("amount_vnd"))
    expense_on = str(payload.get("expense_on", "")).strip()[:10]
    notes = str(payload.get("notes", "")).strip()
    if not lifecycle_id or not title or amount_vnd is None or not expense_on:
        return jsonify({"error": "Cần lifecycle_id, title, amount_vnd, expense_on"}), 400
    with get_connection() as conn:
        eid = _exp_create(conn, lifecycle_id, title, category, amount_vnd, expense_on, notes)
        row = conn.execute(
            "SELECT * FROM crm_svc_expenses WHERE id = ?", (eid,)
        ).fetchone()
    return jsonify(dict(row)), 201


@app.patch("/api/crm/svc-expenses/<int:expense_id>")
def api_svc_expense_patch(expense_id: int) -> Any:
    from crm_svc_finance import update_expense as _exp_update
    payload = request.get_json(force=True) or {}
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM crm_svc_expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Không tìm thấy expense"}), 404
        amount_vnd = _opt_pos_int(payload.get("amount_vnd")) if "amount_vnd" in payload else None
        _exp_update(
            conn, expense_id,
            title=str(payload["title"])[:500] if "title" in payload else None,
            category=str(payload["category"]) if "category" in payload else None,
            amount_vnd=amount_vnd,
            expense_on=str(payload["expense_on"])[:10] if "expense_on" in payload else None,
            notes=str(payload["notes"]) if "notes" in payload else None,
        )
        updated = conn.execute(
            "SELECT * FROM crm_svc_expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    return jsonify(dict(updated))


@app.delete("/api/crm/svc-expenses/<int:expense_id>")
def api_svc_expense_delete(expense_id: int) -> Any:
    from crm_svc_finance import delete_expense as _exp_del
    with get_connection() as conn:
        ok = _exp_del(conn, expense_id)
    if not ok:
        return jsonify({"error": "Không tìm thấy expense"}), 404
    return jsonify({"ok": True})


@app.post("/api/crm/svc-finance/<int:lifecycle_id>/ai-scan")
def api_svc_finance_ai_scan(lifecycle_id: int) -> Any:
    from crm_svc_finance import (
        get_summary as _fin_sum,
        run_ai_finance_scan as _fin_scan_fn,
    )
    from crm_svc_tasks import SERVICE_LABELS as _svc_labels
    payload = request.get_json(force=True) or {}
    scan_type = str(payload.get("scan_type", "health")).strip()
    if scan_type not in ("health", "forecast"):
        return jsonify({"error": "scan_type phải là 'health' hoặc 'forecast'"}), 400
    with get_connection() as conn:
        lc = conn.execute(
            "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
        ).fetchone()
        if lc is None:
            return jsonify({"error": "Không tìm thấy lifecycle"}), 404
        lc = dict(lc)
        contract_amount_vnd = 0
        days_elapsed = 0
        contract_days = 0
        if lc.get("contract_id"):
            c_row = conn.execute(
                "SELECT amount_vnd, starts_on, ends_on FROM crm_contracts WHERE id = ?",
                (lc["contract_id"],),
            ).fetchone()
            if c_row:
                contract_amount_vnd = int(c_row["amount_vnd"] or 0)
                try:
                    from datetime import date
                    today = date.today()
                    if c_row["starts_on"]:
                        start = date.fromisoformat(c_row["starts_on"][:10])
                        days_elapsed = max(0, (today - start).days)
                        if c_row["ends_on"]:
                            end = date.fromisoformat(c_row["ends_on"][:10])
                            contract_days = max(0, (end - start).days)
                except (ValueError, TypeError):
                    pass
        summary = _fin_sum(conn, lifecycle_id, contract_amount_vnd)
        customer_name = "KH"
        if lc.get("customer_id"):
            cust = conn.execute(
                "SELECT name FROM crm_customers WHERE id = ?", (lc["customer_id"],)
            ).fetchone()
            if cust:
                customer_name = cust["name"] or "KH"
        ctx = {
            "service_name": _svc_labels.get(lc["service_slug"], lc["service_slug"]),
            "customer_name": customer_name,
            "contract_amount_vnd": summary["expected_revenue"],
            "received_revenue": summary["received_revenue"],
            "total_expenses": summary["total_expenses"],
            "profit": summary["profit"],
            "margin_pct": summary["margin_pct"],
            "days_elapsed": days_elapsed,
            "contract_days": contract_days,
        }
        output = _fin_scan_fn(conn, lifecycle_id, scan_type, ctx)
    return jsonify({"ai_output": output, "scan_type": scan_type, "lifecycle_id": lifecycle_id})
```

- [ ] **Step 6: Xác nhận app import OK và tests vẫn pass**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -c "import app; print('OK')"
```

Expected: `OK`

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: tất cả tests PASS (bao gồm 22 risk tests + 25 finance tests).

---

## Task 3: Finance section trong crm_service_workflow.html

**Files:**
- Modify: `templates/crm_service_workflow.html` (thêm vào cuối, trước `{% endblock %}`)

**Consumes từ Task 2:** Template variables: `finance_summary`, `payments`, `expenses`, `latest_health_scan`, `latest_forecast_scan`, `lifecycle` (có `id` field)

**Note:** Template hiện tại kết thúc ở `</script>\n{% endblock %}` (risk JS block). Ta thay thế `{% endblock %}` cuối cùng bằng finance section + `{% endblock %}`.

- [ ] **Step 1: Tìm đúng chuỗi cuối file để thay thế**

```bash
tail -5 /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/templates/crm_service_workflow.html
```

Expected output:
```
</script>
{% endblock %}
```

- [ ] **Step 2: Thêm finance section vào cuối template**

Tìm đoạn kết thúc file:
```
</script>
{% endblock %}
```

Thay bằng (finance section + đóng file):

```html
</script>

{# ─── Finance Section ─────────────────────────────────────────────────────── #}
<div style="margin-top:2rem;border-top:2px solid #dcfce7;padding-top:1.5rem;">
  <h3 style="margin:0 0 1rem;font-size:.95rem;color:#16a34a;">
    💰 Tài chính dịch vụ
  </h3>

  {# Summary metrics #}
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1.5rem;">
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:.75rem;text-align:center;">
      <div style="font-size:.7rem;color:#666;margin-bottom:.25rem;">Kỳ vọng (HĐ)</div>
      <div style="font-size:1rem;font-weight:700;color:#16a34a;">
        {{ "{:,.0f}".format(finance_summary.expected_revenue) }} ₫
      </div>
    </div>
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:.75rem;text-align:center;">
      <div style="font-size:.7rem;color:#666;margin-bottom:.25rem;">Thực nhận</div>
      <div style="font-size:1rem;font-weight:700;color:#2563eb;">
        {{ "{:,.0f}".format(finance_summary.received_revenue) }} ₫
      </div>
    </div>
    <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:.75rem;text-align:center;">
      <div style="font-size:.7rem;color:#666;margin-bottom:.25rem;">Chi phí</div>
      <div style="font-size:1rem;font-weight:700;color:#dc2626;">
        {{ "{:,.0f}".format(finance_summary.total_expenses) }} ₫
      </div>
    </div>
    <div style="background:{% if finance_summary.margin_pct >= 50 %}#f0fdf4{% elif finance_summary.margin_pct >= 20 %}#fefce8{% else %}#fef2f2{% endif %};
                border:1px solid {% if finance_summary.margin_pct >= 50 %}#bbf7d0{% elif finance_summary.margin_pct >= 20 %}#fef08a{% else %}#fecaca{% endif %};
                border-radius:8px;padding:.75rem;text-align:center;">
      <div style="font-size:.7rem;color:#666;margin-bottom:.25rem;">Lợi nhuận</div>
      <div style="font-size:.95rem;font-weight:700;color:{% if finance_summary.margin_pct >= 50 %}#16a34a{% elif finance_summary.margin_pct >= 20 %}#ca8a04{% else %}#dc2626{% endif %};">
        {{ "{:,.0f}".format(finance_summary.profit) }} ₫
        <span style="font-size:.7rem;font-weight:400;">({{ finance_summary.margin_pct }}%)</span>
      </div>
    </div>
  </div>

  {# ── Payments ── #}
  <div style="margin-bottom:1.5rem;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem;">
      <h4 style="margin:0;font-size:.85rem;color:#374151;">
        Thu tiền
        <span style="font-weight:400;color:#888;font-size:.75rem;">({{ payments|length }} khoản)</span>
      </h4>
    </div>
    {% if payments %}
    <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:.8rem;">
        <thead>
          <tr style="background:#f8fafc;border-bottom:1px solid #e2e8f0;">
            <th style="text-align:left;padding:.4rem .6rem;font-weight:600;">Ngày</th>
            <th style="text-align:right;padding:.4rem .6rem;font-weight:600;">Số tiền</th>
            <th style="text-align:center;padding:.4rem .6rem;font-weight:600;">Trạng thái</th>
            <th style="text-align:left;padding:.4rem .6rem;font-weight:600;">Ghi chú</th>
            <th style="text-align:center;padding:.4rem .6rem;font-weight:600;">Xóa</th>
          </tr>
        </thead>
        <tbody>
          {% for p in payments %}
          <tr style="border-bottom:1px solid #f1f5f9;">
            <td style="padding:.4rem .6rem;">{{ p.received_on or '—' }}</td>
            <td style="padding:.4rem .6rem;text-align:right;font-weight:500;">
              {{ "{:,.0f}".format(p.amount_vnd) }} ₫
            </td>
            <td style="padding:.4rem .6rem;text-align:center;">
              {% if p.status == 'received' %}
              <span style="font-size:.7rem;background:#dcfce7;color:#16a34a;padding:1px 8px;border-radius:3px;">Đã nhận</span>
              {% elif p.status == 'pending' %}
              <span style="font-size:.7rem;background:#fef9c3;color:#ca8a04;padding:1px 8px;border-radius:3px;">Chờ</span>
              {% else %}
              <span style="font-size:.7rem;background:#f3f4f6;color:#9ca3af;padding:1px 8px;border-radius:3px;">Huỷ</span>
              {% endif %}
            </td>
            <td style="padding:.4rem .6rem;color:#555;font-size:.75rem;">{{ p.notes or '—' }}</td>
            <td style="padding:.4rem .6rem;text-align:center;">
              <button onclick="paymentDelete({{ p.id }})"
                      style="padding:1px 7px;border-radius:4px;border:none;cursor:pointer;
                             background:#fee2e2;color:#dc2626;font-size:.72rem;">✕</button>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% else %}
    <p style="color:#aaa;font-size:.8rem;margin:.25rem 0;">Chưa có khoản thu.</p>
    {% endif %}
    <div style="margin-top:.5rem;">
      <details>
        <summary style="font-size:.8rem;color:#16a34a;cursor:pointer;user-select:none;">
          + Thêm khoản thu
        </summary>
        <div style="display:flex;gap:.5rem;margin-top:.5rem;flex-wrap:wrap;align-items:center;">
          <input type="date" id="pay-date"
                 style="padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
          <input type="number" id="pay-amount" placeholder="Số tiền (VND)"
                 style="width:160px;padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
          <select id="pay-status"
                  style="padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
            <option value="pending">Chờ nhận</option>
            <option value="received">Đã nhận</option>
            <option value="cancelled">Huỷ</option>
          </select>
          <input type="text" id="pay-notes" placeholder="Ghi chú"
                 style="flex:1;min-width:120px;padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
          <button onclick="paymentCreate()"
                  style="padding:.35rem .75rem;background:#16a34a;color:#fff;border:none;
                         border-radius:6px;font-size:.8rem;cursor:pointer;">Thêm</button>
        </div>
      </details>
    </div>
  </div>

  {# ── Expenses ── #}
  <div style="margin-bottom:1.5rem;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem;">
      <h4 style="margin:0;font-size:.85rem;color:#374151;">
        Chi phí
        <span style="font-weight:400;color:#888;font-size:.75rem;">({{ expenses|length }} khoản)</span>
      </h4>
    </div>
    {% if expenses %}
    <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:.8rem;">
        <thead>
          <tr style="background:#f8fafc;border-bottom:1px solid #e2e8f0;">
            <th style="text-align:left;padding:.4rem .6rem;font-weight:600;">Ngày</th>
            <th style="text-align:left;padding:.4rem .6rem;font-weight:600;">Nội dung</th>
            <th style="text-align:center;padding:.4rem .6rem;font-weight:600;">Loại</th>
            <th style="text-align:right;padding:.4rem .6rem;font-weight:600;">Số tiền</th>
            <th style="text-align:left;padding:.4rem .6rem;font-weight:600;">Ghi chú</th>
            <th style="text-align:center;padding:.4rem .6rem;font-weight:600;">Xóa</th>
          </tr>
        </thead>
        <tbody>
          {% for e in expenses %}
          <tr style="border-bottom:1px solid #f1f5f9;">
            <td style="padding:.4rem .6rem;">{{ e.expense_on or '—' }}</td>
            <td style="padding:.4rem .6rem;font-weight:500;">{{ e.title }}</td>
            <td style="padding:.4rem .6rem;text-align:center;">
              <span style="font-size:.7rem;background:#e0e7ff;color:#4338ca;
                           padding:1px 6px;border-radius:3px;">{{ e.category }}</span>
            </td>
            <td style="padding:.4rem .6rem;text-align:right;color:#dc2626;font-weight:500;">
              {{ "{:,.0f}".format(e.amount_vnd) }} ₫
            </td>
            <td style="padding:.4rem .6rem;color:#555;font-size:.75rem;">{{ e.notes or '—' }}</td>
            <td style="padding:.4rem .6rem;text-align:center;">
              <button onclick="expenseDelete({{ e.id }})"
                      style="padding:1px 7px;border-radius:4px;border:none;cursor:pointer;
                             background:#fee2e2;color:#dc2626;font-size:.72rem;">✕</button>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% else %}
    <p style="color:#aaa;font-size:.8rem;margin:.25rem 0;">Chưa có chi phí.</p>
    {% endif %}
    <div style="margin-top:.5rem;">
      <details>
        <summary style="font-size:.8rem;color:#dc2626;cursor:pointer;user-select:none;">
          + Thêm chi phí
        </summary>
        <div style="display:flex;gap:.5rem;margin-top:.5rem;flex-wrap:wrap;align-items:center;">
          <input type="date" id="exp-date"
                 style="padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
          <input type="text" id="exp-title" placeholder="Nội dung..."
                 style="flex:2;min-width:150px;padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
          <select id="exp-category"
                  style="padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
            <option value="nhan-cong">Nhân công</option>
            <option value="cong-cu">Công cụ</option>
            <option value="quang-cao">Quảng cáo</option>
            <option value="outsource">Outsource</option>
            <option value="khac">Khác</option>
          </select>
          <input type="number" id="exp-amount" placeholder="Số tiền (VND)"
                 style="width:160px;padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
          <input type="text" id="exp-notes" placeholder="Ghi chú"
                 style="flex:1;min-width:100px;padding:.35rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
          <button onclick="expenseCreate()"
                  style="padding:.35rem .75rem;background:#dc2626;color:#fff;border:none;
                         border-radius:6px;font-size:.8rem;cursor:pointer;">Thêm</button>
        </div>
      </details>
    </div>
  </div>

  {# ── AI Finance Scan ── #}
  <div style="border-top:1px solid #e5e7eb;padding-top:1rem;">
    <div style="display:flex;gap:.5rem;margin-bottom:.5rem;flex-wrap:wrap;">
      <button onclick="financeAiScan('health')" id="fin-health-btn"
              style="padding:.3rem .75rem;background:#0891b2;color:#fff;border:none;
                     border-radius:6px;font-size:.78rem;cursor:pointer;">
        🔍 AI Health Check
      </button>
      <button onclick="financeAiScan('forecast')" id="fin-forecast-btn"
              style="padding:.3rem .75rem;background:#7c3aed;color:#fff;border:none;
                     border-radius:6px;font-size:.78rem;cursor:pointer;">
        📈 AI Dự báo burn rate
      </button>
      <span id="fin-scan-status" style="font-size:.75rem;color:#888;align-self:center;"></span>
    </div>
    {% if latest_health_scan %}
    <div style="background:#ecfeff;border:1px solid #a5f3fc;border-radius:6px;
                padding:.75rem;margin-bottom:.5rem;font-size:.8rem;white-space:pre-wrap;">
      <div style="font-size:.7rem;color:#0891b2;font-weight:600;margin-bottom:.25rem;">Health Check</div>
      <div id="fin-health-output">{{ latest_health_scan }}</div>
    </div>
    {% else %}
    <div id="fin-health-output" style="display:none;background:#ecfeff;border:1px solid #a5f3fc;
         border-radius:6px;padding:.75rem;margin-bottom:.5rem;font-size:.8rem;white-space:pre-wrap;"></div>
    {% endif %}
    {% if latest_forecast_scan %}
    <div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:6px;
                padding:.75rem;font-size:.8rem;white-space:pre-wrap;">
      <div style="font-size:.7rem;color:#7c3aed;font-weight:600;margin-bottom:.25rem;">Dự báo Burn Rate</div>
      <div id="fin-forecast-output">{{ latest_forecast_scan }}</div>
    </div>
    {% else %}
    <div id="fin-forecast-output" style="display:none;background:#f5f3ff;border:1px solid #ddd6fe;
         border-radius:6px;padding:.75rem;font-size:.8rem;white-space:pre-wrap;"></div>
    {% endif %}
  </div>
</div>

<script>
// ─── Finance JS ────────────────────────────────────────────────────────────────
function paymentCreate() {
  const date = document.getElementById('pay-date').value;
  const amount = parseInt(document.getElementById('pay-amount').value || '0', 10);
  const status = document.getElementById('pay-status').value;
  const notes = (document.getElementById('pay-notes').value || '').trim();
  if (!date || !amount) return;
  fetch('/api/crm/svc-payments', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({lifecycle_id: _lifecycleId, amount_vnd: amount, received_on: date, status, notes}),
  }).then(() => location.reload()).catch(console.error);
}

function paymentDelete(paymentId) {
  if (!confirm('Xoá khoản thu này?')) return;
  fetch('/api/crm/svc-payments/' + paymentId, {method: 'DELETE'})
    .then(() => location.reload())
    .catch(console.error);
}

function expenseCreate() {
  const date = document.getElementById('exp-date').value;
  const title = (document.getElementById('exp-title').value || '').trim();
  const category = document.getElementById('exp-category').value;
  const amount = parseInt(document.getElementById('exp-amount').value || '0', 10);
  const notes = (document.getElementById('exp-notes').value || '').trim();
  if (!date || !title || !amount) return;
  fetch('/api/crm/svc-expenses', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({lifecycle_id: _lifecycleId, title, category, amount_vnd: amount, expense_on: date, notes}),
  }).then(() => location.reload()).catch(console.error);
}

function expenseDelete(expenseId) {
  if (!confirm('Xoá chi phí này?')) return;
  fetch('/api/crm/svc-expenses/' + expenseId, {method: 'DELETE'})
    .then(() => location.reload())
    .catch(console.error);
}

function financeAiScan(scanType) {
  const btnId = scanType === 'health' ? 'fin-health-btn' : 'fin-forecast-btn';
  const outId = scanType === 'health' ? 'fin-health-output' : 'fin-forecast-output';
  const btn = document.getElementById(btnId);
  const out = document.getElementById(outId);
  const status = document.getElementById('fin-scan-status');
  if (btn) btn.disabled = true;
  if (status) status.textContent = 'AI đang phân tích...';
  fetch('/api/crm/svc-finance/' + _lifecycleId + '/ai-scan', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({scan_type: scanType}),
  }).then(r => r.json()).then(data => {
    if (out) {
      out.textContent = data.ai_output || '(Không có kết quả)';
      out.style.display = 'block';
    }
    if (status) status.textContent = '';
    if (btn) btn.disabled = false;
  }).catch(err => {
    if (status) status.textContent = 'Lỗi: ' + err;
    if (btn) btn.disabled = false;
  });
}
</script>
{% endblock %}
```

- [ ] **Step 3: Xác nhận template hợp lệ**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -c "import app; print('OK')"
```

Expected: `OK`

```bash
grep -c "paymentCreate\|paymentDelete\|expenseCreate\|expenseDelete\|financeAiScan\|fin-health-output\|fin-forecast-output" /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/templates/crm_service_workflow.html
```

Expected: `7`

---

## Task 4: crm_financials.html + /crm/financials page route

**Files:**
- Create: `templates/crm_financials.html`
- Modify: `app.py` (thêm 1 route `/crm/financials`)

**Consumes từ Task 2:** `get_summary`, `list_payments` (tính qua summary), `_admin_page_template_kwargs`, auth pattern

**Note:** Trang này query TẤT CẢ lifecycles có status='active', join customer + contract, tính summary, sort margin_pct ASC (rủi ro cao lên đầu).

- [ ] **Step 1: Tạo `templates/crm_financials.html`**

```html
{% extends "admin_layout.html" %}
{% block admin_main %}
<div style="padding:1.5rem;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;">
    <h2 style="margin:0;font-size:1.1rem;font-weight:700;">
      💰 Tổng hợp tài chính dịch vụ
    </h2>
    <span style="font-size:.8rem;color:#888;">{{ rows|length }} lifecycle đang hoạt động</span>
  </div>

  {% if rows %}
  <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-size:.82rem;">
      <thead>
        <tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0;">
          <th style="text-align:left;padding:.6rem .75rem;font-weight:600;white-space:nowrap;">Khách hàng</th>
          <th style="text-align:left;padding:.6rem .75rem;font-weight:600;white-space:nowrap;">Dịch vụ</th>
          <th style="text-align:center;padding:.6rem .5rem;font-weight:600;">Stage</th>
          <th style="text-align:right;padding:.6rem .75rem;font-weight:600;white-space:nowrap;">Kỳ vọng (HĐ)</th>
          <th style="text-align:right;padding:.6rem .75rem;font-weight:600;white-space:nowrap;">Thực nhận</th>
          <th style="text-align:right;padding:.6rem .75rem;font-weight:600;white-space:nowrap;">Chi phí</th>
          <th style="text-align:right;padding:.6rem .75rem;font-weight:600;white-space:nowrap;">Lợi nhuận</th>
          <th style="text-align:center;padding:.6rem .5rem;font-weight:600;">Margin</th>
          <th style="text-align:center;padding:.6rem .5rem;font-weight:600;"></th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        {% set m = row.margin_pct %}
        <tr style="border-bottom:1px solid #f1f5f9;
                   {% if m < 20 %}background:#fff5f5;{% elif m < 50 %}background:#fffbeb;{% endif %}">
          <td style="padding:.5rem .75rem;font-weight:500;">
            {{ row.customer_name or '—' }}
          </td>
          <td style="padding:.5rem .75rem;color:#555;">{{ row.service_label }}</td>
          <td style="padding:.5rem .5rem;text-align:center;">
            <span style="font-size:.7rem;background:#e0e7ff;color:#4338ca;
                         padding:1px 8px;border-radius:3px;">{{ row.stage }}</span>
          </td>
          <td style="padding:.5rem .75rem;text-align:right;color:#374151;">
            {{ "{:,.0f}".format(row.expected_revenue) }} ₫
          </td>
          <td style="padding:.5rem .75rem;text-align:right;color:#2563eb;font-weight:500;">
            {{ "{:,.0f}".format(row.received_revenue) }} ₫
          </td>
          <td style="padding:.5rem .75rem;text-align:right;color:#dc2626;">
            {{ "{:,.0f}".format(row.total_expenses) }} ₫
          </td>
          <td style="padding:.5rem .75rem;text-align:right;font-weight:600;
                     color:{% if row.profit >= 0 %}#16a34a{% else %}#dc2626{% endif %};">
            {{ "{:,.0f}".format(row.profit) }} ₫
          </td>
          <td style="padding:.5rem .5rem;text-align:center;">
            <span style="font-size:.8rem;font-weight:700;padding:2px 10px;border-radius:4px;
                         background:{% if m >= 50 %}#dcfce7{% elif m >= 20 %}#fef9c3{% else %}#fee2e2{% endif %};
                         color:{% if m >= 50 %}#16a34a{% elif m >= 20 %}#ca8a04{% else %}#dc2626{% endif %};">
              {{ m }}%
            </span>
          </td>
          <td style="padding:.5rem .5rem;text-align:center;">
            <a href="/crm/service-delivery/{{ row.lifecycle_id }}"
               style="font-size:.75rem;color:#6366f1;text-decoration:none;">Xem →</a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <p style="color:#aaa;text-align:center;padding:3rem;">Chưa có lifecycle nào đang hoạt động.</p>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 2: Thêm `/crm/financials` route vào `app.py`**

Tìm dòng bắt đầu của `api_svc_finance_summary` route:
```python
@app.get("/api/crm/svc-finance/<int:lifecycle_id>/summary")
```

Chèn TRƯỚC dòng đó:

```python
@app.get("/crm/financials")
def crm_financials_page() -> Any:
    redir = _ensure_admin_session_html()
    if redir is not None:
        return redir
    from crm_svc_finance import get_summary as _fin_sum
    from crm_svc_tasks import SERVICE_LABELS as _svc_labels
    with get_connection() as conn:
        lcs = conn.execute(
            """
            SELECT lc.id, lc.service_slug, lc.stage, lc.contract_id, lc.customer_id,
                   cu.name AS customer_name
            FROM crm_service_lifecycle lc
            LEFT JOIN crm_customers cu ON cu.id = lc.customer_id
            WHERE lc.status = 'active'
            ORDER BY lc.id
            """
        ).fetchall()
        rows = []
        for lc in lcs:
            lc = dict(lc)
            contract_amount_vnd = 0
            if lc.get("contract_id"):
                c_row = conn.execute(
                    "SELECT amount_vnd FROM crm_contracts WHERE id = ?",
                    (lc["contract_id"],),
                ).fetchone()
                if c_row:
                    contract_amount_vnd = int(c_row["amount_vnd"] or 0)
            summary = _fin_sum(conn, lc["id"], contract_amount_vnd)
            rows.append({
                "lifecycle_id": lc["id"],
                "service_slug": lc["service_slug"],
                "service_label": _svc_labels.get(lc["service_slug"], lc["service_slug"]),
                "stage": lc["stage"],
                "customer_name": lc.get("customer_name") or "—",
                **summary,
            })
    rows.sort(key=lambda r: r["margin_pct"])
    return render_template(
        "crm_financials.html",
        rows=rows,
        **_admin_page_template_kwargs(),
    )


```

- [ ] **Step 3: Xác nhận app import OK**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Xác nhận route và template tồn tại**

```bash
grep -c "crm_financials_page\|/crm/financials" /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/app.py
```

Expected: `2` (decorator + function)

```bash
ls /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP/templates/crm_financials.html
```

Expected: file tồn tại

- [ ] **Step 5: Chạy toàn bộ test suite lần cuối**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -15
```

Expected: tất cả tests PASS.

---

## Self-Review

Kiểm tra spec coverage:
- [x] Schema 3 tables (`crm_svc_payments`, `crm_svc_expenses`, `crm_svc_finance_scans`) — Task 1
- [x] `get_summary` returns đủ 7 fields — Task 1
- [x] Division-by-zero guard khi `received_revenue=0` — Task 1 step 3
- [x] `list_payments` ORDER BY received_on DESC, id DESC — Task 1
- [x] `list_expenses` ORDER BY expense_on DESC, id DESC — Task 1
- [x] AI fail silent (no API key → `""`) — Task 1 + `run_ai_finance_scan`
- [x] Hai scan types isolated (health / forecast) — `get_latest_finance_scan` + test
- [x] Schema init trong `app.py` — Task 2 step 2
- [x] `contract_amount_vnd` từ `crm_contracts.amount_vnd` — Task 2 step 3
- [x] 8 API routes — Task 2 step 5
- [x] Finance section trong workflow template — Task 3
- [x] `/crm/financials` trang tổng hợp sort margin_pct ASC — Task 4
- [x] Margin badge màu: đỏ <20%, vàng 20-50%, xanh >50% — Task 4 step 1
- [x] `days_elapsed` và `contract_days` cho forecast prompt — Task 2 step 5 (`api_svc_finance_ai_scan`)
- [x] Health prompt context đủ fields — `_HEALTH_PROMPT` trong `crm_svc_finance.py`
- [x] Forecast prompt context đủ fields — `_FORECAST_PROMPT`

Không có placeholder, type inconsistency, hay scope gap.
