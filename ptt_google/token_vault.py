"""Resolve Google Ads credentials from channel account vault (Phase 3 G1)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def resolve_google_refresh_token(account: dict[str, Any]) -> str | None:
    """
    Token resolution order:
    1. access_token_encrypted (AES-GCM vault — stores refresh token for Google)
    2. credential_ref env var name
    3. PTT_GOOGLE_ADS_REFRESH_TOKEN (dev pilot)
    4. meta.refresh_token in account JSONB (staging only)
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

    global_tok = (os.environ.get("PTT_GOOGLE_ADS_REFRESH_TOKEN") or "").strip()
    if global_tok:
        return global_tok

    meta = account.get("meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    tok = str(meta.get("refresh_token") or "").strip()
    return tok or None


def normalize_customer_id(raw: str) -> str:
    """Google Ads customer ID without dashes."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    return digits
