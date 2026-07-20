"""Unit tests for Flask monolith guard stub (Flask HTTP removed)."""
from __future__ import annotations

import unittest

from ptt_crm.flask_guard import (
    deny_flask_lead_write,
    deny_flask_write,
    flask_monolith_readonly,
    flask_monolith_retired,
)


class TestFlaskGuardStub(unittest.TestCase):
    def test_stub_guard_returns_none(self) -> None:
        self.assertIsNone(deny_flask_write())
        self.assertIsNone(deny_flask_write("test_write"))
        self.assertIsNone(deny_flask_lead_write())

    def test_flask_monolith_retired(self) -> None:
        self.assertTrue(flask_monolith_retired())
        self.assertFalse(flask_monolith_readonly())


if __name__ == "__main__":
    unittest.main()
