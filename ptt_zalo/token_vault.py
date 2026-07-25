"""Resolve Zalo Ads credentials from channel account vault (Wave Z1)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def resolve_zalo_access_token(account: dict[str, Any]) -> str | None:
    """
    Token resolution order:
    1. access_token_encrypted (AES-GCM vault)
    2. credential_ref env var name
    3. PTT_ZALO_ACCESS_TOKEN (dev pilot)
    4. meta.access_token in account JSONB (staging only)
    """
    enc = account.get("access_token_encrypted")
    if enc:
        from ptt_meta.token_crypto import decrypt_token

        tok = decrypt_token(enc)
        if tok:
            return tok

    ref = str(account.get("credential_ref") or "").strip()
    if ref:
        tok = os.environ.get(ref)
        if tok:
            return tok.strip()

    global_tok = (os.environ.get("PTT_ZALO_ACCESS_TOKEN") or "").strip()
    if global_tok:
        return global_tok

    meta = account.get("meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    tok = str(meta.get("access_token") or meta.get("refresh_token") or "").strip()
    return tok or None


def normalize_account_id(raw: str) -> str:
    return str(raw or "").strip()
