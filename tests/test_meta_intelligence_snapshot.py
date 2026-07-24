"""Tests for Meta intelligence snapshot (B11)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_meta.intelligence_snapshot import meta_intel_snapshot_enabled


class TestIntelligenceSnapshotConfig(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_META_INTEL_SNAPSHOT_ENABLED": "0"}, clear=False):
            self.assertFalse(meta_intel_snapshot_enabled())

    @patch("ptt_meta.intelligence_snapshot.pg_meta_intelligence_snapshots_ready", return_value=False)
    def test_create_skipped_when_not_ready(self, _ready) -> None:
        from ptt_meta.intelligence_snapshot import create_intelligence_snapshot

        with patch.dict(os.environ, {"PTT_META_INTEL_SNAPSHOT_ENABLED": "1"}, clear=False):
            out = create_intelligence_snapshot()
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
