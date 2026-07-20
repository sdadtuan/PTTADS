"""Portal ↔ SEO customer bridge (Phase 5C)."""
from __future__ import annotations

import os
import sqlite3
from typing import Any

from ptt_seo.content import approve_stage, get_content, list_content
from ptt_seo.governance import evaluate_content_publish
from ptt_seo.report import dashboard


def portal_seo_enabled() -> bool:
    return os.environ.get("PTT_PORTAL_SEO_ENABLED", "0").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def customer_id_for_portal_client(conn: sqlite3.Connection, client_id: str) -> int | None:
    active_val: bool | int = True if getattr(conn, "backend", "sqlite") == "pg" else 1
    row = conn.execute(
        """
        SELECT customer_id FROM seo_portal_client_map
        WHERE client_id = ? AND active = ?
        """,
        (client_id.strip(), active_val),
    ).fetchone()
    if row is None:
        return None
    return int(dict(row)["customer_id"])


def portal_client_for_customer(conn: sqlite3.Connection, customer_id: int) -> str | None:
    active_val: bool | int = True if getattr(conn, "backend", "sqlite") == "pg" else 1
    row = conn.execute(
        """
        SELECT client_id FROM seo_portal_client_map
        WHERE customer_id = ? AND active = ?
        """,
        (customer_id, active_val),
    ).fetchone()
    if row is None:
        return None
    return str(dict(row)["client_id"])


def upsert_portal_map(conn: sqlite3.Connection, *, client_id: str, customer_id: int) -> None:
    from datetime import datetime

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    backend = getattr(conn, "backend", "sqlite")
    active_val: bool | int = True if backend == "pg" else 1
    conn.execute(
        """
        INSERT INTO seo_portal_client_map (client_id, customer_id, active, created_at)
        VALUES (?,?,?,?)
        ON CONFLICT(client_id) DO UPDATE SET customer_id=excluded.customer_id, active=excluded.active
        """,
        (client_id.strip(), customer_id, active_val, ts),
    )
    conn.commit()


PORTAL_REPORT_TYPES: frozenset[str] = frozenset({"executive", "seo", "aeo", "technical", "content"})


def _sanitize_portal_dashboard(data: dict[str, Any]) -> dict[str, Any]:
    """Strip internal fields — client portal read-only."""
    out = dict(data)
    issues = out.get("issues")
    if isinstance(issues, list):
        out["issues"] = [
            {
                "url": i.get("url") or "",
                "issue_type": i.get("issue_type") or "",
                "severity": i.get("severity") or "",
                "status": i.get("status") or "",
            }
            for i in issues
            if isinstance(i, dict)
        ]
    mentions = out.get("mentions_recent")
    if isinstance(mentions, list):
        out["mentions_recent"] = [
            {
                "stat_date": m.get("stat_date"),
                "mention_count": m.get("mention_count"),
                "citation_status": m.get("citation_status"),
            }
            for m in mentions
            if isinstance(m, dict)
        ]
    sync_runs = out.get("sync_runs_recent") or out.get("sync_runs")
    if isinstance(sync_runs, list):
        key = "sync_runs_recent" if "sync_runs_recent" in out else "sync_runs"
        out[key] = [
            {
                "source": r.get("source") or r.get("connector") or "",
                "status": r.get("status") or "",
                "finished_at": r.get("finished_at") or r.get("created_at"),
            }
            for r in sync_runs
            if isinstance(r, dict)
        ]
    return out


def portal_executive_report(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    dashboard_type: str = "executive",
) -> dict[str, Any]:
    dtype = dashboard_type if dashboard_type in PORTAL_REPORT_TYPES else "executive"
    raw = dashboard(conn, customer_id=customer_id, dashboard_type=dtype)
    return {
        "ok": True,
        "customer_id": customer_id,
        "dashboard_type": dtype,
        "report": _sanitize_portal_dashboard(raw),
        "generated_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def portal_summary(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    exec_dash = portal_executive_report(conn, customer_id, dashboard_type="executive")["report"]
    pending = list_content(conn, customer_id, workflow_status="client_review")
    return {
        "seo_enabled": True,
        "customer_id": customer_id,
        "executive": exec_dash,
        "pending_client_review": len(pending),
    }


def portal_pending_content(conn: sqlite3.Connection, customer_id: int) -> list[dict[str, Any]]:
    items = list_content(conn, customer_id, workflow_status="client_review")
    return [
        {
            "id": i["id"],
            "title": i["title"],
            "content_type": i["content_type"],
            "due_date": i.get("due_date"),
            "updated_at": i.get("updated_at"),
        }
        for i in items
    ]


def portal_content_detail(conn: sqlite3.Connection, customer_id: int, content_id: int) -> dict[str, Any] | None:
    item = get_content(conn, content_id)
    if item is None or int(item["customer_id"]) != customer_id:
        return None
    return {
        "id": item["id"],
        "title": item["title"],
        "content_type": item["content_type"],
        "workflow_status": item["workflow_status"],
        "body_html": item.get("body_html") or "",
        "brief": item.get("brief") or {},
        "approvals": item.get("approvals") or [],
    }


def portal_review_content(
    conn: sqlite3.Connection,
    *,
    customer_id: int,
    content_id: int,
    approved: bool,
    actor_id: str = "",
    notes: str = "",
) -> dict[str, Any]:
    item = get_content(conn, content_id)
    if item is None or int(item["customer_id"]) != customer_id:
        raise ValueError("Content không tồn tại")
    if item["workflow_status"] != "client_review":
        raise ValueError("Content không ở giai đoạn client_review")
    if approved:
        eval_result = evaluate_content_publish(conn, content_id=content_id, action="approve")
        if not eval_result["ok"]:
            keys = ", ".join(v["policy_key"] for v in eval_result["violations"])
            raise ValueError(f"Governance block: {keys}")
    return approve_stage(
        conn,
        content_id,
        "client_review",
        approved=approved,
        actor_id=actor_id,
        notes=notes,
    )


def verify_internal_token(auth_header: str) -> bool:
    expected = (
        os.environ.get("PTT_PORTAL_SEO_SERVICE_TOKEN")
        or os.environ.get("PTT_CRM_INTERNAL_KEY")
        or ""
    ).strip()
    if not expected:
        return False
    token = auth_header.replace("Bearer ", "").strip()
    return token == expected


def seed_e2e_client_review_content(
    conn: sqlite3.Connection,
    *,
    customer_id: int,
    title: str | None = None,
) -> dict[str, Any]:
    """Governance-compliant client_review item for portal E2E / pilot UAT."""
    from datetime import datetime

    from ptt_seo.content import create_content
    from ptt_seo.governance import seed_default_policies
    from ptt_seo.workflow import record_approval

    seed_default_policies(conn, customer_id=customer_id)
    item_title = title or f"E2E Portal SEO {datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    content_id = create_content(
        conn,
        {
            "customer_id": customer_id,
            "title": item_title,
            "workflow_status": "client_review",
            "body_html": "<p>E2E portal client review — approve via portal.</p>",
            "brief": {
                "primary_topic": "seo pilot keyword",
                "meta_title": "E2E Meta Title",
                "meta_description": "E2E meta description for portal approve test.",
                "checklist": ["Schema phù hợp", "Internal links"],
            },
        },
    )
    for stage in ("seo_review", "aeo_review", "technical_review"):
        record_approval(
            conn,
            content_id=content_id,
            stage=stage,
            status="approved",
            actor_id="e2e-seed",
        )
    conn.commit()
    return {"id": content_id, "title": item_title, "customer_id": customer_id}
