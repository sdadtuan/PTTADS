"""Tests for SEO/AEO Ops Phase 1 foundation."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from ptt_seo import schema as seo_schema
from ptt_seo.client_settings import get_settings, upsert_settings
from ptt_seo.constants import is_seo_aeo_service_slug
from ptt_seo.delivery import build_delivery_panel
from ptt_seo.hub import seo_hub_summary
from ptt_seo.initiatives import create_initiative, list_initiatives
from ptt_seo.projects import ensure_project_for_lifecycle


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """

        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            company TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'delivery',
            status TEXT NOT NULL DEFAULT 'active'
        );
        """
    )
    seo_schema.ensure_schema(conn)
    import crm_aeo

    crm_aeo.ensure_schema(conn)
    return conn


class TestSeoConstants(unittest.TestCase):
    def test_is_seo_aeo_slug(self) -> None:
        self.assertTrue(is_seo_aeo_service_slug("dich-vu-aeo"))
        self.assertTrue(is_seo_aeo_service_slug("dich-vu-seo-tong-the"))
        self.assertFalse(is_seo_aeo_service_slug("quang-cao-facebook"))


class TestClientSettings(unittest.TestCase):
    def test_upsert_and_get(self) -> None:
        conn = _mem_conn()
        conn.execute("INSERT INTO crm_customers (name) VALUES ('ACME')")
        conn.commit()
        cid = conn.execute("SELECT id FROM crm_customers").fetchone()["id"]
        upsert_settings(
            conn,
            cid,
            {"domains": ["acme.vn"], "industry": "BĐS", "contract_tier": "pro"},
        )
        s = get_settings(conn, cid)
        self.assertEqual(s["domains"], ["acme.vn"])
        self.assertEqual(s["industry"], "BĐS")
        self.assertEqual(s["contract_tier"], "pro")


class TestProjectsAndInitiatives(unittest.TestCase):
    def test_project_for_lifecycle_idempotent(self) -> None:
        conn = _mem_conn()
        conn.execute("INSERT INTO crm_customers (name) VALUES ('X')")
        conn.execute(
            "INSERT INTO crm_service_lifecycle (customer_id, service_slug) VALUES (1, 'dich-vu-aeo')"
        )
        conn.commit()
        pid1 = ensure_project_for_lifecycle(conn, customer_id=1, lifecycle_id=1, service_slug="dich-vu-aeo")
        pid2 = ensure_project_for_lifecycle(conn, customer_id=1, lifecycle_id=1, service_slug="dich-vu-aeo")
        self.assertEqual(pid1, pid2)

    def test_create_initiative(self) -> None:
        conn = _mem_conn()
        conn.execute("INSERT INTO crm_customers (name) VALUES ('X')")
        conn.commit()
        iid = create_initiative(conn, 1, {"title": "Fix schema", "roadmap_bucket": "30d"})
        rows = list_initiatives(conn, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], iid)


class TestDeliveryPanel(unittest.TestCase):
    def test_build_for_seo_slug(self) -> None:
        conn = _mem_conn()
        conn.execute("INSERT INTO crm_customers (name) VALUES ('KH')")
        conn.execute(
            "INSERT INTO crm_service_lifecycle (customer_id, service_slug) VALUES (1, 'dich-vu-seo-tong-the')"
        )
        conn.commit()
        panel = build_delivery_panel(
            conn, customer_id=1, lifecycle_id=1, service_slug="dich-vu-seo-tong-the"
        )
        self.assertIsNotNone(panel)
        assert panel is not None
        self.assertEqual(panel["project_type"], "seo")

    def test_non_seo_returns_none(self) -> None:
        conn = _mem_conn()
        self.assertIsNone(
            build_delivery_panel(
                conn, customer_id=1, lifecycle_id=1, service_slug="quang-cao-facebook"
            )
        )


class TestHubSummary(unittest.TestCase):
    def test_empty_hub(self) -> None:
        conn = _mem_conn()
        out = seo_hub_summary(conn)
        self.assertTrue(out["ok"])
        self.assertEqual(out["summary"]["seo_clients"], 0)

    def test_hub_with_lifecycle(self) -> None:
        conn = _mem_conn()
        conn.execute("INSERT INTO crm_customers (name, company) VALUES ('A', 'Co')")
        conn.execute(
            "INSERT INTO crm_service_lifecycle (customer_id, service_slug) VALUES (1, 'dich-vu-aeo')"
        )
        conn.commit()
        out = seo_hub_summary(conn)
        self.assertEqual(out["summary"]["seo_clients"], 1)
        self.assertEqual(len(out["clients"]), 1)


class TestSeoBlueprint(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.seo_aeo._can", return_value=True)
    @patch("blueprints.seo_aeo.deps.ensure_crm_session_html", return_value=None)
    @patch("blueprints.seo_aeo.deps.admin_page_template_kwargs", return_value={})
    def test_seo_hub_page(self, _kw: MagicMock, _sess: MagicMock, _can: MagicMock, _auth: MagicMock) -> None:
        resp = self.client.get("/crm/seo")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"SEO/AEO Ops", resp.data)

    @patch("blueprints.seo_aeo._can", return_value=True)
    def test_api_seo_hub(self, _can: MagicMock) -> None:
        resp = self.client.get("/api/v1/seo/hub")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()
