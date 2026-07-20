"""Blueprint tests for CMS webhook pilot receiver."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import json
import unittest
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.enterprise_schema import ensure_enterprise_schema


class TestCmsWebhookReceiver(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import app as flask_app
        except ImportError:
            self.skipTest("app module not available")
        self.app = flask_app.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    @patch.dict("os.environ", {"PTT_SEO_CMS_WEBHOOK_SECRET": "test-secret"}, clear=False)
    def test_receive_unauthorized(self) -> None:
        resp = self.client.post(
            "/api/v1/seo/internal/cms-webhook/receive",
            json={"title": "T", "slug": "t"},
        )
        self.assertEqual(resp.status_code, 401)

    @patch.dict("os.environ", {"PTT_SEO_CMS_WEBHOOK_SECRET": "test-secret"}, clear=False)
    def test_receive_ok(self) -> None:
        resp = self.client.post(
            "/api/v1/seo/internal/cms-webhook/receive",
            json={"title": "Hello", "slug": "hello-world"},
            headers={"Authorization": "Bearer test-secret"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        assert data is not None
        self.assertTrue(data.get("ok"))
        self.assertIn("hello-world", data.get("permalink", ""))


if __name__ == "__main__":
    unittest.main()
