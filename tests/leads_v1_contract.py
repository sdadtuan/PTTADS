"""JSON Schema helpers for CRM v1 contract tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas" / "crm"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "api" / "leads-v1"

LEAD_V1_SCHEMA = SCHEMAS_DIR / "lead-v1.schema.json"
LEADS_LIST_SCHEMA = SCHEMAS_DIR / "leads-list-response-v1.schema.json"
ERROR_SCHEMA = SCHEMAS_DIR / "error-response-v1.schema.json"
OPENAPI_SPEC = SCHEMAS_DIR / "leads-v1.openapi.yaml"
CREATE_LEAD_SCHEMA = SCHEMAS_DIR / "create-lead-v1.schema.json"
PATCH_LEAD_SCHEMA = SCHEMAS_DIR / "patch-lead-v1.schema.json"
WRITE_OPENAPI_SPEC = SCHEMAS_DIR / "leads-v1-write.openapi.yaml"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(name: str) -> dict[str, Any]:
    mapping = {
        "lead-v1": LEAD_V1_SCHEMA,
        "leads-list-response-v1": LEADS_LIST_SCHEMA,
        "error-response-v1": ERROR_SCHEMA,
        "create-lead-v1": CREATE_LEAD_SCHEMA,
        "patch-lead-v1": PATCH_LEAD_SCHEMA,
    }
    path = mapping.get(name)
    if path is None:
        raise KeyError(name)
    return load_json(path)


def load_golden(name: str) -> Any:
    path = FIXTURES_DIR / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return load_json(path)


def validate_instance(instance: Any, schema_name: str) -> None:
    """Validate JSON instance against a named CRM v1 schema."""
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError as exc:
        raise RuntimeError("jsonschema required for contract tests: pip install jsonschema") from exc

    schema = load_schema(schema_name)
    resources = [Resource.from_contents(s) for s in _all_schemas()]
    registry = Registry().with_resources((r.id(), r) for r in resources)
    Draft202012Validator(schema, registry=registry).validate(instance)


def _all_schemas() -> list[dict[str, Any]]:
    return [load_json(p) for p in SCHEMAS_DIR.glob("*.schema.json")]
