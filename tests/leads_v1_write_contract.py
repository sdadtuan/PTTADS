"""JSON Schema helpers for CRM v1 write contract tests."""
from __future__ import annotations

import re

from tests.leads_v1_contract import WRITE_OPENAPI_SPEC, validate_instance

FROZEN_WRITE_VERSION = "1.0.0"
FROZEN_WRITE_STATUS = "frozen"

_VERSION_RE = re.compile(r"^\s*version:\s*([^\s#]+)\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"^\s*x-ptt-contract-status:\s*(\S+)\s*$", re.MULTILINE)


def validate_create_lead(instance: object) -> None:
    validate_instance(instance, "create-lead-v1")


def validate_patch_lead(instance: object) -> None:
    validate_instance(instance, "patch-lead-v1")


def load_write_openapi_text() -> str:
    return WRITE_OPENAPI_SPEC.read_text(encoding="utf-8")


def parse_write_openapi_version() -> str:
    text = load_write_openapi_text()
    m = _VERSION_RE.search(text)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def parse_write_contract_status() -> str:
    text = load_write_openapi_text()
    m = _STATUS_RE.search(text)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def assert_write_openapi_frozen() -> None:
    version = parse_write_openapi_version()
    status = parse_write_contract_status()
    if version != FROZEN_WRITE_VERSION:
        raise AssertionError(f"write OpenAPI version must be {FROZEN_WRITE_VERSION}, got {version!r}")
    if "draft" in version.lower():
        raise AssertionError("write OpenAPI must not be draft")
    if status != FROZEN_WRITE_STATUS:
        raise AssertionError(f"x-ptt-contract-status must be {FROZEN_WRITE_STATUS!r}, got {status!r}")
    text = load_write_openapi_text()
    for needle in ("create-lead-v1.schema.json", "patch-lead-v1.schema.json", "lead-v1.schema.json"):
        if needle not in text:
            raise AssertionError(f"write OpenAPI missing reference: {needle}")
