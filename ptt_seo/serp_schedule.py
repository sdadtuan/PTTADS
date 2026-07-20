"""Scheduled SERP capture for active keywords (Gate B)."""
from __future__ import annotations

import sqlite3
from typing import Any

from ptt_seo.serp_provider import capture_serp_snapshot


def _top_keywords(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, phrase FROM seo_keywords
        WHERE customer_id = ? AND status = 'active' AND phrase != ''
        ORDER BY COALESCE(opportunity_score, 0) DESC, COALESCE(volume, 0) DESC, id ASC
        LIMIT ?
        """,
        (customer_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def capture_serp_for_customer(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    limit: int = 5,
    domain_hint: str = "",
) -> dict[str, Any]:
    """Capture SERP snapshots for top opportunity keywords of one client."""
    keywords = _top_keywords(conn, customer_id, limit=limit)
    captured: list[dict[str, Any]] = []
    errors: list[str] = []
    for kw in keywords:
        try:
            snap = capture_serp_snapshot(
                conn,
                customer_id,
                phrase=str(kw["phrase"]),
                keyword_id=int(kw["id"]),
                domain_hint=domain_hint,
            )
            captured.append({"keyword_id": kw["id"], "phrase": kw["phrase"], "snapshot_id": snap["id"], "source": snap["source"]})
        except ValueError as exc:
            errors.append(f"{kw['phrase']}: {exc}")
    return {
        "customer_id": customer_id,
        "captured": len(captured),
        "snapshots": captured,
        "errors": errors,
    }


def capture_serp_all_customers(
    conn: sqlite3.Connection,
    *,
    per_customer_limit: int = 5,
    max_customers: int | None = None,
) -> dict[str, Any]:
    """Weekly/daily SERP job — all clients with active keywords."""
    rows = conn.execute(
        """
        SELECT DISTINCT customer_id FROM seo_keywords
        WHERE status = 'active' AND phrase != ''
        ORDER BY customer_id ASC
        """
    ).fetchall()
    customer_ids = [int(r["customer_id"]) for r in rows]
    if max_customers is not None:
        customer_ids = customer_ids[: max(0, max_customers)]

    results: list[dict[str, Any]] = []
    total_captured = 0
    for cid in customer_ids:
        from ptt_seo.client_settings import get_settings

        domains = get_settings(conn, cid).get("domains") or []
        hint = str(domains[0] if domains else "").replace("https://", "").replace("http://", "").split("/")[0]
        row = capture_serp_for_customer(conn, cid, limit=per_customer_limit, domain_hint=hint)
        total_captured += row["captured"]
        results.append(row)

    return {
        "ok": True,
        "customers": len(customer_ids),
        "snapshots_captured": total_captured,
        "results": results,
    }
