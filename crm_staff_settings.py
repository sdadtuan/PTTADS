"""Cấu hình hệ thống phân cấp nhân viên — lưu trong crm_staff_settings."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from crm_staff_competency import (
    METRIC_OPTIONS,
    default_competency_config,
    merge_competency_config,
    normalize_competency_config,
)
from crm_staff_levels import DEFAULT_STAFF_LEVELS, merge_staff_levels, normalize_staff_levels

DEFAULT_STAFF_CONFIG: dict[str, Any] = {
    "staff_levels": DEFAULT_STAFF_LEVELS,
    "competency": default_competency_config(),
}


def ensure_staff_settings_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff_settings (
            config_key TEXT PRIMARY KEY,
            config_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT ''
        )
        """
    )


def fetch_staff_config(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_staff_settings_schema(conn)
    row = conn.execute(
        "SELECT config_json FROM crm_staff_settings WHERE config_key = 'global'"
    ).fetchone()
    cfg = dict(DEFAULT_STAFF_CONFIG)
    if row:
        try:
            raw = json.loads(str(row["config_json"] or "{}"))
            if isinstance(raw, dict):
                cfg.update(raw)
        except json.JSONDecodeError:
            pass
    stored = cfg.get("staff_levels")
    if isinstance(stored, list) and stored:
        cfg["staff_levels"] = merge_staff_levels(stored)
    else:
        cfg["staff_levels"] = [dict(d) for d in DEFAULT_STAFF_LEVELS]
    stored_comp = cfg.get("competency")
    if isinstance(stored_comp, dict):
        cfg["competency"] = merge_competency_config(stored_comp)
    else:
        cfg["competency"] = default_competency_config()
    return cfg


def save_staff_config(
    conn: sqlite3.Connection,
    *,
    config: dict[str, Any],
    updated_by: str,
    ts: str,
) -> dict[str, Any]:
    ensure_staff_settings_schema(conn)
    merged = fetch_staff_config(conn)
    if "staff_levels" in config:
        merged["staff_levels"] = normalize_staff_levels(config["staff_levels"])
    if "competency" in config:
        merged["competency"] = normalize_competency_config(config["competency"])
    conn.execute(
        """
        INSERT INTO crm_staff_settings (config_key, config_json, updated_at, updated_by)
        VALUES ('global', ?, ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET
            config_json = excluded.config_json,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (json.dumps(merged, ensure_ascii=False), ts, updated_by[:120]),
    )
    conn.commit()
    return fetch_staff_config(conn)


def fetch_staff_competency(conn: sqlite3.Connection | None) -> dict[str, Any]:
    if conn is None:
        return default_competency_config()
    cfg = fetch_staff_config(conn)
    comp = cfg.get("competency")
    if isinstance(comp, dict):
        return merge_competency_config(comp)
    return default_competency_config()
