"""Live rank capture from SERP provider + share of voice (Gate E6)."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any
from urllib.parse import urlparse

from ptt_seo.rank_tracker import add_tracked_keyword, list_tracked_keywords, record_snapshot
from ptt_seo.serp_provider import fetch_serp_results


def _domain_match(url: str, domain_hint: str) -> bool:
    if not url or not domain_hint:
        return False
    host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    hint = domain_hint.lower().replace("https://", "").replace("http://", "").split("/")[0]
    return hint in host or host.endswith("." + hint)


def _position_for_domain(results: list[dict[str, Any]], domain_hint: str) -> tuple[float | None, str]:
    for row in results:
        url = str(row.get("url") or "")
        if _domain_match(url, domain_hint):
            pos = row.get("position")
            try:
                return float(pos), url
            except (TypeError, ValueError):
                return None, url
    return None, ""


def capture_ranks_for_customer(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    domain_hint: str = "",
) -> dict[str, Any]:
    """Fetch SERP for each tracked keyword and record position snapshots."""
    if not domain_hint:
        from ptt_seo.client_settings import get_settings

        domains = get_settings(conn, customer_id).get("domains") or []
        domain_hint = str(domains[0] if domains else "").replace("https://", "").replace("http://", "").split("/")[0]

    tracked = list_tracked_keywords(conn, customer_id)
    snap_date = date.today().isoformat()
    captured = 0
    errors: list[str] = []

    for kw in tracked:
        phrase = str(kw.get("phrase") or "").strip()
        if not phrase:
            continue
        try:
            results, source = fetch_serp_results(phrase, domain_hint=domain_hint)
            position, url_found = _position_for_domain(results, domain_hint)
            record_snapshot(
                conn,
                int(kw["id"]),
                snapshot_date=snap_date,
                position=position,
                url_found=url_found,
                source=source,
            )
            captured += 1
        except ValueError as exc:
            errors.append(f"{phrase}: {exc}")

    return {
        "customer_id": customer_id,
        "captured": captured,
        "domain_hint": domain_hint,
        "errors": errors,
    }


def capture_ranks_all_customers(
    conn: sqlite3.Connection,
    *,
    max_customers: int | None = None,
) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT DISTINCT customer_id FROM seo_rank_tracked_keywords
        WHERE status = 'active'
        ORDER BY customer_id
        """
    ).fetchall()
    customer_ids = [int(r["customer_id"]) for r in rows]
    if max_customers is not None:
        customer_ids = customer_ids[: max(0, max_customers)]

    results: list[dict[str, Any]] = []
    total = 0
    for cid in customer_ids:
        row = capture_ranks_for_customer(conn, cid)
        total += row.get("captured", 0)
        results.append(row)
    return {"ok": True, "customers": len(customer_ids), "snapshots_captured": total, "results": results}


def share_of_voice(conn: sqlite3.Connection, customer_id: int, *, top_n: int = 10) -> dict[str, Any]:
    """Share of voice = % tracked keywords with position in top N."""
    from ptt_seo.client_settings import get_settings

    domains = get_settings(conn, customer_id).get("domains") or []
    domain_hint = str(domains[0] if domains else "").replace("https://", "").replace("http://", "").split("/")[0]
    tracked = list_tracked_keywords(conn, customer_id)
    if not tracked:
        return {"customer_id": customer_id, "tracked": 0, "in_top_n": 0, "sov_pct": 0.0, "top_n": top_n}

    in_top = 0
    for kw in tracked:
        pos = kw.get("latest_position")
        if pos is not None and float(pos) <= top_n:
            in_top += 1
    total = len(tracked)
    return {
        "customer_id": customer_id,
        "domain_hint": domain_hint,
        "tracked": total,
        "in_top_n": in_top,
        "sov_pct": round(in_top * 100.0 / total, 2),
        "top_n": top_n,
    }


def sync_tracked_from_keywords(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    limit: int = 20,
) -> int:
    """Ensure top opportunity keywords are in rank tracker."""
    rows = conn.execute(
        """
        SELECT id, phrase FROM seo_keywords
        WHERE customer_id = ? AND status = 'active' AND phrase != ''
        ORDER BY COALESCE(opportunity_score, 0) DESC, COALESCE(volume, 0) DESC
        LIMIT ?
        """,
        (customer_id, limit),
    ).fetchall()
    existing = {str(k["phrase"]).lower() for k in list_tracked_keywords(conn, customer_id)}
    added = 0
    for row in rows:
        phrase = str(row["phrase"])
        if phrase.lower() in existing:
            continue
        add_tracked_keyword(conn, customer_id, {"phrase": phrase, "keyword_id": row["id"]})
        existing.add(phrase.lower())
        added += 1
    return added
