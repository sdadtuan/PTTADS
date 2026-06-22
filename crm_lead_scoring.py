"""FR-03: Chấm điểm lead theo rubric D1–D6 (có thể cấu hình)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# Legacy flat rules — chỉ dùng khi cấu hình cũ scoring_rules được lưu riêng.
DEFAULT_SCORING_RULES: list[dict[str, Any]] = [
    {"id": "valid_phone", "label": "Có số điện thoại hợp lệ", "points": 20, "enabled": True, "condition": "valid_phone"},
    {"id": "valid_email", "label": "Có email hợp lệ", "points": 10, "enabled": True, "condition": "valid_email"},
    {"id": "ask_price", "label": "Hỏi giá", "points": 25, "enabled": True, "condition": "ask_price"},
    {"id": "request_demo", "label": "Xin demo", "points": 25, "enabled": True, "condition": "request_demo"},
    {"id": "clear_need", "label": "Có nhu cầu rõ", "points": 20, "enabled": True, "condition": "clear_need"},
    {"id": "buy_soon", "label": "Có thời điểm mua gần", "points": 20, "enabled": True, "condition": "buy_soon"},
    {"id": "high_interaction", "label": "Tương tác nhiều lần", "points": 15, "enabled": True, "condition": "high_interaction"},
    {"id": "referral_source", "label": "Lead giới thiệu", "points": 15, "enabled": True, "condition": "referral_source"},
    {"id": "no_response_3x", "label": "Không phản hồi 3 lần", "points": -20, "enabled": True, "condition": "no_response_3x"},
    {"id": "missing_data", "label": "Dữ liệu thiếu", "points": -15, "enabled": True, "condition": "missing_data"},
    {"id": "spam", "label": "Spam", "points": -100, "enabled": True, "condition": "spam"},
]

SCORING_RULE_IDS: tuple[str, ...] = tuple(r["id"] for r in DEFAULT_SCORING_RULES)

SCORING_CONDITIONS: list[dict[str, Any]] = [
    {"id": "valid_phone", "label": "Có số điện thoại hợp lệ", "group": "builtin"},
    {"id": "valid_email", "label": "Có email hợp lệ", "group": "builtin"},
    {"id": "ask_price", "label": "Hỏi giá (từ khóa)", "group": "builtin"},
    {"id": "request_demo", "label": "Xin demo (từ khóa)", "group": "builtin"},
    {"id": "clear_need", "label": "Có nhu cầu rõ", "group": "builtin"},
    {"id": "buy_soon", "label": "Thời điểm mua gần (từ khóa)", "group": "builtin"},
    {"id": "high_interaction", "label": "Tương tác ≥ 2 lần", "group": "builtin"},
    {"id": "referral_source", "label": "Nguồn giới thiệu", "group": "builtin"},
    {"id": "no_response_3x", "label": "Không phản hồi ≥ 3 lần", "group": "builtin"},
    {"id": "missing_data", "label": "Dữ liệu thiếu / chưa sạch", "group": "builtin"},
    {"id": "spam", "label": "Spam (từ khóa / meta)", "group": "builtin"},
    {"id": "keyword", "label": "Chứa từ khóa tùy chỉnh", "group": "custom", "params": ("keywords",)},
    {"id": "source_is", "label": "Nguồn lead bằng", "group": "custom", "params": ("source",)},
    {"id": "field_has_text", "label": "Trường có nội dung", "group": "custom", "params": ("field", "min_count")},
    {"id": "min_activities", "label": "Số activity (không system) ≥", "group": "custom", "params": ("min_count",)},
    {"id": "meta_flag", "label": "Meta có cờ (key)", "group": "custom", "params": ("meta_key",)},
]

VALID_CONDITIONS: frozenset[str] = frozenset(c["id"] for c in SCORING_CONDITIONS)

_ASK_PRICE = (
    "gia",
    "báo giá",
    "bao gia",
    "price",
    "chi phí",
    "chi phi",
    "cost",
    "quote",
    "hỏi giá",
    "hoi gia",
    "bảng giá",
    "bang gia",
)
_REQUEST_DEMO = (
    "demo",
    "xem thử",
    "xem thu",
    "trial",
    "dùng thử",
    "dung thu",
    "pilot",
    "presentation",
    "trình diễn",
    "trinh dien",
)
_BUY_SOON = (
    "gấp",
    "gap",
    "ngay",
    "tuần này",
    "tuan nay",
    "tháng này",
    "thang nay",
    "sớm",
    "som",
    "urgent",
    "asap",
    "mua ngay",
    "triển khai",
    "trien khai",
    "tuần tới",
    "tuan toi",
)
_SPAM = ("spam", "quảng cáo", "quang cao", "lừa đảo", "lua dao", "xxx", "fake lead")
_NO_RESPONSE = (
    "không nghe",
    "khong nghe",
    "không bắt máy",
    "khong bat may",
    "không phản hồi",
    "khong phan hoi",
    "no answer",
    "no response",
    "busy",
    "tắt máy",
    "tat may",
    "voicemail",
    "không liên lạc được",
    "khong lien lac duoc",
)

SCORING_FIELD_OPTIONS: tuple[str, ...] = ("need", "product_interest", "region", "phone", "email", "full_name")


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    folded = _fold(text)
    return any(kw in folded for kw in keywords)


def _parse_keywords(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(k).strip() for k in raw if str(k).strip()]
    text = str(raw or "").replace(";", ",")
    return [k.strip() for k in text.split(",") if k.strip()]


def _slug_from_label(label: str) -> str:
    folded = _fold(label)[:48]
    slug = re.sub(r"[^a-z0-9]+", "_", folded).strip("_")
    return slug or "rule"


def _condition_label(condition: str) -> str:
    for c in SCORING_CONDITIONS:
        if c["id"] == condition:
            return str(c["label"])
    return condition


def _normalize_rule_item(item: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    base = fallback or {}
    label = str(item.get("label") or base.get("label") or "").strip()
    if not label:
        raise ValueError("Rule phải có tên.")
    rid = str(item.get("id") or base.get("id") or "").strip()
    if not rid:
        rid = f"custom_{_slug_from_label(label)}"
    cond = str(item.get("condition") or base.get("condition") or rid).strip()
    if cond not in VALID_CONDITIONS:
        raise ValueError(f"Điều kiện «{cond}» không hợp lệ.")
    try:
        points = int(item.get("points", base.get("points", 0)))
    except (TypeError, ValueError):
        points = int(base.get("points") or 0)
    keywords = _parse_keywords(item.get("keywords", base.get("keywords", "")))
    try:
        min_count = max(1, int(item.get("min_count", base.get("min_count", 2))))
    except (TypeError, ValueError):
        min_count = 2
    field = str(item.get("field") or base.get("field") or "need").strip()
    if field not in SCORING_FIELD_OPTIONS:
        field = "need"
    source = str(item.get("source") or base.get("source") or "").strip()[:40]
    meta_key = str(item.get("meta_key") or base.get("meta_key") or "spam").strip()[:40]
    custom = bool(item.get("custom", rid.startswith("custom_") or rid not in SCORING_RULE_IDS))
    return {
        "id": rid[:80],
        "label": label[:120],
        "points": max(-100, min(100, points)),
        "enabled": bool(item.get("enabled", base.get("enabled", True))),
        "condition": cond[:40],
        "condition_label": _condition_label(cond),
        "keywords": keywords,
        "keywords_text": ", ".join(keywords),
        "source": source,
        "field": field,
        "min_count": min_count,
        "meta_key": meta_key,
        "custom": custom,
    }


def merge_scoring_rules(raw: list[Any] | None) -> list[dict[str, Any]]:
    """Trả danh sách rule — mặc định nếu chưa lưu, ngược lại dùng bản đã cấu hình."""
    if not raw:
        return [_normalize_rule_item(dict(r), fallback=r) for r in DEFAULT_SCORING_RULES]
    try:
        return normalize_scoring_rules(raw)
    except ValueError:
        return merge_scoring_rules(None)


def normalize_scoring_rules(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("scoring_rules phải là mảng.")
    if not raw:
        return merge_scoring_rules(None)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        fallback = next((d for d in DEFAULT_SCORING_RULES if d["id"] == str(item.get("id") or "")), None)
        norm = _normalize_rule_item(item, fallback=fallback)
        if norm["id"] in seen:
            raise ValueError(f"Rule trùng id: {norm['id']}")
        if norm["condition"] == "keyword" and not norm["keywords"]:
            raise ValueError(f"Rule «{norm['label']}» cần từ khóa.")
        if norm["condition"] == "source_is" and not norm["source"]:
            raise ValueError(f"Rule «{norm['label']}» cần chọn nguồn lead.")
        seen.add(norm["id"])
        out.append(norm)
    if not out:
        raise ValueError("Cần ít nhất một rule chấm điểm.")
    if len(out) > 50:
        raise ValueError("Tối đa 50 rule chấm điểm.")
    return out


def fetch_scoring_rules(conn: Any | None) -> list[dict[str, Any]]:
    if conn is None:
        return merge_scoring_rules([])
    from crm_lead_rules import fetch_lead_config

    cfg = fetch_lead_config(conn)
    stored = cfg.get("scoring_rules")
    if isinstance(stored, list) and stored:
        return merge_scoring_rules(stored)
    return merge_scoring_rules(None)


def _text_blob(
    *,
    need: str,
    product_interest: str,
    meta: dict[str, Any] | None,
    activities: list[dict[str, Any]] | None,
) -> str:
    parts = [str(need or ""), str(product_interest or "")]
    if isinstance(meta, dict):
        for key in ("message", "note", "form_data", "raw_text", "comment"):
            val = meta.get(key)
            if val:
                parts.append(str(val))
    for act in activities or []:
        parts.append(str(act.get("content") or ""))
        parts.append(str(act.get("result") or ""))
    return " ".join(parts)


def _non_system_activity_count(activities: list[dict[str, Any]] | None) -> int:
    n = 0
    for act in activities or []:
        if str(act.get("activity_type") or "").lower() != "system":
            n += 1
    return n


def _no_response_count(activities: list[dict[str, Any]] | None) -> int:
    n = 0
    for act in activities or []:
        if str(act.get("activity_type") or "").lower() == "system":
            continue
        blob = f"{act.get('result') or ''} {act.get('content') or ''}"
        if _contains_any(blob, _NO_RESPONSE):
            n += 1
    return n


def _field_value(field: str, *, full_name: str, phone: str, email: str, need: str, product_interest: str, region: str) -> str:
    mapping = {
        "need": need,
        "product_interest": product_interest,
        "region": region,
        "phone": phone,
        "email": email,
        "full_name": full_name,
    }
    return str(mapping.get(field, need) or "")


def _evaluate_rule(
    rule: dict[str, Any],
    *,
    source: str,
    phone: str,
    email: str,
    need: str,
    product_interest: str,
    region: str,
    full_name: str,
    meta: dict[str, Any] | None,
    activities: list[dict[str, Any]] | None,
    activity_count: int,
) -> bool:
    from crm_lead_store import lead_needs_cleanup, normalize_email, normalize_phone, normalize_source

    cond = str(rule.get("condition") or rule.get("id") or "").strip()
    blob = _text_blob(need=need, product_interest=product_interest, meta=meta, activities=activities)
    src = normalize_source(source)
    ph = normalize_phone(phone)
    em = normalize_email(email)
    need_s = str(need or "").strip()
    prod_s = str(product_interest or "").strip()
    non_sys = _non_system_activity_count(activities)
    if activities is None and activity_count:
        non_sys = max(non_sys, int(activity_count))
    keywords = _parse_keywords(rule.get("keywords"))
    min_count = max(1, int(rule.get("min_count") or 2))

    if cond == "keyword":
        if not keywords:
            return False
        folded_blob = _fold(blob)
        return any(_fold(kw) in folded_blob for kw in keywords)
    if cond == "source_is":
        target = str(rule.get("source") or "").strip()
        return bool(target) and src == normalize_source(target)
    if cond == "field_has_text":
        field = str(rule.get("field") or "need")
        val = _field_value(
            field,
            full_name=full_name,
            phone=phone,
            email=email,
            need=need_s,
            product_interest=prod_s,
            region=str(region or ""),
        )
        return len(val.strip()) >= min_count
    if cond == "min_activities":
        return non_sys >= min_count
    if cond == "meta_flag":
        key = str(rule.get("meta_key") or "spam").strip()
        return bool(isinstance(meta, dict) and meta.get(key))

    if cond == "valid_phone":
        from crm_lead_store import is_valid_phone_format

        return is_valid_phone_format(phone)
    if cond == "valid_email":
        from crm_lead_store import is_valid_email_format

        return is_valid_email_format(email)
    if cond == "ask_price":
        return _contains_any(blob, _ASK_PRICE)
    if cond == "request_demo":
        return _contains_any(blob, _REQUEST_DEMO)
    if cond == "clear_need":
        return len(need_s) >= 12 or (len(need_s) >= 6 and bool(prod_s))
    if cond == "buy_soon":
        return _contains_any(blob, _BUY_SOON)
    if cond == "high_interaction":
        return non_sys >= 2
    if cond == "referral_source":
        return src == "referral"
    if cond == "no_response_3x":
        return _no_response_count(activities) >= 3
    if cond == "missing_data":
        needs_clean, _ = lead_needs_cleanup(
            full_name=full_name,
            phone=phone,
            email=email,
            need=need,
            product_interest=product_interest,
        )
        return needs_clean
    if cond == "spam":
        if isinstance(meta, dict) and meta.get("spam"):
            return True
        return _contains_any(blob, _SPAM)
    return False


def fetch_scoring_rubric(conn: Any | None) -> dict[str, Any]:
    if conn is None:
        from crm_lead_scoring_rubric import default_scoring_rubric

        return default_scoring_rubric()
    from crm_lead_rules import fetch_lead_config
    from crm_lead_scoring_rubric import merge_scoring_rubric

    cfg = fetch_lead_config(conn)
    stored = cfg.get("scoring_rubric")
    if isinstance(stored, dict):
        return merge_scoring_rubric(stored)
    return merge_scoring_rubric(None)


def _uses_legacy_flat_rules(conn: Any | None) -> bool:
    if conn is None:
        return False
    from crm_lead_rules import fetch_lead_config

    cfg = fetch_lead_config(conn)
    stored = cfg.get("scoring_rules")
    return isinstance(stored, list) and len(stored) > 0 and cfg.get("scoring_mode") == "legacy_rules"


def _score_lead_flat_rules(
    active_rules: list[dict[str, Any]],
    *,
    source: str,
    phone: str,
    email: str,
    need: str,
    product_interest: str,
    region: str,
    full_name: str,
    meta: dict[str, Any] | None,
    activities: list[dict[str, Any]] | None,
    activity_count: int,
) -> dict[str, Any]:
    breakdown: list[dict[str, Any]] = []
    total = 0
    for rule in active_rules:
        if not rule.get("enabled", True):
            continue
        matched = _evaluate_rule(
            rule,
            source=source,
            phone=phone,
            email=email,
            need=need,
            product_interest=product_interest,
            region=region,
            full_name=full_name,
            meta=meta,
            activities=activities,
            activity_count=activity_count,
        )
        pts = int(rule.get("points") or 0)
        delta = pts if matched else 0
        total += delta
        breakdown.append(
            {
                "id": str(rule.get("id") or ""),
                "label": str(rule.get("label") or ""),
                "points": pts,
                "applied": matched,
                "delta": delta,
            }
        )
    score = max(0, min(100, total))
    return {"score": score, "raw_total": total, "breakdown": breakdown, "rubric": False}


def score_lead(
    conn: Any | None,
    *,
    source: str,
    phone: str = "",
    email: str = "",
    need: str = "",
    product_interest: str = "",
    region: str = "",
    full_name: str = "",
    meta: dict[str, Any] | None = None,
    activities: list[dict[str, Any]] | None = None,
    activity_count: int = 0,
    rules: list[dict[str, Any]] | None = None,
    rubric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Chấm điểm lead (0–100) theo rubric D1–D6 hoặc rule phẳng (legacy)."""
    if rules is not None:
        return _score_lead_flat_rules(
            rules,
            source=source,
            phone=phone,
            email=email,
            need=need,
            product_interest=product_interest,
            region=region,
            full_name=full_name,
            meta=meta,
            activities=activities,
            activity_count=activity_count,
        )
    if conn is not None and _uses_legacy_flat_rules(conn):
        active_rules = fetch_scoring_rules(conn)
        return _score_lead_flat_rules(
            active_rules,
            source=source,
            phone=phone,
            email=email,
            need=need,
            product_interest=product_interest,
            region=region,
            full_name=full_name,
            meta=meta,
            activities=activities,
            activity_count=activity_count,
        )
    from crm_lead_scoring_rubric import score_lead_rubric

    active_rubric = rubric if rubric is not None else fetch_scoring_rubric(conn)
    ctx = {
        "source": source,
        "phone": phone,
        "email": email,
        "need": need,
        "product_interest": product_interest,
        "region": region,
        "full_name": full_name,
        "meta": meta,
        "activities": activities,
        "activity_count": activity_count,
    }
    return score_lead_rubric(active_rubric, ctx)
