"""Resolve ESP API credentials from workspace + client_channel_accounts."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def resolve_esp_config(client_id: str, *, esp_provider: str | None = None) -> dict[str, Any]:
    """
    Returns {provider, api_key, from_email, from_name, reply_to, dry_run}.
    """
    from ptt_jobs.db import pg_connection

    provider = (esp_provider or "sendgrid").strip().lower()
    from_email = ""
    from_name = ""
    reply_to = ""
    account: dict[str, Any] | None = None

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT w.default_from_email, w.default_from_name, w.default_reply_to,
                       w.esp_provider, w.esp_account_ref::text
                FROM {SCHEMA}.workspaces w
                WHERE w.client_id = %s::uuid
                LIMIT 1
                """,
                (client_id,),
            )
            row = cur.fetchone()
            if row:
                from_email = str(row[0] or "")
                from_name = str(row[1] or "")
                reply_to = str(row[2] or "")
                provider = str(row[3] or provider).strip().lower() or provider
                esp_ref = row[4]
                if esp_ref:
                    cur.execute(
                        """
                        SELECT id::text, channel, credential_ref, meta, access_token_encrypted
                        FROM client_channel_accounts
                        WHERE id = %s::uuid AND channel = 'email'
                        LIMIT 1
                        """,
                        (esp_ref,),
                    )
                    acct_row = cur.fetchone()
                    if acct_row:
                        account = {
                            "id": acct_row[0],
                            "channel": acct_row[1],
                            "credential_ref": acct_row[2],
                            "meta": acct_row[3] or {},
                            "access_token_encrypted": acct_row[4],
                        }

    api_key = _resolve_api_key(account, provider)
    from ptt_email.config import email_esp_dry_run

    dry_run = email_esp_dry_run() or not api_key
    if dry_run and not api_key:
        logger.info("ESP dry-run for client=%s (no API key)", client_id)

    return {
        "provider": provider,
        "api_key": api_key,
        "from_email": from_email,
        "from_name": from_name,
        "reply_to": reply_to or from_email,
        "dry_run": dry_run,
    }


def _resolve_api_key(account: dict[str, Any] | None, provider: str) -> str | None:
    if account:
        enc = account.get("access_token_encrypted")
        if enc:
            try:
                from ptt_meta.token_crypto import decrypt_token

                tok = decrypt_token(enc)
                if tok:
                    return tok.strip()
            except Exception as exc:
                logger.debug("vault decrypt failed: %s", exc)

        ref = str(account.get("credential_ref") or "").strip()
        if ref:
            tok = os.environ.get(ref)
            if tok:
                return tok.strip()

        meta = account.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        if isinstance(meta, dict):
            for key in ("api_key", "sendgrid_api_key", "mailgun_api_key"):
                val = str(meta.get(key) or "").strip()
                if val:
                    return val

    for env_name in (
        "SENDGRID_API_KEY",
        "PTT_SENDGRID_API_KEY",
        "MAILGUN_API_KEY",
        "PTT_MAILGUN_API_KEY",
        f"PTT_EMAIL_{provider.upper()}_API_KEY",
    ):
        tok = (os.environ.get(env_name) or "").strip()
        if tok:
            return tok
    return None
