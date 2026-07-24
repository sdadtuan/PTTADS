"""B15 — Link approved CRM creative to Graph ad creative (stub/Graph)."""
from __future__ import annotations

import logging
import os
from typing import Any

from ptt_meta.ads_ops import ads_ops_enabled

logger = logging.getLogger(__name__)


def validate_upload_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(payload.get("client_id") or "").strip():
        errors.append("client_id_required")
    if not str(payload.get("creative_submission_id") or "").strip():
        errors.append("creative_submission_id_required")
    return errors


def upload_creative_link(
    *,
    client_id: str,
    creative_submission_id: str,
    external_account_id: str | None = None,
    stub: bool = False,
) -> dict[str, Any]:
    errors = validate_upload_payload(
        {
            "client_id": client_id,
            "creative_submission_id": creative_submission_id,
        }
    )
    if errors:
        return {"ok": False, "errors": errors}

    if stub or not ads_ops_enabled():
        return {
            "ok": True,
            "stub": True,
            "external_creative_id": f"stub_creative_{creative_submission_id[:8]}",
            "client_id": client_id,
            "creative_submission_id": creative_submission_id,
            "external_account_id": external_account_id,
        }

    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, status, title, asset_url
                    FROM creative_submissions
                    WHERE id = %s::uuid AND client_id = %s::uuid
                    LIMIT 1
                    """,
                    (creative_submission_id, client_id),
                )
                row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "creative_not_found"}
        if str(row[1]) != "approved":
            return {"ok": False, "error": "creative_not_approved", "status": str(row[1])}
    except Exception as exc:
        logger.warning("upload_creative_link pg check failed: %s", exc)
        return {"ok": False, "error": "creative_lookup_failed"}

    ext_id = f"graph_creative_{creative_submission_id.replace('-', '')[:12]}"
    return {
        "ok": True,
        "external_creative_id": ext_id,
        "client_id": client_id,
        "creative_submission_id": creative_submission_id,
        "creative_title": str(row[2]) if row else None,
        "note": "Graph upload stub — wire Meta Marketing API in pilot",
    }
