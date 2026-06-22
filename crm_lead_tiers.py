"""FR-04: Phân hạng lead theo ngưỡng điểm — bảng phân loại cấu hình được."""
from __future__ import annotations

import copy
import re
from typing import Any

UNCLASSIFIED_TIER_ID = "unclassified"

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

DEFAULT_LEVEL_TIERS: list[dict[str, Any]] = [
    {
        "id": "vip",
        "label": "VIP",
        "emoji": "🔴",
        "description": "Siêu nóng, ưu tiên tuyệt đối",
        "sla_label": "< 2 phút",
        "min_score": 90,
        "max_score": 100,
        "enabled": True,
        "sort_order": 1,
    },
    {
        "id": "hot",
        "label": "HOT",
        "emoji": "🟠",
        "description": "Nóng, cần liên hệ ngay",
        "sla_label": "< 5 phút",
        "min_score": 75,
        "max_score": 89,
        "enabled": True,
        "sort_order": 2,
    },
    {
        "id": "warm_plus",
        "label": "WARM+",
        "emoji": "🟡",
        "description": "Ấm tốt, có tiềm năng cao",
        "sla_label": "< 30 phút",
        "min_score": 55,
        "max_score": 74,
        "enabled": True,
        "sort_order": 3,
    },
    {
        "id": "warm",
        "label": "WARM",
        "emoji": "🟢",
        "description": "Ấm thường, cần nurturing",
        "sla_label": "Trong ngày",
        "min_score": 35,
        "max_score": 54,
        "enabled": True,
        "sort_order": 4,
    },
    {
        "id": "cold_plus",
        "label": "COLD+",
        "emoji": "🔵",
        "description": "Lạnh nhưng có tiềm năng",
        "sla_label": "Trong tuần",
        "min_score": 15,
        "max_score": 34,
        "enabled": True,
        "sort_order": 5,
    },
    {
        "id": "cold",
        "label": "COLD",
        "emoji": "⚫",
        "description": "Lạnh, cần nuôi dưỡng dài hạn",
        "sla_label": "Automation",
        "min_score": 0,
        "max_score": 14,
        "enabled": True,
        "sort_order": 6,
    },
]


