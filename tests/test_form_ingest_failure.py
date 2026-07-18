"""Tests for form ingest failure handling (P0-08)."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ptt_jobs.form_ingest_failure import (
    build_form_idempotency_key,
    enqueue_form_ingest_failure,
    ensure_spillover_table,
    record_form_ingest_spillover,
)


class TestFormIngestFailure(unittest.TestCase):
    def test_idempotency_key_stable(self) -> None:
        fields = {"phone": "0901111222", "email": "a@x.com", "full_name": "Test"}
        k1 = build_form_idempotency_key(fields)
        k2 = build_form_idempotency_key(fields)
        self.assertEqual(k1, k2)
        self.assertTrue(k1.startswith("form:"))

    @patch("ptt_jobs.form_ingest_failure.notify_form_ingest_dead")
    @patch("ptt_jobs.form_ingest_failure.jobs_sync_fallback", return_value=False)
    @patch("ptt_jobs.form_ingest_failure.jobs_enabled", return_value=False)
    @patch("ptt_jobs.form_ingest_failure.pg_available", return_value=False)
    def test_spillover_when_queue_unavailable(self, _pg, _jobs, _sync, _notify) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = sqlite3.connect(tmp.name)
            ensure_spillover_table(conn)
            conn.close()
            with patch("ptt_jobs.form_ingest_failure.sqlite_db_path", return_value=tmp.name):
                out = enqueue_form_ingest_failure(
                    full_name="Fail User",
                    phone="0909999888",
                    email="",
                    need="test",
                    source="website",
                    error="db locked",
                )
                self.assertEqual(out["mode"], "spillover")
                self.assertFalse(out["ok"])
                conn = sqlite3.connect(tmp.name)
                row = conn.execute(
                    "SELECT payload, error FROM form_ingest_spillover ORDER BY id DESC LIMIT 1"
                ).fetchone()
                conn.close()
                self.assertIsNotNone(row)
                payload = json.loads(row[0])
                self.assertEqual(payload["phone"], "0909999888")
                self.assertEqual(row[1], "db locked")
                _notify.assert_called_once()

    @patch("ptt_jobs.enqueue.enqueue_job")
    @patch("ptt_jobs.form_ingest_failure.jobs_enabled", return_value=True)
    @patch("ptt_jobs.form_ingest_failure.pg_available", return_value=True)
    def test_queue_when_pg_available(self, _pg, _jobs, mock_enqueue) -> None:
        mock_enqueue.return_value = {"id": "job-1", "status": "pending"}
        out = enqueue_form_ingest_failure(
            full_name="Queued",
            phone="0908888777",
            email="",
            error="temporary",
        )
        self.assertEqual(out["mode"], "queue")
        mock_enqueue.assert_called_once()

    def test_record_spillover_row(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch("ptt_jobs.form_ingest_failure.sqlite_db_path", return_value=tmp.name):
                rid = record_form_ingest_spillover(
                    fields={"full_name": "X", "phone": "090", "email": ""},
                    error="oops",
                )
                self.assertIsNotNone(rid)


if __name__ == "__main__":
    unittest.main()
