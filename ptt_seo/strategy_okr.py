"""S-05 OKR/KPI tree — goal → KPI → initiative (Gate E1)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def list_goals(conn: sqlite3.Connection, customer_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM seo_strategy_goals
        WHERE customer_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_goal(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Thiếu title")
    cur = conn.execute(
        """
        INSERT INTO seo_strategy_goals (
            customer_id, title, description, period, status, sort_order, created_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            title,
            str(payload.get("description") or ""),
            str(payload.get("period") or ""),
            str(payload.get("status") or "active"),
            int(payload.get("sort_order") or 0),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def create_kpi(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    goal_id = int(payload["goal_id"])
    goal = conn.execute(
        "SELECT id FROM seo_strategy_goals WHERE id = ? AND customer_id = ?",
        (goal_id, customer_id),
    ).fetchone()
    if goal is None:
        raise ValueError("Goal không tồn tại")
    label = str(payload.get("metric_label") or payload.get("metric_key") or "").strip()
    if not label:
        raise ValueError("Thiếu metric_label")
    cur = conn.execute(
        """
        INSERT INTO seo_strategy_kpis (
            customer_id, goal_id, initiative_id, metric_key, metric_label,
            target_value, current_value, unit, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            goal_id,
            payload.get("initiative_id"),
            str(payload.get("metric_key") or label.lower().replace(" ", "_")),
            label,
            payload.get("target_value"),
            payload.get("current_value"),
            str(payload.get("unit") or ""),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_kpi_current(
    conn: sqlite3.Connection,
    kpi_id: int,
    *,
    current_value: float | None,
) -> dict[str, Any]:
    conn.execute(
        "UPDATE seo_strategy_kpis SET current_value = ?, updated_at = ? WHERE id = ?",
        (current_value, _ts(), kpi_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM seo_strategy_kpis WHERE id = ?", (kpi_id,)).fetchone()
    if row is None:
        raise ValueError("KPI không tồn tại")
    return dict(row)


def link_initiative_to_goal(
    conn: sqlite3.Connection,
    customer_id: int,
    initiative_id: int,
    goal_id: int | None,
) -> None:
    row = conn.execute(
        "SELECT id FROM seo_initiatives WHERE id = ? AND customer_id = ?",
        (initiative_id, customer_id),
    ).fetchone()
    if row is None:
        raise ValueError("Initiative không tồn tại")
    if goal_id is not None:
        g = conn.execute(
            "SELECT id FROM seo_strategy_goals WHERE id = ? AND customer_id = ?",
            (goal_id, customer_id),
        ).fetchone()
        if g is None:
            raise ValueError("Goal không tồn tại")
    conn.execute(
        "UPDATE seo_initiatives SET goal_id = ? WHERE id = ? AND customer_id = ?",
        (goal_id, initiative_id, customer_id),
    )
    conn.commit()


def _initiatives_for_goal(conn: sqlite3.Connection, customer_id: int, goal_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM seo_initiatives
        WHERE customer_id = ? AND goal_id = ?
        ORDER BY id DESC
        """,
        (customer_id, goal_id),
    ).fetchall()
    return [dict(r) for r in rows]


def okr_tree(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    """Goal → KPIs + linked initiatives."""
    goals = list_goals(conn, customer_id)
    kpi_rows = conn.execute(
        "SELECT * FROM seo_strategy_kpis WHERE customer_id = ? ORDER BY id ASC",
        (customer_id,),
    ).fetchall()
    kpis_by_goal: dict[int, list[dict[str, Any]]] = {}
    for row in kpi_rows:
        k = dict(row)
        kpis_by_goal.setdefault(int(k["goal_id"]), []).append(k)

    tree: list[dict[str, Any]] = []
    for goal in goals:
        gid = int(goal["id"])
        tree.append(
            {
                **goal,
                "kpis": kpis_by_goal.get(gid, []),
                "initiatives": _initiatives_for_goal(conn, customer_id, gid),
            }
        )
    unlinked = conn.execute(
        """
        SELECT * FROM seo_initiatives
        WHERE customer_id = ? AND (goal_id IS NULL OR goal_id = 0)
        ORDER BY id DESC
        """,
        (customer_id,),
    ).fetchall()
    return {
        "customer_id": customer_id,
        "goals": tree,
        "unlinked_initiatives": [dict(r) for r in unlinked],
    }


def refresh_kpi_metrics(conn: sqlite3.Connection, customer_id: int) -> int:
    """Pull current values from live SEO metrics into KPI rows."""
    updated = 0
    kpis = conn.execute(
        "SELECT * FROM seo_strategy_kpis WHERE customer_id = ?",
        (customer_id,),
    ).fetchall()
    for kpi in kpis:
        key = str(dict(kpi).get("metric_key") or "")
        val = _metric_value(conn, customer_id, key)
        if val is None:
            continue
        update_kpi_current(conn, int(kpi["id"]), current_value=val)
        updated += 1
    return updated


def _metric_value(conn: sqlite3.Connection, customer_id: int, metric_key: str) -> float | None:
    key = metric_key.strip().lower()
    if key in ("gsc_clicks", "organic_clicks"):
        row = conn.execute(
            """
            SELECT COALESCE(SUM(clicks), 0) AS v FROM seo_gsc_daily_stats
            WHERE customer_id = ? AND stat_date >= date('now', '-28 days')
            """,
            (customer_id,),
        ).fetchone()
        return float(row["v"] or 0) if row else 0.0
    if key in ("content_published", "published_count"):
        row = conn.execute(
            """
            SELECT COUNT(*) AS v FROM seo_content
            WHERE customer_id = ? AND workflow_status = 'published'
            """,
            (customer_id,),
        ).fetchone()
        return float(row["v"] or 0) if row else 0.0
    if key in ("aeo_coverage", "aeo_coverage_pct"):
        row = conn.execute(
            """
            SELECT COUNT(*) AS t,
                   SUM(CASE WHEN COALESCE(m.brand_visible, 0) = 1 THEN 1 ELSE 0 END) AS v
            FROM seo_questions q
            LEFT JOIN seo_ai_mentions m ON m.id = (
                SELECT id FROM seo_ai_mentions WHERE question_id = q.id ORDER BY id DESC LIMIT 1
            )
            WHERE q.customer_id = ? AND q.status = 'active'
            """,
            (customer_id,),
        ).fetchone()
        if not row or int(row["t"] or 0) == 0:
            return 0.0
        return round(100.0 * int(row["v"] or 0) / int(row["t"]), 2)
    if key in ("organic_revenue", "revenue"):
        from ptt_seo.attribution import organic_revenue_total

        return organic_revenue_total(conn, customer_id, days=28)
    if key in ("share_of_voice", "sov"):
        from ptt_seo.rank_live import share_of_voice

        sov = share_of_voice(conn, customer_id)
        return float(sov.get("sov_pct") or 0)
    if key in ("cwv_pass_rate",):
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN cwv_rating = 'pass' THEN 1 ELSE 0 END) * 100.0
                / NULLIF(COUNT(*), 0) AS v
            FROM seo_cwv_snapshots
            WHERE customer_id = ? AND checked_at >= date('now', '-30 days')
            """,
            (customer_id,),
        ).fetchone()
        return float(row["v"] or 0) if row and row["v"] is not None else None
    return None
