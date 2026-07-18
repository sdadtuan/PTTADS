"""Form ingest spillover list/replay tests (P0-06)."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ptt_jobs.form_ingest_failure import (
    list_form_ingest_spillover,
    record_form_ingest_spillover,
    replay_form_ingest_spillover,
    spillover_stats,
)


class TestFormIngestSpilloverApi(unittest.TestCase):
    def test_list_and_stats(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch("ptt_jobs.form_ingest_failure.sqlite_db_path", return_value=tmp.name):
                record_form_ingest_spillover(
                    fields={"phone": "0901", "full_name": "A"},
                    error="queue down",
                )
                st = spillover_stats()
                self.assertEqual(st["open"], 1)
                rows = list_form_ingest_spillover(limit=10)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["phone"], "0901")

    @patch("ptt_jobs.enqueue.enqueue_job")
    @patch("ptt_jobs.form_ingest_failure.jobs_enabled", return_value=True)
    @patch("ptt_jobs.form_ingest_failure.pg_available", return_value=True)
    def test_replay_enqueue(self, _pg, _jobs, mock_enqueue) -> None:
        mock_enqueue.return_value = {"id": "job-1", "status": "pending"}
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch("ptt_jobs.form_ingest_failure.sqlite_db_path", return_value=tmp.name):
                sid = record_form_ingest_spillover(
                    fields={"phone": "0902", "full_name": "B"},
                    error="fail",
                )
                out = replay_form_ingest_spillover(int(sid or 0))
                self.assertTrue(out.get("ok"))
                self.assertEqual(out.get("mode"), "queue")
                st = spillover_stats()
                self.assertEqual(st["open"], 0)

    def test_replay_not_found(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch("ptt_jobs.form_ingest_failure.sqlite_db_path", return_value=tmp.name):
                out = replay_form_ingest_spillover(999)
                self.assertFalse(out.get("ok"))
                self.assertEqual(out.get("error"), "not_found")


if __name__ == "__main__":
    unittest.main()
