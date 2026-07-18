"""Sổ quỹ chủ DN — snapshot số dư ngân hàng/tiền mặt + dự báo cash 30 ngày."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from crm_svc_finance import get_ar_aging, resolve_payment_due_on

CASH_SOURCE_MANUAL = "manual"
CASH_SOURCE_BANK = "bank"
CASH_SOURCES = (CASH_SOURCE_MANUAL, CASH_SOURCE_BANK)

POSITION_SOURCE_LEDGER = "ledger"
POSITION_SOURCE_PROXY = "proxy"

OVERDUE_COLLECTION_RATE = 0.5


def ensure_cash_ledger_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_owner_cash_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_on TEXT NOT NULL,
            balance_vnd INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_owner_cash_snapshots_on
        ON crm_owner_cash_snapshots(snapshot_on)
        """
    )
    conn.commit()


def _parse_ymd(raw: str) -> date | None:
    text = str(raw or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _sum_received_between(conn: sqlite3.Connection, start: date, end: date) -> int:
    if start > end:
        return 0
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0)
        FROM crm_svc_payments
        WHERE status = 'received'
          AND substr(received_on, 1, 10) >= ?
          AND substr(received_on, 1, 10) <= ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return int(row[0] if row else 0)


def _sum_expenses_between(conn: sqlite3.Connection, start: date, end: date) -> int:
    if start > end:
        return 0
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0)
        FROM crm_svc_expenses
        WHERE substr(expense_on, 1, 10) >= ?
          AND substr(expense_on, 1, 10) <= ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return int(row[0] if row else 0)


def _proxy_cash_position(conn: sqlite3.Connection, as_of: date) -> int:
    recv = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_payments
        WHERE status = 'received' AND substr(received_on, 1, 10) <= ?
        """,
        (as_of.isoformat(),),
    ).fetchone()
    exp = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses
        WHERE substr(expense_on, 1, 10) <= ?
        """,
        (as_of.isoformat(),),
    ).fetchone()
    return int(recv[0] if recv else 0) - int(exp[0] if exp else 0)


def get_cash_snapshot_on_or_before(
    conn: sqlite3.Connection, as_of: date
) -> dict[str, Any] | None:
    ensure_cash_ledger_schema(conn)
    row = conn.execute(
        """
        SELECT id, snapshot_on, balance_vnd, source, notes, updated_at
        FROM crm_owner_cash_snapshots
        WHERE snapshot_on <= ?
        ORDER BY snapshot_on DESC
        LIMIT 1
        """,
        (as_of.isoformat(),),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row[0]),
        "snapshot_on": str(row[1]),
        "balance_vnd": int(row[2] or 0),
        "source": str(row[3] or CASH_SOURCE_MANUAL),
        "notes": str(row[4] or ""),
        "updated_at": str(row[5] or ""),
    }


