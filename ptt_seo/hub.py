"""SEO/AEO hub — cross-client summary (mirror facebook_ads_hub)."""
from __future__ import annotations

from typing import Any

from ptt_seo.constants import SEO_AEO_SERVICE_SLUGS
from ptt_seo.content import count_by_status
from ptt_seo.technical import count_open_critical


def _seo_conn(seo_conn: Any, crm_conn: Any) -> Any:
    return seo_conn if seo_conn is not None else crm_conn


def _aeo_totals(seo_conn: Any, customer_ids: list[int]) -> dict[int, dict[str, int]]:
    if not customer_ids:
        return {}
    try:
        from ptt_seo.aeo_store import list_aeo_questions
        from ptt_seo.db import SeoDB
    except ImportError:
        return {}
    db = seo_conn if isinstance(seo_conn, SeoDB) else SeoDB(seo_conn, "sqlite")
    out: dict[int, dict[str, int]] = {}
    for cid in customer_ids:
        qs = list_aeo_questions(db, cid)
        out[cid] = {
            "total": len(qs),
            "visible": sum(1 for q in qs if int(q.get("brand_visible") or 0) == 1),
        }
    return out


def _settings_configured(seo_conn: Any, customer_id: int) -> bool:
    row = seo_conn.execute(
        "SELECT domains_json, industry FROM seo_client_settings WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    if row is None:
        return False
    domains = row["domains_json"]
    if isinstance(domains, list):
        return bool(domains) or bool((row["industry"] or "").strip())
    domains_text = domains or "[]"
    return domains_text not in ("[]", "") or bool((row["industry"] or "").strip())


def compute_health_score(
    *,
    settings_ok: bool,
    aeo_coverage_pct: float,
    aeo_queries: int,
    critical_issues: int,
    content_overdue: int = 0,
) -> int:
    """0–100 client health score for executive overview."""
    score = 50
    if settings_ok:
        score += 15
    else:
        score -= 20
    if aeo_queries > 0:
        score += int(min(25, aeo_coverage_pct * 0.25))
    else:
        score += 10
    score -= min(30, critical_issues * 10)
    score -= min(15, content_overdue * 3)
    return max(0, min(100, score))


def _health_tier(score: int) -> str:
    if score >= 75:
        return "good"
    if score >= 50:
        return "warn"
    return "bad"


def content_delivery_summary(seo_conn: Any) -> dict[str, int]:
    seo = seo_conn
    rows = seo.execute(
        """
        SELECT workflow_status, COUNT(*) AS c FROM seo_content
        WHERE workflow_status != 'archived'
        GROUP BY workflow_status
        """
    ).fetchall()
    by_status = {str(r["workflow_status"]): int(r["c"]) for r in rows}
    in_writing = by_status.get("in_writing", 0)
    in_review = sum(
        by_status.get(st, 0)
        for st in ("seo_review", "aeo_review", "technical_review", "client_review")
    )
    overdue_row = seo.execute(
        """
        SELECT COUNT(*) AS c FROM seo_content
        WHERE workflow_status NOT IN ('published', 'monitoring', 'archived')
          AND due_date IS NOT NULL
          AND due_date < date('now')
        """
    ).fetchone()
    overdue = int(overdue_row["c"] or 0) if overdue_row else 0
    return {
        "in_writing": in_writing,
        "in_review": in_review,
        "overdue": overdue,
        "published": by_status.get("published", 0) + by_status.get("monitoring", 0),
        "by_status": by_status,
    }


def list_open_critical_issues(
    seo_conn: Any,
    crm_conn: Any,
    *,
    customer_id: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    sql = """
        SELECT id, customer_id, url, issue_type, severity, status, discovered_at
        FROM seo_technical_issues
        WHERE severity = 'critical' AND status NOT IN ('closed', 'verified')
    """
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    sql += " ORDER BY discovered_at DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = seo_conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        cid = int(d.get("customer_id") or 0)
        name = ""
        if cid and crm_conn is not None:
            cu = crm_conn.execute(
                "SELECT name FROM crm_customers WHERE id = ?", (cid,)
            ).fetchone()
            name = cu["name"] if cu else ""
        d["customer_name"] = name
        out.append(d)
    return out


def _client_critical_count(seo: Any, customer_id: int) -> int:
    row = seo.execute(
        """
        SELECT COUNT(*) AS c FROM seo_technical_issues
        WHERE customer_id = ? AND severity = 'critical'
          AND status NOT IN ('closed', 'verified')
        """,
        (customer_id,),
    ).fetchone()
    return int(row["c"] or 0) if row else 0


def _client_content_overdue(seo: Any, customer_id: int) -> int:
    row = seo.execute(
        """
        SELECT COUNT(*) AS c FROM seo_content
        WHERE customer_id = ?
          AND workflow_status NOT IN ('published', 'monitoring', 'archived')
          AND due_date IS NOT NULL
          AND due_date < date('now')
        """,
        (customer_id,),
    ).fetchone()
    return int(row["c"] or 0) if row else 0


def seo_hub_summary(
    crm_conn: Any,
    seo_conn: Any | None = None,
    *,
    customer_id: int | None = None,
    days: int = 90,
    market: str | None = None,
) -> dict[str, Any]:
    seo = _seo_conn(seo_conn, crm_conn)
    slug_placeholders = ",".join("?" for _ in SEO_AEO_SERVICE_SLUGS)
    lifecycle_rows = crm_conn.execute(
        f"""
        SELECT lc.id AS lifecycle_id, lc.customer_id, lc.service_slug, lc.stage, lc.status,
               c.name AS customer_name, c.company AS customer_company
        FROM crm_service_lifecycle lc
        JOIN crm_customers c ON c.id = lc.customer_id
        WHERE lc.service_slug IN ({slug_placeholders})
          AND COALESCE(lc.status, 'active') != 'cancelled'
        ORDER BY c.name, lc.id DESC
        """,
        tuple(SEO_AEO_SERVICE_SLUGS),
    ).fetchall()

    customer_ids = sorted({int(r["customer_id"]) for r in lifecycle_rows})
    aeo_by_customer = _aeo_totals(seo, customer_ids)

    clients_map: dict[int, dict[str, Any]] = {}
    for row in lifecycle_rows:
        cid = int(row["customer_id"])
        if cid not in clients_map:
            visible = aeo_by_customer.get(cid, {}).get("visible", 0)
            total_aeo = aeo_by_customer.get(cid, {}).get("total", 0)
            coverage = round(100.0 * visible / total_aeo, 1) if total_aeo else 0.0
            proj_count = seo.execute(
                "SELECT COUNT(*) AS c FROM seo_projects WHERE customer_id = ? AND status = 'active'",
                (cid,),
            ).fetchone()
            init_active = seo.execute(
                """
                SELECT COUNT(*) AS c FROM seo_initiatives
                WHERE customer_id = ? AND status IN ('planned', 'in_progress')
                """,
                (cid,),
            ).fetchone()
            settings_ok = _settings_configured(seo, cid)
            crit = _client_critical_count(seo, cid)
            overdue = _client_content_overdue(seo, cid)
            health = compute_health_score(
                settings_ok=settings_ok,
                aeo_coverage_pct=coverage,
                aeo_queries=total_aeo,
                critical_issues=crit,
                content_overdue=overdue,
            )
            from ptt_seo.client_settings import get_settings

            st = get_settings(seo, cid)
            clients_map[cid] = {
                "customer_id": cid,
                "customer_name": row["customer_name"] or "",
                "customer_company": row["customer_company"] or "",
                "settings_ok": settings_ok,
                "domains": st.get("domains") or [],
                "markets": st.get("markets") or [],
                "contract_tier": st.get("contract_tier") or "standard",
                "active_projects": int(proj_count["c"] or 0) if proj_count else 0,
                "active_initiatives": int(init_active["c"] or 0) if init_active else 0,
                "aeo_queries": total_aeo,
                "aeo_visible": visible,
                "aeo_coverage_pct": coverage,
                "critical_issues": crit,
                "content_overdue": overdue,
                "health_score": health,
                "health_tier": _health_tier(health),
                "lifecycles": [],
            }
        clients_map[cid]["lifecycles"].append(
            {
                "lifecycle_id": int(row["lifecycle_id"]),
                "service_slug": row["service_slug"],
                "stage": row["stage"],
                "status": row["status"],
            }
        )

    clients = list(clients_map.values())
    if customer_id is not None:
        clients = [c for c in clients if c["customer_id"] == customer_id]
    if market:
        market_upper = market.strip().upper()
        clients = [
            c
            for c in clients
            if any(str(m).upper() == market_upper for m in (c.get("markets") or []))
        ]
    total_aeo_q = sum(c["aeo_queries"] for c in clients)
    total_visible = sum(c["aeo_visible"] for c in clients)
    settings_missing = sum(1 for c in clients if not c["settings_ok"])

    alerts: list[dict[str, str]] = []
    if settings_missing:
        alerts.append(
            {
                "severity": "warn",
                "message": f"{settings_missing} client SEO chưa cấu hình domain/industry.",
                "link": "/crm/seo/clients",
                "link_label": "Xem client",
            }
        )
    critical = count_open_critical(seo)
    if critical:
        alerts.append(
            {
                "severity": "danger",
                "message": f"{critical} issue kỹ thuật nghiêm trọng (critical) đang mở.",
                "link": "/crm/seo/technical",
                "link_label": "Technical Console",
            }
        )
    open_alerts_row = seo.execute(
        "SELECT COUNT(*) AS c FROM seo_alerts WHERE status = 'open'"
    ).fetchone()
    open_alerts = int(open_alerts_row["c"] or 0) if open_alerts_row else 0
    if open_alerts:
        alerts.append(
            {
                "severity": "warn",
                "message": f"{open_alerts} cảnh báo automation đang mở.",
                "link": "/crm/seo/automations",
                "link_label": "Automations",
            }
        )

    failed_sync_row = seo.execute(
        """
        SELECT COUNT(*) AS c FROM seo_sync_runs
        WHERE status IN ('failed', 'error')
          AND started_at >= datetime('now', '-7 days')
        """
    ).fetchone()
    failed_sync_runs = int(failed_sync_row["c"] or 0) if failed_sync_row else 0
    if failed_sync_runs:
        alerts.append(
            {
                "severity": "danger",
                "message": f"{failed_sync_runs} lần sync GSC/GA4 thất bại trong 7 ngày qua.",
                "link": "/crm/seo/reports?type=ops",
                "link_label": "Xem sync runs",
            }
        )

    for c in clients:
        if c["aeo_queries"] > 0 and c["aeo_coverage_pct"] < 50:
            alerts.append(
                {
                    "severity": "warn",
                    "message": f"AEO coverage thấp ({c['aeo_coverage_pct']}%) — {c['customer_name']}.",
                    "link": f"/crm/seo/clients/{c['customer_id']}",
                    "link_label": "Mở client",
                }
            )

    from ptt_seo.connectors.gsc import gsc_daily_trend, gsc_summary

    cid_filter = customer_id if customer_id is not None else None
    if len(clients) == 1:
        cid_filter = clients[0]["customer_id"]
    delivery = content_delivery_summary(seo)
    gsc_trend = gsc_daily_trend(seo, days=days, customer_id=cid_filter)
    gsc_totals = gsc_summary(seo, cid_filter, days=min(days, 28)) if cid_filter else {}
    if not cid_filter:
        agg = seo.execute(
            f"""
            SELECT COALESCE(SUM(clicks),0) AS clicks, COALESCE(SUM(impressions),0) AS impressions
            FROM seo_gsc_daily_stats
            WHERE stat_date >= date('now', '-{min(days, 28)} days')
            """
        ).fetchone()
        clicks = int(agg["clicks"] or 0) if agg else 0
        impressions = int(agg["impressions"] or 0) if agg else 0
        gsc_totals = {
            "clicks": clicks,
            "impressions": impressions,
            "avg_ctr": round(clicks / impressions, 4) if impressions else 0.0,
        }
    prev_clicks = sum(p["clicks"] for p in gsc_trend[: max(1, len(gsc_trend) // 2)])
    recent_clicks = sum(p["clicks"] for p in gsc_trend[max(1, len(gsc_trend) // 2) :])
    organic_growth_pct = (
        round(100.0 * (recent_clicks - prev_clicks) / prev_clicks, 1) if prev_clicks else 0.0
    )

    return {
        "ok": True,
        "summary": {
            "seo_clients": len(clients),
            "active_lifecycles": len(lifecycle_rows),
            "aeo_queries_total": total_aeo_q,
            "aeo_visible_total": total_visible,
            "aeo_coverage_pct": round(100.0 * total_visible / total_aeo_q, 1) if total_aeo_q else 0.0,
            "settings_missing": settings_missing,
            "active_initiatives": sum(c["active_initiatives"] for c in clients),
            "critical_issues": critical,
            "open_alerts": open_alerts,
            "failed_sync_runs": failed_sync_runs,
            "organic_growth_pct": organic_growth_pct,
            "publish_sla_pct": round(
                100.0
                * delivery["published"]
                / max(1, delivery["published"] + delivery["overdue"] + delivery["in_review"]),
                1,
            ),
        },
        "clients": clients,
        "alerts": alerts,
        "executive": {
            "gsc_trend": gsc_trend,
            "gsc_totals": gsc_totals,
            "content_delivery": delivery,
            "critical_issues": list_open_critical_issues(seo, crm_conn, customer_id=cid_filter, limit=8),
            "filters": {"customer_id": customer_id, "days": days, "market": market},
        },
    }


def customer_workspace(
    crm_conn: Any, customer_id: int, seo_conn: Any | None = None
) -> dict[str, Any] | None:
    seo = _seo_conn(seo_conn, crm_conn)
    row = crm_conn.execute(
        "SELECT id, name, company FROM crm_customers WHERE id = ?",
        (customer_id,),
    ).fetchone()
    if row is None:
        return None

    from ptt_seo.client_settings import get_settings
    from ptt_seo.initiatives import list_initiatives

    lifecycles = [
        dict(r)
        for r in crm_conn.execute(
            f"""
            SELECT id, service_slug, stage, status, created_at
            FROM crm_service_lifecycle
            WHERE customer_id = ? AND service_slug IN ({",".join("?" * len(SEO_AEO_SERVICE_SLUGS))})
            ORDER BY id DESC
            """,
            (customer_id, *SEO_AEO_SERVICE_SLUGS),
        ).fetchall()
    ]
    hub_part = seo_hub_summary(crm_conn, seo, customer_id=customer_id)
    client_row = next((c for c in hub_part["clients"] if c["customer_id"] == customer_id), None)
    kw_count = seo.execute(
        "SELECT COUNT(*) AS c FROM seo_keywords WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    content_counts = count_by_status(seo, customer_id)
    content_pipe = sum(content_counts.values())
    tech_crit = _client_critical_count(seo, customer_id)
    from ptt_seo.research import list_opportunities

    opportunities = list_opportunities(seo, customer_id, min_score=50.0)[:5]
    tab_badges = {
        "technical": tech_crit,
        "content": _client_content_overdue(seo, customer_id),
        "aeo": 1 if (client_row or {}).get("aeo_coverage_pct", 100) < 50 else 0,
    }
    return {
        "customer": dict(row),
        "settings": get_settings(seo, customer_id),
        "lifecycles": lifecycles,
        "initiatives": list_initiatives(seo, customer_id),
        "metrics": client_row or {},
        "overview": {
            "keywords": int(kw_count["c"] or 0) if kw_count else 0,
            "content_pipeline": content_pipe,
            "technical_issues": tech_crit,
            "aeo_coverage_pct": (client_row or {}).get("aeo_coverage_pct", 0),
            "opportunities": opportunities,
        },
        "tab_badges": tab_badges,
    }


def client_tab_badges(seo_conn: Any, customer_id: int) -> dict[str, int]:
    seo = seo_conn
    crit = _client_critical_count(seo, customer_id)
    overdue = _client_content_overdue(seo, customer_id)
    aeo_row = seo.execute(
        "SELECT COUNT(*) AS t, SUM(CASE WHEN brand_visible = 1 THEN 1 ELSE 0 END) AS v FROM seo_questions WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    total = int(aeo_row["t"] or 0) if aeo_row else 0
    visible = int(aeo_row["v"] or 0) if aeo_row else 0
    cov = 100.0 * visible / total if total else 100.0
    return {
        "technical": crit,
        "content": overdue,
        "aeo": 1 if total and cov < 50 else 0,
    }


def nav_badges(crm_conn: Any, seo_conn: Any | None = None) -> dict[str, int]:
    seo = _seo_conn(seo_conn, crm_conn)
    review_row = seo.execute(
        """
        SELECT COUNT(*) AS c FROM seo_content
        WHERE workflow_status IN ('seo_review', 'aeo_review', 'technical_review', 'client_review')
        """
    ).fetchone()
    content_pending = int(review_row["c"] or 0) if review_row else 0
    critical = count_open_critical(seo)
    hub = seo_hub_summary(crm_conn, seo)
    low_aeo = sum(
        1 for c in hub["clients"] if c["aeo_queries"] > 0 and c["aeo_coverage_pct"] < 50
    )
    open_alerts = int(hub["summary"].get("open_alerts") or 0)
    return {
        "content": content_pending,
        "technical": critical,
        "aeo": low_aeo,
        "automations": open_alerts,
    }
