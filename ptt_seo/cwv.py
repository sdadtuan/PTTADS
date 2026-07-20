"""Core Web Vitals capture via PageSpeed Insights API (Gate D)."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def cwv_enabled() -> bool:
    return os.getenv("PTT_CWV_ENABLED", "1").strip().lower() not in ("0", "false", "no")


def pagespeed_api_key() -> str:
    return (
        os.getenv("PAGESPEED_API_KEY")
        or os.getenv("GOOGLE_PAGESPEED_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip()


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _rating(lcp_ms: float | None, cls: float | None, inp_ms: float | None) -> str:
    """Rough pass/fail from CWV thresholds (LCP≤2500ms, CLS≤0.1, INP≤200ms)."""
    if lcp_ms is None and cls is None and inp_ms is None:
        return "unknown"
    fails = 0
    checks = 0
    if lcp_ms is not None:
        checks += 1
        if lcp_ms > 2500:
            fails += 1
    if cls is not None:
        checks += 1
        if cls > 0.1:
            fails += 1
    if inp_ms is not None:
        checks += 1
        if inp_ms > 200:
            fails += 1
    if checks == 0:
        return "unknown"
    return "fail" if fails else "pass"


def parse_pagespeed_response(data: dict[str, Any]) -> dict[str, Any]:
    lh = data.get("lighthouseResult") or {}
    audits = lh.get("audits") or {}
    categories = lh.get("categories") or {}
    perf = categories.get("performance") or {}

    def audit_value(key: str) -> float | None:
        aud = audits.get(key) or {}
        raw = aud.get("numericValue")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    lcp = audit_value("largest-contentful-paint")
    cls = audit_value("cumulative-layout-shift")
    inp = audit_value("interaction-to-next-paint") or audit_value("experimental-interaction-to-next-paint")
    score = perf.get("score")
    performance_score = float(score) * 100 if score is not None else None
    return {
        "lcp_ms": lcp,
        "cls": cls,
        "inp_ms": inp,
        "performance_score": performance_score,
        "cwv_rating": _rating(lcp, cls, inp),
    }


def fetch_pagespeed(url: str, *, strategy: str = "mobile") -> dict[str, Any]:
    """Call PageSpeed Insights v5. Returns parsed metrics or raises."""
    api_key = pagespeed_api_key()
    if not api_key:
        raise ValueError("pagespeed_api_key_missing")
    qs = urllib.parse.urlencode(
        {
            "url": url,
            "strategy": strategy,
            "category": "performance",
            "key": api_key,
        }
    )
    req_url = f"https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed?{qs}"
    req = urllib.request.Request(req_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise ValueError(f"pagespeed_http_{exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"pagespeed_network: {exc.reason or exc}") from exc
    metrics = parse_pagespeed_response(payload)
    metrics["source"] = "pagespeed"
    metrics["url"] = url
    return metrics


def _stub_pagespeed(url: str) -> dict[str, Any]:
    return {
        "url": url,
        "lcp_ms": 2100.0,
        "cls": 0.05,
        "inp_ms": 180.0,
        "performance_score": 82.0,
        "cwv_rating": "pass",
        "source": "stub",
    }


def effective_pagespeed(url: str) -> dict[str, Any]:
    if os.getenv("PTT_CWV_STUB", "0").strip().lower() in ("1", "true", "yes"):
        return _stub_pagespeed(url)
    return fetch_pagespeed(url)


def insert_cwv_snapshot(conn: sqlite3.Connection, customer_id: int, metrics: dict[str, Any]) -> int:
    cur = conn.execute(
        """
        INSERT INTO seo_cwv_snapshots (
            customer_id, url, lcp_ms, cls, inp_ms, performance_score, cwv_rating, source, checked_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            str(metrics.get("url") or ""),
            metrics.get("lcp_ms"),
            metrics.get("cls"),
            metrics.get("inp_ms"),
            metrics.get("performance_score"),
            str(metrics.get("cwv_rating") or "unknown"),
            str(metrics.get("source") or "pagespeed"),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _urls_for_customer(conn: sqlite3.Connection, customer_id: int, *, limit: int = 3) -> list[str]:
    rows = conn.execute(
        """
        SELECT url FROM seo_pages
        WHERE customer_id = ? AND url != ''
        ORDER BY COALESCE(last_crawled_at, created_at) DESC, id DESC
        LIMIT ?
        """,
        (customer_id, limit),
    ).fetchall()
    urls = [str(r["url"]) for r in rows if r["url"]]
    if urls:
        return urls
    from ptt_seo.client_settings import get_settings

    domains = get_settings(conn, customer_id).get("domains") or []
    out: list[str] = []
    for d in domains[:limit]:
        d = str(d).strip()
        if not d:
            continue
        if not d.startswith("http"):
            d = "https://" + d
        out.append(d.rstrip("/") + "/")
    return out


def capture_cwv_for_customer(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    limit: int = 3,
) -> dict[str, Any]:
    urls = _urls_for_customer(conn, customer_id, limit=limit)
    if not urls:
        return {"customer_id": customer_id, "captured": 0, "skipped": True, "reason": "no_urls"}
    captured: list[dict[str, Any]] = []
    errors: list[str] = []
    for url in urls:
        try:
            metrics = effective_pagespeed(url)
            snap_id = insert_cwv_snapshot(conn, customer_id, metrics)
            captured.append({"snapshot_id": snap_id, "url": url, "cwv_rating": metrics.get("cwv_rating")})
        except ValueError as exc:
            errors.append(f"{url}: {exc}")
    return {
        "customer_id": customer_id,
        "captured": len(captured),
        "snapshots": captured,
        "errors": errors,
    }


def list_cwv_snapshots(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM seo_cwv_snapshots
        WHERE customer_id = ?
        ORDER BY checked_at DESC, id DESC
        LIMIT ?
        """,
        (customer_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def cwv_summary(conn: sqlite3.Connection, customer_id: int, *, days: int = 30) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN cwv_rating = 'pass' THEN 1 ELSE 0 END) AS pass_count,
            AVG(lcp_ms) AS avg_lcp,
            AVG(cls) AS avg_cls,
            AVG(inp_ms) AS avg_inp,
            AVG(performance_score) AS avg_score
        FROM seo_cwv_snapshots
        WHERE customer_id = ? AND checked_at >= date('now', ?)
        """,
        (customer_id, f"-{max(1, days)} days"),
    ).fetchone()
    if row is None or int(row["total"] or 0) == 0:
        return {
            "customer_id": customer_id,
            "total": 0,
            "pass_count": 0,
            "pass_rate_pct": 0.0,
            "avg_lcp_ms": None,
            "avg_cls": None,
            "avg_inp_ms": None,
            "avg_performance_score": None,
        }
    total = int(row["total"] or 0)
    passed = int(row["pass_count"] or 0)
    return {
        "customer_id": customer_id,
        "total": total,
        "pass_count": passed,
        "pass_rate_pct": round(100.0 * passed / total, 2) if total else 0.0,
        "avg_lcp_ms": round(float(row["avg_lcp"]), 1) if row["avg_lcp"] is not None else None,
        "avg_cls": round(float(row["avg_cls"]), 4) if row["avg_cls"] is not None else None,
        "avg_inp_ms": round(float(row["avg_inp"]), 1) if row["avg_inp"] is not None else None,
        "avg_performance_score": round(float(row["avg_score"]), 1) if row["avg_score"] is not None else None,
    }


def capture_cwv_all_customers(
    conn: sqlite3.Connection,
    *,
    per_customer_limit: int = 3,
    max_customers: int | None = None,
) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT DISTINCT customer_id FROM (
            SELECT customer_id FROM seo_pages WHERE url != ''
            UNION SELECT customer_id FROM seo_client_settings
        ) ORDER BY customer_id
        """
    ).fetchall()
    customer_ids = [int(r["customer_id"]) for r in rows]
    if max_customers is not None:
        customer_ids = customer_ids[: max(0, max_customers)]

    results: list[dict[str, Any]] = []
    total = 0
    for cid in customer_ids:
        row = capture_cwv_for_customer(conn, cid, limit=per_customer_limit)
        total += row.get("captured", 0)
        results.append(row)
    return {"ok": True, "customers": len(customer_ids), "snapshots_captured": total, "results": results}