def list_cash_snapshots(
    conn: sqlite3.Connection, *, limit: int = 24
) -> list[dict[str, Any]]:
    ensure_cash_ledger_schema(conn)
    rows = conn.execute(
        """
        SELECT id, snapshot_on, balance_vnd, source, notes, updated_at
        FROM crm_owner_cash_snapshots
        ORDER BY snapshot_on DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    return [
        {
            "id": int(r[0]),
            "snapshot_on": str(r[1]),
            "balance_vnd": int(r[2] or 0),
            "source": str(r[3] or CASH_SOURCE_MANUAL),
            "notes": str(r[4] or ""),
            "updated_at": str(r[5] or ""),
        }
        for r in rows
    ]


def upsert_cash_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_on: date | str,
    balance_vnd: int,
    source: str = CASH_SOURCE_MANUAL,
    notes: str = "",
) -> dict[str, Any]:
    ensure_cash_ledger_schema(conn)
    snap_d = _parse_ymd(str(snapshot_on)) if not isinstance(snapshot_on, date) else snapshot_on
    if snap_d is None:
        raise ValueError("snapshot_on không hợp lệ (YYYY-MM-DD).")
    src = str(source or CASH_SOURCE_MANUAL).strip().lower()
    if src not in CASH_SOURCES:
        src = CASH_SOURCE_MANUAL
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    balance = int(balance_vnd)
    conn.execute(
        """
        INSERT INTO crm_owner_cash_snapshots
            (snapshot_on, balance_vnd, source, notes, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_on) DO UPDATE SET
            balance_vnd = excluded.balance_vnd,
            source = excluded.source,
            notes = excluded.notes,
            updated_at = excluded.updated_at
        """,
        (snap_d.isoformat(), balance, src, str(notes or "").strip(), ts),
    )
    conn.commit()
    row = conn.execute(
        """
        SELECT id, snapshot_on, balance_vnd, source, notes, updated_at
        FROM crm_owner_cash_snapshots
        WHERE snapshot_on = ?
        """,
        (snap_d.isoformat(),),
    ).fetchone()
    assert row is not None
    return {
        "id": int(row[0]),
        "snapshot_on": str(row[1]),
        "balance_vnd": int(row[2] or 0),
        "source": str(row[3] or CASH_SOURCE_MANUAL),
        "notes": str(row[4] or ""),
        "updated_at": str(row[5] or ""),
    }


def delete_cash_snapshot(conn: sqlite3.Connection, snapshot_on: date | str) -> bool:
    ensure_cash_ledger_schema(conn)
    snap_d = _parse_ymd(str(snapshot_on)) if not isinstance(snapshot_on, date) else snapshot_on
    if snap_d is None:
        raise ValueError("snapshot_on không hợp lệ.")
    cur = conn.execute(
        "DELETE FROM crm_owner_cash_snapshots WHERE snapshot_on = ?",
        (snap_d.isoformat(),),
    )
    conn.commit()
    return int(cur.rowcount or 0) > 0


def get_cash_position(conn: sqlite3.Connection, as_of: date) -> dict[str, Any]:
    """
    Số dư tại cuối ngày as_of.
    Ưu tiên snapshot sổ quỹ gần nhất + dòng tiền CRM sau ngày snapshot.
    Fallback: proxy thu − chi lũy kế.
    """
    snapshot = get_cash_snapshot_on_or_before(conn, as_of)
    if snapshot is None:
        return {
            "as_of": as_of.isoformat(),
            "position_vnd": _proxy_cash_position(conn, as_of),
            "source": POSITION_SOURCE_PROXY,
            "snapshot": None,
            "flow_adjustment_vnd": 0,
        }

    snap_on = _parse_ymd(snapshot["snapshot_on"])
    assert snap_on is not None
    base = int(snapshot["balance_vnd"])
    if snap_on >= as_of:
        return {
            "as_of": as_of.isoformat(),
            "position_vnd": base,
            "source": POSITION_SOURCE_LEDGER,
            "snapshot": snapshot,
            "flow_adjustment_vnd": 0,
        }

    flow_start = snap_on + timedelta(days=1)
    cash_in = _sum_received_between(conn, flow_start, as_of)
    cash_out = _sum_expenses_between(conn, flow_start, as_of)
    adjustment = cash_in - cash_out
    return {
        "as_of": as_of.isoformat(),
        "position_vnd": base + adjustment,
        "source": POSITION_SOURCE_LEDGER,
        "snapshot": snapshot,
        "flow_adjustment_vnd": adjustment,
        "flow_cash_in_vnd": cash_in,
        "flow_cash_out_vnd": cash_out,
    }


def _ar_collectible_30d(conn: sqlite3.Connection, as_of: date) -> dict[str, int]:
    horizon = as_of + timedelta(days=30)
    ar = get_ar_aging(conn, as_of=as_of.isoformat())
    due_future = 0
    overdue = 0
    for item in ar.get("items") or []:
        amount = int(item.get("amount_vnd") or 0)
        if amount <= 0:
            continue
        due_d = _parse_ymd(resolve_payment_due_on(item))
        if due_d is None:
            continue
        if due_d <= as_of:
            overdue += amount
        elif due_d <= horizon:
            due_future += amount
    overdue_collect = int(round(overdue * OVERDUE_COLLECTION_RATE))
    return {
        "ar_due_future_vnd": due_future,
        "ar_overdue_vnd": overdue,
        "ar_overdue_collect_vnd": overdue_collect,
        "ar_inflow_vnd": due_future + overdue_collect,
    }


def build_cash_forecast_30d(
    conn: sqlite3.Connection,
    as_of: date,
    *,
    current_position: int,
) -> dict[str, Any]:
    """
    Dự báo cash 30 ngày:
    số dư hiện tại + AR thu trong hạn (100%) + AR quá hạn (50%) − chi TB 30 ngày gần nhất.
    """
    start = as_of - timedelta(days=29)
    cash_in_30 = _sum_received_between(conn, start, as_of)
    cash_out_30 = _sum_expenses_between(conn, start, as_of)
    avg_daily_net = (cash_in_30 - cash_out_30) / 30.0
    avg_daily_out = cash_out_30 / 30.0

    ar_part = _ar_collectible_30d(conn, as_of)
    projected_out = int(round(avg_daily_out * 30))
    enhanced = int(current_position + ar_part["ar_inflow_vnd"] - projected_out)
    trend_only = int(current_position + avg_daily_net * 30)

    position_meta = get_cash_position(conn, as_of)
    return {
        "as_of": as_of.isoformat(),
        "forecast_vnd": enhanced,
        "trend_forecast_vnd": trend_only,
        "current_position_vnd": int(current_position),
        "position_source": position_meta.get("source"),
        "avg_daily_net_vnd": round(avg_daily_net, 0),
        "avg_daily_outflow_vnd": round(avg_daily_out, 0),
        "projected_outflow_30d_vnd": projected_out,
        "ar_due_future_vnd": ar_part["ar_due_future_vnd"],
        "ar_overdue_vnd": ar_part["ar_overdue_vnd"],
        "ar_overdue_collect_vnd": ar_part["ar_overdue_collect_vnd"],
        "ar_inflow_vnd": ar_part["ar_inflow_vnd"],
        "method": "ledger_ar_expense"
        if position_meta.get("source") == POSITION_SOURCE_LEDGER
        else "proxy_ar_expense",
    }


def cash_position_note(meta: dict[str, Any]) -> str:
    if meta.get("source") == POSITION_SOURCE_LEDGER:
        snap = meta.get("snapshot") or {}
        snap_on = snap.get("snapshot_on") or "—"
        src = snap.get("source") or CASH_SOURCE_MANUAL
        return f"Sổ quỹ: snapshot {snap_on} ({src}) + dòng tiền CRM."
    return "Proxy dòng tiền — nhập snapshot sổ quỹ để chính xác hơn."


def cash_forecast_note(forecast: dict[str, Any]) -> str:
    ar_in = int(forecast.get("ar_inflow_vnd") or 0)
    out = int(forecast.get("projected_outflow_30d_vnd") or 0)
    return (
        f"Dự báo: số dư + AR thu {ar_in:,} − chi TB 30 ngày {out:,} "
        f"(quá hạn thu {int(OVERDUE_COLLECTION_RATE * 100)}%)."
    ).replace(",", ".")
