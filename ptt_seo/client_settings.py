"""Client SEO/AEO settings (module 6.1)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _loads(raw: str | None, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    d["domains"] = _loads(d.pop("domains_json", "[]"), [])
    d["markets"] = _loads(d.pop("markets_json", "[]"), [])
    d["languages"] = _loads(d.pop("languages_json", '["vi"]'), ["vi"])
    d["brand_guidelines"] = _loads(d.pop("brand_guidelines_json", "{}"), {})
    d["seo_guidelines"] = _loads(d.pop("seo_guidelines_json", "{}"), {})
    d["aeo_guidelines"] = _loads(d.pop("aeo_guidelines_json", "{}"), {})
    d["integrations"] = _loads(d.pop("integrations_json", "{}"), {})
    return d


def get_settings(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM seo_client_settings WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    if row is None:
        return {
            "customer_id": customer_id,
            "domains": [],
            "markets": [],
            "languages": ["vi"],
            "industry": "",
            "brand_guidelines": {},
            "seo_guidelines": {},
            "aeo_guidelines": {},
            "contract_tier": "standard",
            "notes": "",
            "integrations": {},
            "updated_at": None,
        }
    return _row_to_dict(row)  # type: ignore[return-value]


def upsert_settings(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    existing = get_settings(conn, customer_id)
    merged = {**existing, **{k: v for k, v in payload.items() if k != "customer_id"}}
    conn.execute(
        """
        INSERT INTO seo_client_settings (
            customer_id, domains_json, markets_json, languages_json, industry,
            brand_guidelines_json, seo_guidelines_json, aeo_guidelines_json,
            contract_tier, notes, integrations_json, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(customer_id) DO UPDATE SET
            domains_json=excluded.domains_json,
            markets_json=excluded.markets_json,
            languages_json=excluded.languages_json,
            industry=excluded.industry,
            brand_guidelines_json=excluded.brand_guidelines_json,
            seo_guidelines_json=excluded.seo_guidelines_json,
            aeo_guidelines_json=excluded.aeo_guidelines_json,
            contract_tier=excluded.contract_tier,
            notes=excluded.notes,
            integrations_json=excluded.integrations_json,
            updated_at=excluded.updated_at
        """,
        (
            customer_id,
            json.dumps(merged.get("domains") or [], ensure_ascii=False),
            json.dumps(merged.get("markets") or [], ensure_ascii=False),
            json.dumps(merged.get("languages") or ["vi"], ensure_ascii=False),
            str(merged.get("industry") or ""),
            json.dumps(merged.get("brand_guidelines") or {}, ensure_ascii=False),
            json.dumps(merged.get("seo_guidelines") or {}, ensure_ascii=False),
            json.dumps(merged.get("aeo_guidelines") or {}, ensure_ascii=False),
            str(merged.get("contract_tier") or "standard"),
            str(merged.get("notes") or ""),
            json.dumps(merged.get("integrations") or {}, ensure_ascii=False),
            _ts(),
        ),
    )
    conn.commit()
    return get_settings(conn, customer_id)
