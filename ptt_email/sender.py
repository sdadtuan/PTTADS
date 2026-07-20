"""Send batch worker — dequeue send_queue and call ESP adapter (EM-6)."""
from __future__ import annotations

import logging
import re
from typing import Any

from ptt_channel.adapters.email import EmailAdapter
from ptt_channel.context import AdapterContext
from ptt_email.config import email_batch_size, email_send_enabled
from ptt_email.esp_credentials import resolve_esp_config
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"
TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def send_batch(
    *,
    campaign_id: str | None = None,
    client_id: str | None = None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    if not email_send_enabled():
        return {"ok": False, "error": "send_disabled", "skipped": True}

    limit = batch_size or email_batch_size()
    claimed: list[dict[str, Any]] = []

    with pg_connection() as conn:
        with conn.cursor() as cur:
            where_parts = ["sq.status = 'pending'", "sq.scheduled_at <= NOW()"]
            params: list[Any] = []
            if campaign_id:
                params.append(campaign_id)
                where_parts.append("sq.campaign_id = %s::uuid")
            if client_id:
                params.append(client_id)
                where_parts.append("sq.client_id = %s::uuid")
            params.append(limit)
            cur.execute(
                f"""
                SELECT sq.id::text, sq.client_id::text, sq.campaign_id::text, sq.contact_id::text,
                       sq.subject_rendered, sq.tracking_id::text,
                       ct.email, ct.first_name, ct.last_name,
                       tmpl.html_body, tmpl.text_body,
                       w.default_from_email, w.default_from_name, w.default_reply_to, w.esp_provider
                FROM {SCHEMA}.send_queue sq
                JOIN {SCHEMA}.contacts ct ON ct.id = sq.contact_id
                JOIN {SCHEMA}.campaigns cam ON cam.id = sq.campaign_id
                JOIN {SCHEMA}.templates tmpl ON tmpl.id = cam.template_id
                JOIN {SCHEMA}.workspaces w ON w.client_id = sq.client_id
                WHERE {' AND '.join(where_parts)}
                ORDER BY sq.scheduled_at ASC
                FOR UPDATE OF sq SKIP LOCKED
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()
            for row in rows:
                send_id = str(row[0])
                cur.execute(
                    f"UPDATE {SCHEMA}.send_queue SET status = 'processing' WHERE id = %s::uuid",
                    (send_id,),
                )
                claimed.append(
                    {
                        "send_id": send_id,
                        "client_id": str(row[1]),
                        "campaign_id": str(row[2]),
                        "contact_id": str(row[3]),
                        "subject": str(row[4] or ""),
                        "tracking_id": str(row[5]),
                        "to_email": str(row[6]),
                        "first_name": str(row[7] or ""),
                        "last_name": str(row[8] or ""),
                        "html_body": str(row[9] or ""),
                        "text_body": str(row[10] or "") if row[10] else "",
                        "from_email": str(row[11] or ""),
                        "from_name": str(row[12] or ""),
                        "reply_to": str(row[13] or row[11] or ""),
                        "esp_provider": str(row[14] or "sendgrid"),
                    }
                )
        conn.commit()

    if not claimed:
        if campaign_id:
            _maybe_complete_campaign(campaign_id)
        return {"ok": True, "sent": 0, "failed": 0, "skipped": 0}

    sent = 0
    failed = 0
    adapter = EmailAdapter()
    outcomes: list[dict[str, Any]] = []

    by_client: dict[str, list[dict[str, Any]]] = {}
    for item in claimed:
        by_client.setdefault(item["client_id"], []).append(item)

    for cid, items in by_client.items():
        esp = resolve_esp_config(cid, esp_provider=items[0]["esp_provider"])
        ctx = AdapterContext(
            client_id=cid,
            channel_account_id="",
            credential_ref="",
            request_id=items[0]["campaign_id"],
        )
        messages = []
        for item in items:
            tokens = {
                "first_name": item["first_name"],
                "last_name": item["last_name"],
                "email": item["to_email"],
                "unsubscribe_url": f"https://ops.pttads.vn/email/public/unsubscribe/{item['tracking_id']}",
            }
            messages.append(
                {
                    "send_id": item["send_id"],
                    "to_email": item["to_email"],
                    "subject": _render_tokens(item["subject"], tokens),
                    "html_body": _render_tokens(item["html_body"], tokens),
                    "text_body": _render_tokens(item["text_body"], tokens) if item["text_body"] else "",
                    "from_email": esp["from_email"] or item["from_email"],
                    "from_name": esp["from_name"] or item["from_name"],
                    "reply_to": esp["reply_to"] or item["reply_to"],
                    "tracking_id": item["tracking_id"],
                    "unsubscribe_url": tokens["unsubscribe_url"],
                    "custom_args": {
                        "send_id": item["send_id"],
                        "campaign_id": item["campaign_id"],
                        "client_id": cid,
                    },
                }
            )
        batch_out = adapter.send_batch(ctx, messages, api_key=esp.get("api_key"), dry_run=esp.get("dry_run", False))
        outcomes.extend(batch_out.get("results") or [])

    with pg_connection() as conn:
        with conn.cursor() as cur:
            for out in outcomes:
                send_id = out.get("send_id")
                if out.get("ok"):
                    cur.execute(
                        f"""
                        UPDATE {SCHEMA}.send_queue
                        SET status = 'sent', sent_at = NOW(), esp_message_id = %s, attempts = attempts + 1
                        WHERE id = %s::uuid
                        """,
                        (out.get("esp_message_id"), send_id),
                    )
                    cur.execute(
                        f"""
                        INSERT INTO {SCHEMA}.engagement_events
                          (client_id, send_id, contact_id, event_type, occurred_at)
                        SELECT sq.client_id, sq.id, sq.contact_id, 'delivered', NOW()
                        FROM {SCHEMA}.send_queue sq WHERE sq.id = %s::uuid
                        """,
                        (send_id,),
                    )
                    sent += 1
                else:
                    cur.execute(
                        f"""
                        UPDATE {SCHEMA}.send_queue
                        SET status = 'failed', last_error = %s, attempts = attempts + 1
                        WHERE id = %s::uuid
                        """,
                        (str(out.get("error") or "send_failed"), send_id),
                    )
                    failed += 1
        conn.commit()

    if campaign_id:
        _maybe_complete_campaign(campaign_id)
        pending = _pending_count(campaign_id)
        if pending > 0:
            from ptt_jobs.enqueue import enqueue_job

            enqueue_job(
                "email_send_batch",
                {"campaign_id": campaign_id, "client_id": client_id or claimed[0]["client_id"]},
                f"email_send_batch:{campaign_id}:cont",
                client_id=client_id or claimed[0]["client_id"],
            )

    return {"ok": True, "sent": sent, "failed": failed, "claimed": len(claimed)}


def _render_tokens(text: str, tokens: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return tokens.get(key, match.group(0))

    return TOKEN_RE.sub(repl, text or "")


def _pending_count(campaign_id: str) -> int:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {SCHEMA}.send_queue
                WHERE campaign_id = %s::uuid AND status IN ('pending', 'processing')
                """,
                (campaign_id,),
            )
            row = cur.fetchone()
            return int(row[0] if row else 0)


def _maybe_complete_campaign(campaign_id: str) -> None:
    pending = _pending_count(campaign_id)
    if pending > 0:
        return
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {SCHEMA}.send_queue
                WHERE campaign_id = %s::uuid AND status = 'sent'
                """,
                (campaign_id,),
            )
            sent_count = int(cur.fetchone()[0])
            if sent_count <= 0:
                return
            cur.execute(
                f"""
                UPDATE {SCHEMA}.campaigns
                SET status = 'sent', sent_at = NOW(), updated_at = NOW()
                WHERE id = %s::uuid AND status = 'sending'
                """,
                (campaign_id,),
            )
        conn.commit()
