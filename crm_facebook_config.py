"""Cấu hình tích hợp Facebook Lead Ads — page/form chỉ định."""
from __future__ import annotations

import copy
import re
from typing import Any

DEFAULT_FACEBOOK_CONFIG: dict[str, Any] = {
    "enabled": False,
    "page_id": "",
    "page_name": "",
    "form_ids": [],
    "webhook_enabled": True,
    "auto_sync": True,
    "sync_interval_minutes": 5,
    "auto_optimize": True,
    "auto_score": True,
    "auto_assign": True,
    "last_sync_at": "",
    "last_sync_count": 0,
    "last_sync_message": "",
    "last_webhook_at": "",
    "last_webhook_events": 0,
    "last_webhook_created": 0,
    "last_webhook_message": "",
    "leads_live_revision": 0,
}


def _split_ids(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        parts = re.split(r"[,;\s]+", raw.strip())
        return [p for p in parts if p]
    return []


def merge_facebook_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = copy.deepcopy(DEFAULT_FACEBOOK_CONFIG)
    if not isinstance(raw, dict):
        return base
    if "enabled" in raw:
        base["enabled"] = bool(raw["enabled"])
    if base["enabled"] and "auto_sync" not in raw:
        base["auto_sync"] = True
    if "page_id" in raw:
        base["page_id"] = str(raw.get("page_id") or "").strip()
    if "page_name" in raw:
        base["page_name"] = str(raw.get("page_name") or "").strip()[:120]
    if "form_ids" in raw:
        base["form_ids"] = _split_ids(raw["form_ids"])
    if "webhook_enabled" in raw:
        base["webhook_enabled"] = bool(raw["webhook_enabled"])
    if "auto_sync" in raw:
        base["auto_sync"] = bool(raw["auto_sync"])
    if "auto_optimize" in raw:
        base["auto_optimize"] = bool(raw["auto_optimize"])
    if "auto_score" in raw:
        base["auto_score"] = bool(raw["auto_score"])
    if "auto_assign" in raw:
        base["auto_assign"] = bool(raw["auto_assign"])
    if "last_sync_at" in raw:
        base["last_sync_at"] = str(raw.get("last_sync_at") or "").strip()[:40]
    if "last_sync_count" in raw:
        try:
            base["last_sync_count"] = max(0, int(raw.get("last_sync_count") or 0))
        except (TypeError, ValueError):
            pass
    if "last_sync_message" in raw:
        base["last_sync_message"] = str(raw.get("last_sync_message") or "").strip()[:500]
    if "last_webhook_at" in raw:
        base["last_webhook_at"] = str(raw.get("last_webhook_at") or "").strip()[:40]
    if "last_webhook_events" in raw:
        try:
            base["last_webhook_events"] = max(0, int(raw.get("last_webhook_events") or 0))
        except (TypeError, ValueError):
            pass
    if "last_webhook_created" in raw:
        try:
            base["last_webhook_created"] = max(0, int(raw.get("last_webhook_created") or 0))
        except (TypeError, ValueError):
            pass
    if "last_webhook_message" in raw:
        base["last_webhook_message"] = str(raw.get("last_webhook_message") or "").strip()[:500]
    if "leads_live_revision" in raw:
        try:
            base["leads_live_revision"] = max(0, int(raw.get("leads_live_revision") or 0))
        except (TypeError, ValueError):
            pass
    if "graph_rate_limited_until" in raw:
        base["graph_rate_limited_until"] = str(raw.get("graph_rate_limited_until") or "").strip()[:40]
    if "graph_rate_limited_message" in raw:
        base["graph_rate_limited_message"] = str(raw.get("graph_rate_limited_message") or "").strip()[:500]
    try:
        iv = int(raw.get("sync_interval_minutes", base["sync_interval_minutes"]))
        base["sync_interval_minutes"] = max(5, min(1440, iv))
    except (TypeError, ValueError):
        pass
    return base


def normalize_facebook_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("facebook_config phải là object.")
    cfg = merge_facebook_config(raw)
    if cfg["enabled"] and not cfg["page_id"] and not cfg["form_ids"]:
        raise ValueError("Bật Facebook Lead cần Page ID hoặc ít nhất một Form ID.")
    return cfg


def fetch_facebook_config(conn: Any) -> dict[str, Any]:
    from crm_lead_rules import fetch_lead_config

    cfg = fetch_lead_config(conn)
    return merge_facebook_config(cfg.get("facebook_config"))


def matches_facebook_source(item: dict[str, Any], fb_cfg: dict[str, Any]) -> tuple[bool, str]:
    """Kiểm tra lead thuộc page/form đã cấu hình."""
    if not fb_cfg.get("enabled"):
        return False, "Facebook Lead chưa bật trong cấu hình."
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    page_id = str(meta.get("facebook_page_id") or item.get("facebook_page_id") or "").strip()
    form_id = str(meta.get("facebook_form_id") or item.get("facebook_form_id") or "").strip()

    cfg_page = str(fb_cfg.get("page_id") or "").strip()
    cfg_forms = [str(x).strip() for x in (fb_cfg.get("form_ids") or []) if str(x).strip()]

    if cfg_forms and form_id and form_id not in cfg_forms:
        return (
            False,
            f"Form Facebook (ID {form_id}) chưa được thêm trong cấu hình CRM.",
        )
    if cfg_forms and not form_id:
        # Lead nhập tay / sync không có form_id — vẫn cho qua
        pass
    if cfg_page and page_id and page_id != cfg_page:
        return (
            False,
            f"Page Facebook (ID {page_id}) không khớp Page đã cấu hình ({cfg_page}).",
        )
    return True, ""
