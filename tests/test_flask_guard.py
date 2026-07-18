"""Unit tests for Flask monolith guard (Phase 4 F3)."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from flask import Flask

from ptt_crm.flask_guard import (
    deny_flask_write,
    flask_monolith_readonly,
    flask_monolith_retired,
)

app = Flask(__name__)


class TestFlaskGuard(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_FLASK_MONOLITH_MODE": "active"}, clear=False)
    def test_active_allows_writes(self) -> None:
        self.assertFalse(flask_monolith_readonly())
        self.assertFalse(flask_monolith_retired())
        with app.app_context():
            self.assertIsNone(deny_flask_write())

    @patch.dict(os.environ, {"PTT_FLASK_MONOLITH_MODE": "readonly"}, clear=False)
    def test_readonly_blocks_writes(self) -> None:
        self.assertTrue(flask_monolith_readonly())
        with app.app_context():
            resp, status = deny_flask_write("test_write")
        self.assertEqual(status, 503)
        data = json.loads(resp.get_data(as_text=True))
        self.assertEqual(data["error"], "flask_monolith_readonly")

    @patch.dict(os.environ, {"PTT_FLASK_MONOLITH_MODE": "retired"}, clear=False)
    def test_retired_blocks_writes(self) -> None:
        self.assertTrue(flask_monolith_retired())
        with app.app_context():
            resp, status = deny_flask_write()
        self.assertEqual(status, 503)
        data = json.loads(resp.get_data(as_text=True))
        self.assertEqual(data["error"], "flask_monolith_retired")


if __name__ == "__main__":
    unittest.main()
