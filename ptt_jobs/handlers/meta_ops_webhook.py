"""Job handler — process Meta ops webhook events (B13)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_meta.ops_webhooks import process_ops_webhook_payload
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def _resolve_client_id_factory(payload: dict[str, Any]):
    def resolve(external_account_id: str | None) -> str | None:
        explicit = payload.get("client_id")
        if explicit:
            return str(explicit).strip() or None
        if not external_account_id:
            return None
        try:
            from ptt_jobs.db import pg_connection

            account = str(external_account_id).strip()
            digits = "".join(ch for ch in account if ch.isdigit())
            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT client_id::text
                        FROM client_channel_accounts
                        WHERE channel = 'meta'
                          AND status = 'active'
                          AND (
                            external_account_id = %s
                            OR external_account_id = %s
                            OR regexp_replace(external_account_id, '\\D', '', 'g') = %s
                            OR meta->>'ad_account_id' = %s
                          )
                        ORDER BY updated_at DESC
                        LIMIT 1
                        """,
                        (account, f"act_{digits}" if digits else account, digits, account),
                    )
                    row = cur.fetchone()
                    return str(row[0]) if row else None
        except Exception as exc:
            logger.warning("meta_ops_webhook client resolve failed: %s", exc)
            return None

    return resolve


def process_meta_ops_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    webhook = payload.get("webhook")
    if isinstance(webhook, dict):
        body = webhook
    else:
        body = payload
    return process_ops_webhook_payload(
        body if isinstance(body, dict) else {},
        resolve_client_id=_resolve_client_id_factory(payload),
    )


def run_meta_ops_webhook_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_meta_ops_webhook_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("meta_ops_webhook done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or "meta ops webhook failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
