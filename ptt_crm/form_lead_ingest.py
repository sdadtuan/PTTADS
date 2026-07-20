"""Form/API lead ingest — no Flask dependency."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from crm_lead_store import create_lead
from crm_project_webhooks import resolve_project_for_lead_ingest
from ptt_crm.crm_sqlite import db_path

logger = logging.getLogger(__name__)


def ingest_lead_from_form(
    conn: sqlite3.Connection,
    *,
    full_name: str,
    phone: str,
    email: str,
    need: str,
    source: str,
    region: str = "",
    product_interest: str = "",
    utm_campaign: str = "",
    re_project_id: int | None = None,
    re_project_code: str | None = None,
    ingest_site: str = "",
    ts: str,
    _from_worker: bool = False,
) -> int | None:
    """Tạo lead CRM từ form/API ngoài — bỏ qua nếu trùng policy reject."""
    try:
        pid = resolve_project_for_lead_ingest(
            conn,
            re_project_id=re_project_id,
            re_project_code=re_project_code,
            utm_campaign=utm_campaign,
            ingest_site=ingest_site,
        )
        ingest_meta: dict[str, Any] = {"ingest_channel": "website_form"}
        if ingest_site:
            ingest_meta["ingest_site"] = str(ingest_site).strip()[:120]
        row, _dups, _dup_matches = create_lead(
            conn,
            full_name=full_name,
            phone=phone,
            email=email,
            source=source,
            region=region,
            product_interest=product_interest,
            need=need,
            utm_campaign=utm_campaign,
            re_project_id=pid,
            meta=ingest_meta,
            auto_assign=True,
            duplicate_policy=None,
            created_by="system:ingest",
            ts=ts,
        )
        lead_id = int(row["id"])

        try:
            from crm_ai_qualify import trigger_qualify_brief_async
            from crm_re_projects import fetch_project

            project_name = ""
            if pid:
                proj = fetch_project(conn, pid)
                project_name = str(proj.get("name") or "") if proj else ""

            trigger_qualify_brief_async(
                lead_id,
                full_name=full_name,
                product_interest=product_interest,
                source=source,
                need=need,
                project_name=project_name,
                db_path=str(db_path()),
            )
        except Exception as ai_exc:
            logger.debug("AI qualify trigger bỏ qua: %s", ai_exc)

        return lead_id
    except ValueError as exc:
        logger.warning("CRM ingest lead from form failed: %s", exc)
        if not _from_worker:
            _enqueue_form_ingest_failure(
                full_name=full_name,
                phone=phone,
                email=email,
                need=need,
                source=source,
                error=str(exc),
            )
        return None
    except Exception as exc:
        logger.exception("CRM ingest lead from form error: %s", exc)
        if not _from_worker:
            _enqueue_form_ingest_failure(
                full_name=full_name,
                phone=phone,
                email=email,
                need=need,
                source=source,
                error=str(exc),
            )
        return None


def _enqueue_form_ingest_failure(**fields: Any) -> None:
    from ptt_jobs.form_ingest_failure import enqueue_form_ingest_failure

    enqueue_form_ingest_failure(**fields)
