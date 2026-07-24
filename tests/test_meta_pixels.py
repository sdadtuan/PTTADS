"""Tests for Meta multi-pixel registry (B11)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_meta.meta_pixels import meta_pixels_enabled


class TestMetaPixelsConfig(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_META_PIXELS_ENABLED": "0"}, clear=False):
            self.assertFalse(meta_pixels_enabled())

    @patch("ptt_meta.meta_pixels.pg_meta_pixels_ready", return_value=False)
    def test_list_pixels_not_ready(self, _ready) -> None:
        from ptt_meta.meta_pixels import list_pixels

        with patch.dict(os.environ, {"PTT_META_PIXELS_ENABLED": "1"}, clear=False):
            out = list_pixels()
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