def _slug_id(label: str) -> str:
    raw = str(label or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if slug and _ID_RE.match(slug):
        return slug[:32]
    return f"tier_{abs(hash(label)) % 100000}"


def _normalize_tier_item(item: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    base = fallback or {}
    label = str(item.get("label") or base.get("label") or "").strip()
    if not label:
        raise ValueError("Phân hạng phải có tên.")
    rid = str(item.get("id") or base.get("id") or "").strip().lower()
    if not rid:
        rid = _slug_id(label)
    if not _ID_RE.match(rid):
        raise ValueError(f"Mã phân hạng «{rid}» không hợp lệ (a-z, số, _).")
    try:
        min_score = int(item.get("min_score", base.get("min_score", 0)))
        max_score = int(item.get("max_score", base.get("max_score", 100)))
    except (TypeError, ValueError):
        raise ValueError(f"Ngưỡng điểm phân hạng «{label}» không hợp lệ.")
    min_score = max(0, min(100, min_score))
    max_score = max(0, min(100, max_score))
    if min_score > max_score:
        raise ValueError(f"Phân hạng «{label}»: điểm từ phải ≤ điểm đến.")
    try:
        sort_order = int(item.get("sort_order", base.get("sort_order", 99)))
    except (TypeError, ValueError):
        sort_order = 99
    emoji = str(item.get("emoji") or base.get("emoji") or "").strip()[:8]
    description = str(item.get("description") or base.get("description") or "").strip()[:500]
    sla_label = str(item.get("sla_label") or base.get("sla_label") or "").strip()[:120]
    return {
        "id": rid,
        "label": label[:80],
        "emoji": emoji,
        "description": description,
        "sla_label": sla_label,
        "min_score": min_score,
        "max_score": max_score,
        "enabled": bool(item.get("enabled", base.get("enabled", True))),
        "sort_order": sort_order,
        "custom": bool(item.get("custom", rid not in {t["id"] for t in DEFAULT_LEVEL_TIERS})),
    }


def _validate_no_overlap(tiers: list[dict[str, Any]]) -> None:
    enabled = [t for t in tiers if t.get("enabled", True)]
    for i, a in enumerate(enabled):
        for b in enabled[i + 1 :]:
            if a["min_score"] <= b["max_score"] and b["min_score"] <= a["max_score"]:
                raise ValueError(
                    f"Ngưỡng điểm trùng: «{a['label']}» ({a['min_score']}–{a['max_score']}) "
                    f"và «{b['label']}» ({b['min_score']}–{b['max_score']})."
                )


def normalize_level_tiers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("level_tiers phải là mảng.")
    if not raw:
        raise ValueError("Cần ít nhất một phân hạng lead.")
    defaults_by_id = {str(t["id"]): t for t in DEFAULT_LEVEL_TIERS}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("id") or "").strip().lower()
        fb = defaults_by_id.get(rid)
        norm = _normalize_tier_item(item, fallback=fb)
        if norm["id"] in seen:
            raise ValueError(f"Phân hạng trùng mã: {norm['id']}")
        seen.add(norm["id"])
        out.append(norm)
    if not out:
        raise ValueError("Cần ít nhất một phân hạng lead.")
    if len(out) > 20:
        raise ValueError("Tối đa 20 phân hạng lead.")
    _validate_no_overlap(out)
    out.sort(key=lambda t: (int(t.get("sort_order", 99)), -int(t["min_score"])))
    return out


def merge_level_tiers(raw: list[Any] | None) -> list[dict[str, Any]]:
    """Chuẩn hóa cấu hình — trả mặc định nếu chưa lưu."""
    if not raw or not isinstance(raw, list):
        return [copy.deepcopy(t) for t in DEFAULT_LEVEL_TIERS]
    try:
        return normalize_level_tiers(raw)
    except ValueError:
        return [copy.deepcopy(t) for t in DEFAULT_LEVEL_TIERS]


def fetch_level_tiers(conn: Any | None) -> list[dict[str, Any]]:
    if conn is None:
        return merge_level_tiers(None)
    from crm_lead_rules import fetch_lead_config

    cfg = fetch_lead_config(conn)
    stored = cfg.get("level_tiers")
    if isinstance(stored, list) and stored:
        return merge_level_tiers(stored)
    return merge_level_tiers(None)


def tier_display_label(tier: dict[str, Any]) -> str:
    em = str(tier.get("emoji") or "").strip()
    lab = str(tier.get("label") or tier.get("id") or "").strip()
    return f"{em} {lab}".strip() if em else lab


def level_labels_map(conn: Any | None = None, tiers: list[dict[str, Any]] | None = None) -> dict[str, str]:
    active = tiers if tiers is not None else fetch_level_tiers(conn)
    return {str(t["id"]): tier_display_label(t) for t in active}


def classify_score_to_tier(score: int, tiers: list[dict[str, Any]] | None = None) -> str:
    """Áp ngưỡng điểm → mã phân hạng."""
    active = tiers if tiers is not None else merge_level_tiers(None)
    s = max(0, min(100, int(score)))
    enabled = [t for t in active if t.get("enabled", True)]
    if not enabled:
        return UNCLASSIFIED_TIER_ID
    for t in sorted(enabled, key=lambda x: -int(x["min_score"])):
        if int(t["min_score"]) <= s <= int(t["max_score"]):
            return str(t["id"])
    fallback = sorted(enabled, key=lambda x: int(x["min_score"]))
    return str(fallback[0]["id"]) if fallback else UNCLASSIFIED_TIER_ID


def tier_range_label(tier: dict[str, Any]) -> str:
    return f"{int(tier['min_score'])}–{int(tier['max_score'])}"
