"""Tests for Meta token vault M1."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from ptt_agency.channel_vault import compute_token_status, public_channel_account


class TestTokenCrypto(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self) -> None:
        key = "test-vault-key-for-unit-tests-only"
        with patch.dict(os.environ, {"PTT_TOKEN_VAULT_KEY": key}):
            try:
                from ptt_meta.token_crypto import decrypt_token, encrypt_token
            except ImportError:
                self.skipTest("cryptography not installed")
            blob = encrypt_token("EAA-test-token-123")
            self.assertEqual(decrypt_token(blob), "EAA-test-token-123")


class TestChannelVaultPublic(unittest.TestCase):
    def test_public_masks_encrypted(self) -> None:
        out = public_channel_account(
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "channel": "meta",
                "external_account_id": "act_1",
                "display_name": "Demo",
                "status": "active",
                "access_token_encrypted": b"secret-bytes",
                "token_expires_at": None,
                "token_status": "unknown",
            }
        )
        self.assertTrue(out["has_token"])
        self.assertNotIn("access_token_encrypted", out)

    def test_compute_expiring(self) -> None:
        soon = datetime.now(timezone.utc) + timedelta(days=3)
        self.assertEqual(
            compute_token_status(has_token=True, token_status=None, token_expires_at=soon),
            "expiring",
        )


class TestResolveMetaToken(unittest.TestCase):
    def test_decrypt_vault_first(self) -> None:
        key = "resolve-test-key"
        with patch.dict(os.environ, {"PTT_TOKEN_VAULT_KEY": key}):
            try:
                from ptt_meta.token_crypto import encrypt_token
                from ptt_meta.token_vault import resolve_meta_access_token
            except ImportError:
                self.skipTest("cryptography not installed")
            blob = encrypt_token("vault-token")
            tok = resolve_meta_access_token({"access_token_encrypted": blob})
            self.assertEqual(tok, "vault-token")


if __name__ == "__main__":
    unittest.main()
