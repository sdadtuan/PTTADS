"""Tests for ptt_observability."""
from __future__ import annotations

import json
import logging
import unittest
from unittest.mock import patch

from ptt_observability.logging_config import (
    JsonLogFormatter,
    bind_correlation_id,
    configure_json_logging,
    json_logs_enabled,
)


class TestObservability(unittest.TestCase):
    def test_json_formatter_includes_correlation_id(self) -> None:
        bind_correlation_id("corr-abc")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        line = JsonLogFormatter().format(record)
        data = json.loads(line)
        self.assertEqual(data["message"], "hello")
        self.assertEqual(data["correlation_id"], "corr-abc")

    def test_json_formatter_http_fields(self) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="http_request",
            args=(),
            exc_info=None,
        )
        record.http_method = "GET"
        record.path = "/api/v1/jobs"
        record.status = 200
        record.duration_ms = 12.5
        data = json.loads(JsonLogFormatter().format(record))
        self.assertEqual(data["http_method"], "GET")
        self.assertEqual(data["status"], 200)

    def test_json_logs_enabled_prod_env(self) -> None:
        with patch.dict("os.environ", {"SENTRY_ENVIRONMENT": "production"}, clear=True):
            self.assertTrue(json_logs_enabled())
        with patch.dict("os.environ", {"PTT_JSON_LOGS": "0", "SENTRY_ENVIRONMENT": "production"}, clear=True):
            self.assertFalse(json_logs_enabled())

    def test_init_sentry_noop_without_dsn(self) -> None:
        from ptt_observability.sentry_init import init_sentry

        with patch.dict("os.environ", {}, clear=True):
            init_sentry(component="test")

    def test_capture_exception_noop_without_dsn(self) -> None:
        from ptt_observability.sentry_init import capture_exception

        with patch.dict("os.environ", {}, clear=True):
            capture_exception(RuntimeError("x"))

    def test_configure_json_logging_idempotent(self) -> None:
        with patch.dict("os.environ", {"PTT_JSON_LOGS": "1"}, clear=True):
            configure_json_logging(component="unittest")
            configure_json_logging(component="unittest")
            root = logging.getLogger()
            self.assertTrue(any(isinstance(h.formatter, JsonLogFormatter) for h in root.handlers))

    def test_flask_observability_sets_correlation_header(self) -> None:
        from flask import Flask

        from ptt_observability import bind_correlation_id, init_observability

        app = Flask(__name__)
        init_observability(component="flask_test", app=app)

        @app.get("/ping")
        def ping() -> str:
            bind_correlation_id("test-corr-id")
            return "ok"

        client = app.test_client()
        resp = client.get("/ping", headers={"X-Correlation-Id": "test-corr-id"})
        self.assertEqual(resp.headers.get("X-Correlation-Id"), "test-corr-id")


if __name__ == "__main__":
    unittest.main()
