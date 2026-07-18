"""Contract tests — CRM Leads API v1 write (Phase 2 W3 freeze)."""
from __future__ import annotations

import unittest

from tests.leads_v1_contract import (
    CREATE_LEAD_SCHEMA,
    PATCH_LEAD_SCHEMA,
    SCHEMAS_DIR,
    WRITE_OPENAPI_SPEC,
    validate_instance,
)
from tests.leads_v1_write_contract import (
    FROZEN_WRITE_STATUS,
    FROZEN_WRITE_VERSION,
    assert_write_openapi_frozen,
    validate_create_lead,
    validate_patch_lead,
)


class TestLeadsV1WriteSchemaArtifacts(unittest.TestCase):
    def test_write_schema_files_exist(self) -> None:
        for path in (CREATE_LEAD_SCHEMA, PATCH_LEAD_SCHEMA, WRITE_OPENAPI_SPEC):
            self.assertTrue(path.is_file(), msg=str(path))

    def test_write_openapi_frozen_marker(self) -> None:
        assert_write_openapi_frozen()

    def test_write_openapi_references_schemas(self) -> None:
        text = WRITE_OPENAPI_SPEC.read_text(encoding="utf-8")
        self.assertIn("create-lead-v1.schema.json", text)
        self.assertIn("patch-lead-v1.schema.json", text)
        self.assertIn("/api/v1/leads", text)
        self.assertIn(FROZEN_WRITE_VERSION, text)
        self.assertIn(FROZEN_WRITE_STATUS, text)


class TestLeadsV1WriteGoldenExamples(unittest.TestCase):
    def test_create_lead_example_validates(self) -> None:
        payload = {
            "full_name": "Staging Lead",
            "phone": "0903333333",
            "channel": "meta",
            "client_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "new",
            "source": "staging",
        }
        validate_create_lead(payload)

    def test_patch_assign_example_validates(self) -> None:
        validate_patch_lead({"owner_id": 42, "assigned_by": "admin"})

    def test_patch_score_stub_validates(self) -> None:
        validate_patch_lead({"score": 78})

    def test_patch_rejects_unknown_fields(self) -> None:
        with self.assertRaises(Exception):
            validate_patch_lead({"owner_id": 1, "unexpected": True})

    def test_create_requires_full_name(self) -> None:
        with self.assertRaises(Exception):
            validate_create_lead({"phone": "090"})


class TestLeadsV1WriteOpenApiFreezeGuard(unittest.TestCase):
    def test_version_not_draft(self) -> None:
        from tests.leads_v1_write_contract import parse_write_openapi_version

        version = parse_write_openapi_version()
        self.assertEqual(version, FROZEN_WRITE_VERSION)
        self.assertNotIn("draft", version.lower())

    def test_all_crm_schemas_registered(self) -> None:
        from tests.leads_v1_contract import load_schema

        for name in (
            "lead-v1",
            "create-lead-v1",
            "patch-lead-v1",
            "leads-list-response-v1",
            "error-response-v1",
        ):
            schema = load_schema(name)
            self.assertIn("$schema", schema)


if __name__ == "__main__":
    unittest.main()
