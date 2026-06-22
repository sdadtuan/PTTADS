"""Hàng đợi leadgen Facebook — retry khi Graph API chưa trả dữ liệu."""
from __future__ import annotations

import json
import sqlite3
from typing import Any


def ensure_facebook_pending_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_facebook_pending (
            leadgen_id TEXT PRIMARY KEY,
            page_id TEXT NOT NULL DEFAULT '',
            form_id TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'webhook',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_fb_pending_updated ON crm_facebook_pending(updated_at)"
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_facebook_pending)").fetchall()}
    if "re_project_id" not in cols:
        conn.execute(
            """
            ALTER TABLE crm_facebook_pending
            ADD COLUMN re_project_id INTEGER REFERENCES crm_re_projects(id) ON DELETE SET NULL
            """
        )


def enqueue_facebook_leadgen(
    conn: sqlite3.Connection,
    *,
    leadgen_id: str,
    page_id: str = "",
    form_id: str = "",
    re_project_id: int | None = None,
    source: str = "webhook",
    ts: str,
    error: str = "",
) -> None:
    ensure_facebook_pending_schema(conn)
    lid = str(leadgen_id or "").strip()
    if not lid:
        return
    conn.execute(
        """
        INSERT INTO crm_facebook_pending (leadgen_id, page_id, form_id, re_project_id, source, attempts, last_error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
        ON CONFLICT(leadgen_id) DO UPDATE SET
            page_id = excluded.page_id,
            form_id = excluded.form_id,
            re_project_id = COALESCE(excluded.re_project_id, crm_facebook_pending.re_project_id),
            last_error = excluded.last_error,
            updated_at = excluded.updated_at
        """,
        (
            lid,
            str(page_id or ""),
            str(form_id or ""),
            int(re_project_id) if re_project_id else None,
            str(source or "webhook")[:40],
            error[:500],
            ts,
            ts,
        ),
    )


def dequeue_facebook_leadgen(conn: sqlite3.Connection, leadgen_id: str) -> None:
    ensure_facebook_pending_schema(conn)
    conn.execute("DELETE FROM crm_facebook_pending WHERE leadgen_id = ?", (str(leadgen_id or "").strip(),))


def list_pending_facebook_leadgens(conn: sqlite3.Connection, *, limit: int = 30) -> list[dict[str, str]]:
    ensure_facebook_pending_schema(conn)
    lim = max(1, min(int(limit), 100))
    rows = conn.execute(
        """
        SELECT leadgen_id, page_id, form_id, re_project_id, source, attempts, last_error, created_at, updated_at
        FROM crm_facebook_pending
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (lim,),
    ).fetchall()
    return [
        {
            "leadgen_id": str(r["leadgen_id"] or ""),
            "page_id": str(r["page_id"] or ""),
            "form_id": str(r["form_id"] or ""),
            "re_project_id": int(r["re_project_id"]) if r["re_project_id"] else None,
            "source": str(r["source"] or ""),
            "attempts": int(r["attempts"] or 0),
            "last_error": str(r["last_error"] or ""),
        }
        for r in rows
    ]


def bump_pending_attempt(conn: sqlite3.Connection, leadgen_id: str, *, ts: str, error: str = "") -> None:
    ensure_facebook_pending_schema(conn)
    conn.execute(
        """
        UPDATE crm_facebook_pending
        SET attempts = attempts + 1, last_error = ?, updated_at = ?
        WHERE leadgen_id = ?
        """,
        (error[:500], ts, str(leadgen_id or "").strip()),
    )


def process_pending_facebook_leads(
    conn: sqlite3.Connection,
    *,
    created_by: str,
    ts: str,
    max_items: int = 20,
) -> dict[str, Any]:
    """Xử lý hàng đợi leadgen (webhook/retry)."""
    from crm_facebook_config import fetch_facebook_config
    from crm_facebook_leads import fetch_facebook_lead_from_graph_with_retry, is_graph_rate_limited, process_facebook_lead_item, record_graph_rate_limit

    fb_cfg = fetch_facebook_config(conn)
    if not fb_cfg.get("enabled"):
        return {"processed": 0, "created_count": 0, "results": []}

    rate_limited, rate_msg = is_graph_rate_limited(conn)
    if rate_limited:
        return {"processed": 0, "created_count": 0, "results": [], "rate_limited": True, "message": rate_msg}

    results: list[dict[str, Any]] = []
    for row in list_pending_facebook_leadgens(conn, limit=max(1, min(int(max_items), 20))):
        lid = row["leadgen_id"]
        item = fetch_facebook_lead_from_graph_with_retry(lid, attempts=3, delay_sec=1.0)
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        meta["facebook_leadgen_id"] = lid
        if row.get("form_id"):
            meta["facebook_form_id"] = row["form_id"]
        if row.get("page_id"):
            meta["facebook_page_id"] = row["page_id"]
        item["meta"] = meta
        item["source"] = "facebook"

        phone = str(item.get("phone") or "").strip()
        email = str(item.get("email") or "").strip()
        if not phone and not email:
            err = str(meta.get("_graph_error") or "Graph API chưa trả SĐT/email")
            if "80005" in err or "too many leadgen" in err.lower():
                record_graph_rate_limit(conn, err, updated_by=created_by)
                results.append({"leadgen_id": lid, "status": "rate_limited", "message": err})
                break
            bump_pending_attempt(conn, lid, ts=ts, error=err)
            results.append({"leadgen_id": lid, "status": "pending_retry", "message": err})
            continue

        pending_project_id = None
        try:
            pending_project_id = int(row.get("re_project_id") or 0) or None
        except (TypeError, ValueError):
            pending_project_id = None
        result = process_facebook_lead_item(
            conn,
            item,
            created_by=created_by,
            ts=ts,
            fb_cfg=fb_cfg,
            skip_source_filter=True,
            re_project_id=pending_project_id,
        )
        result["leadgen_id"] = lid
        st = str(result.get("status") or "")
        if st in (
            "created_assigned",
            "created_unassigned",
            "duplicate_skipped",
            "duplicate_seen",
            "duplicate_linked",
            "filtered_out",
        ):
            dequeue_facebook_leadgen(conn, lid)
        elif st == "enriched":
            dequeue_facebook_leadgen(conn, lid)
        else:
            bump_pending_attempt(conn, lid, ts=ts, error=str(result.get("message") or ""))
        results.append(result)

    created = [
        r
        for r in results
        if r.get("status") in ("created_assigned", "created_unassigned", "enriched")
    ]
    enriched = [r for r in results if r.get("status") == "enriched"]
    if enriched or created:
        from crm_facebook_leads import save_facebook_webhook_receipt

        parts = []
        if created:
            parts.append(f"+{len(created)} lead")
        if enriched:
            parts.append(f"enrich {len(enriched)}")
        save_facebook_webhook_receipt(
            conn,
            ts=ts,
            event_count=0,
            created_count=len(created) + len(enriched),
            message=(" · ".join(parts) or "Pending Graph")[:500],
            updated_by=created_by,
        )
    return {
        "processed": len(results),
        "created_count": len(created),
        "results": results,
        "created_ids": [int(r["lead_id"]) for r in created if r.get("lead_id")],
    }
