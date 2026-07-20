# tests/test_crm_aeo.py — legacy schema + deprecation wrappers (PG cutover).
from __future__ import annotations

import sqlite3
import unittest
import warnings
from unittest.mock import patch

import crm_aeo as m


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE crm_service_lifecycle (id INTEGER PRIMARY KEY, customer_id INTEGER);
        """
    )
    m.ensure_schema(conn)
    conn.execute("INSERT INTO crm_customers (id, name) VALUES (1, 'Test')")
    conn.commit()
    return conn


class TestSchema(unittest.TestCase):
    def test_tables_created(self) -> None:
        conn = _conn()
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("crm_aeo_queries", tables)
        self.assertIn("crm_aeo_scans", tables)
        self.assertIn("crm_aeo_content", tables)


class TestDeprecatedWrappers(unittest.TestCase):
    @patch("ptt_seo.aeo.add_aeo_query", return_value=42)
    def test_add_query_delegates(self, mock_add) -> None:
        conn = _conn()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            qid = m.add_query(conn, 1, "q?", "Brand")
        self.assertEqual(qid, 42)
        mock_add.assert_called_once()

    @patch("ptt_seo.aeo.list_aeo_queries", return_value=[{"id": 1}])
    def test_list_queries_delegates(self, mock_list) -> None:
        conn = _conn()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            rows = m.list_queries(conn, 1)
        self.assertEqual(len(rows), 1)
        mock_list.assert_called_once_with(1)

    @patch("ptt_seo.aeo.delete_aeo_query")
    def test_delete_query_delegates(self, mock_del) -> None:
        conn = _conn()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            m.delete_query(conn, 5)
        mock_del.assert_called_once_with(5)


if __name__ == "__main__":
    unittest.main()
