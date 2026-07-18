"""Dual-run compare PG write vs SQLite shadow vs Nest (Phase 2 W7)."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from ptt_crm.config import nest_internal_key, nest_leads_base_url
from ptt_crm.dual_run import diff_lead_v1
from ptt_crm.lead_shadow_sync import get_pg_lead_v1, reconcile_leads_pg_primary
from ptt_crm.leads_read import get_lead_v1
from ptt_jobs.config import sqlite_db_path

logger = logging.getLogger(__name__)

WRITE_FIELDS = ("owner_id", "status")


def _sqlite_write_snapshot(lead_id: int) -> dict[str, Any] | None:
    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, owner_id, status FROM crm_leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        if not row:
            return None
        return {"id": int(row["id"]), "owner_id": row["owner_id"], "status": row["status"] or ""}
    finally:
        conn.close()


def _pg_write_snapshot(lead_id: int) -> dict[str, Any] | None:
    lead = get_pg_lead_v1(lead_id)
    if not lead:
        return None
    return {"id": lead["id"], "owner_id": lead.get("owner_id"), "status": lead.get("status") or ""}


def _nest_get_lead(lead_id: int) -> dict[str, Any] | None:
    import urllib.error
    import urllib.request

    url = f"{nest_leads_base_url()}/api/v1/leads/{lead_id}"
    req = urllib.request.Request(url, method="GET")
    key = nest_internal_key()
    if key:
        req.add_header("X-PTT-Internal-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json

            body = json.loads(resp.read().decode())
            return body.get("lead") or body
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        logger.debug("nest get lead %s: %s", lead_id, exc)
        return None


def run_write_dual_run_check(*, sample_size: int = 50, include_nest: bool = True) -> dict[str, Any]:
    """
    Compare write-relevant fields across PG (authoritative), SQLite shadow, and Nest read.
    """
    from ptt_crm.phase2_prereqs import ensure_phase2_write_gates

    prereq = ensure_phase2_write_gates(repair_shadow=True)
    base = reconcile_leads_pg_primary(sample_size=sample_size)
    write_mismatches: list[dict[str, Any]] = []

    from ptt_jobs.db import pg_available, pg_connection

    ids: list[int] = []
    if pg_available():
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT sqlite_lead_id FROM crm_leads
                    WHERE is_duplicate IS NOT TRUE
                      AND owner_id IS NOT NULL
                    ORDER BY sqlite_lead_id DESC
                    LIMIT %s
                    """,
                    (max(1, min(sample_size, 500)),),
                )
                ids = [int(r[0]) for r in cur.fetchall()]

    if not ids:
        conn = sqlite3.connect(sqlite_db_path())
        try:
            ids = [
                int(r[0])
                for r in conn.execute(
                    """
                    SELECT id FROM crm_leads
                    WHERE COALESCE(is_duplicate, 0) = 0 AND owner_id IS NOT NULL
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (max(1, min(sample_size, 500)),),
                ).fetchall()
            ]
        finally:
            conn.close()

    nest_mismatches: list[dict[str, Any]] = []
    for lead_id in ids:
        pg = _pg_write_snapshot(lead_id)
        sql = _sqlite_write_snapshot(lead_id)
        if pg and sql:
            for field in WRITE_FIELDS:
                if pg.get(field) != sql.get(field):
                    write_mismatches.append(
                        {
                            "id": lead_id,
                            "error": "pg_sqlite_write_mismatch",
                            "field": field,
                            "pg": pg.get(field),
                            "sqlite": sql.get(field),
                        }
                    )
                    break

        if include_nest and pg:
            nest = _nest_get_lead(lead_id)
            if nest:
                diffs = [d for d in diff_lead_v1(pg, nest) if d.field in WRITE_FIELDS]
                if diffs:
                    nest_mismatches.append(
                        {"id": lead_id, "diffs": [d.__dict__ for d in diffs]}
                    )

    ok = len(write_mismatches) == 0 and len(nest_mismatches) == 0 and prereq.get("ok", True)
    return {
        "ok": ok,
        "mode": "write_dual_run",
        "sample_size": len(ids),
        "pg_sqlite_mismatch_count": len(write_mismatches),
        "pg_nest_mismatch_count": len(nest_mismatches),
        "mismatches": write_mismatches[:20],
        "nest_mismatches": nest_mismatches[:20],
        "reconcile": base,
        "prerequisites": prereq,
        "nest_url": nest_leads_base_url(),
    }
