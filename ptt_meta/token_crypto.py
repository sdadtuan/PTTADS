"""AES-GCM token vault (Phase 2 M1) — key from PTT_TOKEN_VAULT_KEY."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_NONCE_LEN = 12
_KEY_LEN = 32


class TokenVaultError(Exception):
    pass


def vault_configured() -> bool:
    return bool((os.environ.get("PTT_TOKEN_VAULT_KEY") or "").strip())


def _derive_key() -> bytes:
    raw = (os.environ.get("PTT_TOKEN_VAULT_KEY") or "").strip()
    if not raw:
        raise TokenVaultError("PTT_TOKEN_VAULT_KEY chưa cấu hình")
    try:
        padded = raw + "=" * (-len(raw) % 4)
        key = base64.urlsafe_b64decode(padded.encode("ascii"))
        if len(key) == _KEY_LEN:
            return key
    except Exception:
        pass
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_token(plaintext: str) -> bytes:
    text = str(plaintext or "").strip()
    if not text:
        raise TokenVaultError("Token rỗng")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise TokenVaultError(
            "Cần package cryptography — pip install cryptography"
        ) from exc
    key = _derive_key()
    nonce = os.urandom(_NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, text.encode("utf-8"), None)
    return nonce + ct


def decrypt_token(blob: bytes | memoryview | None) -> str | None:
    if not blob:
        return None
    data = bytes(blob)
    if len(data) <= _NONCE_LEN:
        return None
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        logger.warning("cryptography missing — cannot decrypt vault token")
        return None
    try:
        key = _derive_key()
        plain = AESGCM(key).decrypt(data[:_NONCE_LEN], data[_NONCE_LEN:], None)
        return plain.decode("utf-8")
    except Exception as exc:
        logger.warning("token vault decrypt failed: %s", exc)
        return None
