"""Resolve Zalo Ads credentials from channel account vault (Wave Z1)."""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _meta_dict(account: dict[str, Any]) -> dict[str, Any]:
    meta = account.get("meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def resolve_zalo_refresh_token(account: dict[str, Any]) -> str | None:
    """
    Refresh token resolution:
    1. meta.refresh_token_encrypted (AES-GCM vault, base64)
    2. meta.refresh_token (staging only)
    """
    meta = _meta_dict(account)
    enc_b64 = str(meta.get("refresh_token_encrypted") or "").strip()
    if enc_b64:
        try:
            from ptt_meta.token_crypto import decrypt_token

            tok = decrypt_token(base64.b64decode(enc_b64))
            if tok:
                return tok
        except Exception as exc:
            logger.debug("zalo refresh decrypt failed: %s", exc)

    tok = str(meta.get("refresh_token") or "").strip()
    return tok or None


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

    meta = _meta_dict(account)
    tok = str(meta.get("access_token") or meta.get("refresh_token") or "").strip()
    return tok or None


def normalize_account_id(raw: str) -> str:
    return str(raw or "").strip()
