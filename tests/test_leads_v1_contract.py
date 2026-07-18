"""Contract tests — CRM Leads API v1 (Phase 1b Bước 2).

Validates golden fixtures and Flask responses against JSON Schema + frozen fixtures.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.leads_v1_contract import (
    FIXTURES_DIR,
    OPENAPI_SPEC,
    SCHEMAS_DIR,
    load_golden,
    validate_instance,
)


class TestLeadsV1SchemaArtifacts(unittest.TestCase):
    def test_schema_files_exist(self) -> None:
        for name in (
            "lead-v1.schema.json",
            "leads-list-response-v1.schema.json",
            "error-response-v1.schema.json",
            "leads-v1.openapi.yaml",
        ):
            self.assertTrue((SCHEMAS_DIR / name).is_file(), msg=name)

    def test_openapi_references_lead_schema(self) -> None:
        text = OPENAPI_SPEC.read_text(encoding="utf-8")
        self.assertIn("lead-v1.schema.json", text)
        self.assertIn("/api/v1/leads", text)

    def test_golden_fixtures_exist(self) -> None:
        for name in ("lead_v1.json", "list_leads_response.json", "not_found.json"):
            self.assertTrue((FIXTURES_DIR / name).is_file(), msg=name)


class TestLeadsV1GoldenFixtures(unittest.TestCase):
    def test_lead_v1_golden_validates(self) -> None:
        validate_instance(load_golden("lead_v1.json"), "lead-v1")

    def test_list_response_golden_validates(self) -> None:
        validate_instance(load_golden("list_leads_response.json"), "leads-list-response-v1")

    def test_not_found_golden_validates(self) -> None:
        validate_instance(load_golden("not_found.json"), "error-response-v1")


class TestLeadsV1ReadLayerContract(unittest.TestCase):
    CLIENT_ID = "550e8400-e29b-41d4-a716-446655440000"

    def _seed_db(self, tmp: str) -> Path:
        db = Path(tmp) / "contract.db"
        conn = sqlite3.connect(db)
        conn.execute(
            """
            CREATE TABLE crm_leads (
                id INTEGER PRIMARY KEY,
                full_name TEXT, phone TEXT, email TEXT,
                status TEXT, source TEXT, owner_id INTEGER,
                created_at TEXT, is_duplicate INTEGER DEFAULT 0,
                meta_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute(
            "INSERT INTO crm_leads (full_name, phone, status, source, created_at, meta_json) VALUES (?,?,?,?,?,?)",
            (
                "Lead A",
                "0901111111",
                "new",
                "facebook",
                "2026-07-17",
                json.dumps(
                    {
                        "agency_client_id": self.CLIENT_ID,
                        "channel": "meta",
                        "facebook_leadgen_id": "fb-1",
                    }
                ),
            ),
        )
        conn.commit()
        conn.close()
        return db

    def test_lead_row_to_v1_matches_golden(self) -> None:
        from ptt_crm.leads_read import lead_row_to_v1

        row = {
            "id": 1,
            "full_name": "Lead A",
            "phone": "0901111111",
            "email": "",
            "status": "new",
            "source": "facebook",
            "owner_id": None,
            "created_at": "2026-07-17",
            "is_duplicate": 0,
            "meta_json": json.dumps(
                {
                    "agency_client_id": self.CLIENT_ID,
                    "channel": "meta",
                    "facebook_leadgen_id": "fb-1",
                }
            ),
        }
        golden = load_golden("lead_v1.json")
        out = lead_row_to_v1(row)
        self.assertEqual(out, golden)
        validate_instance(out, "lead-v1")

    def test_list_leads_v1_matches_golden(self) -> None:
        from ptt_crm.leads_read import list_leads_v1

        golden = load_golden("list_leads_response.json")
        with tempfile.TemporaryDirectory() as tmp:
            db = self._seed_db(tmp)
            with patch("ptt_crm.leads_read.sqlite_db_path", return_value=str(db)):
                leads, total = list_leads_v1(
                    client_id=self.CLIENT_ID,
                    limit=50,
                    offset=0,
                )
        payload = {"leads": leads, "total": total, "limit": 50, "offset": 0}
        self.assertEqual(payload, golden)
        validate_instance(payload, "leads-list-response-v1")

    def test_get_lead_v1_matches_golden(self) -> None:
        from ptt_crm.leads_read import get_lead_v1

        golden = load_golden("lead_v1.json")
        with tempfile.TemporaryDirectory() as tmp:
            db = self._seed_db(tmp)
            with patch("ptt_crm.leads_read.sqlite_db_path", return_value=str(db)):
                lead = get_lead_v1(1)
        self.assertEqual(lead, golden)
        validate_instance(lead, "lead-v1")


class TestLeadsV1FlaskApiContract(unittest.TestCase):
    CLIENT_ID = "550e8400-e29b-41d4-a716-446655440000"

    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    def test_api_list_leads_matches_golden(self, _can: MagicMock, _auth: MagicMock) -> None:
        golden = load_golden("list_leads_response.json")
        with patch(
            "ptt_crm.leads_read.list_leads_v1",
            return_value=(golden["leads"], golden["total"]),
        ):
            resp = self.client.get("/api/v1/leads?limit=50&offset=0")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data, golden)
        validate_instance(data, "leads-list-response-v1")

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    def test_api_get_lead_matches_golden(self, _can: MagicMock, _auth: MagicMock) -> None:
        golden = load_golden("lead_v1.json")
        with patch("ptt_crm.leads_read.get_lead_v1", return_value=golden):
            resp = self.client.get("/api/v1/leads/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data, golden)
        validate_instance(data, "lead-v1")

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    def test_api_get_lead_404_matches_golden(self, _can: MagicMock, _auth: MagicMock) -> None:
        golden = load_golden("not_found.json")
        with patch("ptt_crm.leads_read.get_lead_v1", return_value=None):
            resp = self.client.get("/api/v1/leads/999")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertEqual(data, golden)
        validate_instance(data, "error-response-v1")


if __name__ == "__main__":
    unittest.main()
