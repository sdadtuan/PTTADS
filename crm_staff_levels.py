"""Hệ thống phân cấp nhân viên kinh doanh — Level S / A / B / C."""
from __future__ import annotations

from typing import Any

STAFF_LEVEL_IDS: frozenset[str] = frozenset({"s", "a", "b", "c"})

DEFAULT_STAFF_LEVELS: list[dict[str, Any]] = [
    {
        "id": "s",
        "code": "S",
        "label": "CHUYÊN GIA",
        "emoji": "💎",
        "experience": "> 3 năm kinh nghiệm",
        "quantitative": [
            "Tỷ lệ chốt: > 30% trong 3 tháng liên tiếp",
            "Doanh số: Top 20% toàn team",
            "Tốc độ phản hồi TB: < 3 phút",
            "Tỷ lệ bỏ sót lead: < 2%",
            "Điểm KH: > 9.0/10",
            "Referral từ KH cũ: > 3/tháng",
        ],
        "skills": [
            "Đàm phán deal lớn (> 5 tỷ)",
            "Xử lý objection phức tạp",
            "Tư vấn đầu tư, phân tích ROI",
            "Quản lý mối quan hệ KH VIP",
            "Hiểu sâu pháp lý BĐS",
            "Kỹ năng thuyết trình chuyên nghiệp",
        ],
        "suitable_leads": [
            "Hot lead VIP (ngân sách > 5 tỷ)",
            "Khách nước ngoài/Việt kiều",
            "Deal mua nhiều căn (đầu tư)",
            "Khách khó tính từng từ chối NV khác",
            "Lead từ referral đối tác chiến lược",
            "Lead từ CEO/doanh nhân cấp cao",
        ],
        "max_leads_min": 10,
        "max_leads_max": 15,
        "priority_note": "Ưu tiên nhận: HOT + VIP trước tiên",
        "enabled": True,
        "sort_order": 1,
    },
    {
        "id": "a",
        "code": "A",
        "label": "SENIOR",
        "emoji": "🥇",
        "experience": "1–3 năm kinh nghiệm",
        "quantitative": [
            "Tỷ lệ chốt: 15–30%",
            "Doanh số: Đạt và vượt KPI đều đặn",
            "Tốc độ phản hồi TB: < 5 phút",
            "Tỷ lệ bỏ sót lead: < 5%",
            "Điểm KH: 8.0–9.0/10",
            "Referral từ KH cũ: 1–3/tháng",
        ],
        "skills": [
            "Tư vấn đa dạng sản phẩm",
            "Xử lý được hầu hết objection",
            "Tính toán tài chính, hỗ trợ vay",
            "Dẫn dắt buổi xem thực tế chuyên nghiệp",
            "Chăm sóc KH sau bán ổn định",
        ],
        "suitable_leads": [
            "Hot lead thường (ngân sách 2–5 tỷ)",
            "Warm lead chất lượng cao",
            "Khách đầu tư vừa",
            "Khách mua lần 2 trở lên",
        ],
        "max_leads_min": 8,
        "max_leads_max": 12,
        "priority_note": "",
        "enabled": True,
        "sort_order": 2,
    },
    {
        "id": "b",
        "code": "B",
        "label": "MIDDLE",
        "emoji": "🥈",
        "experience": "6–12 tháng kinh nghiệm",
        "quantitative": [
            "Tỷ lệ chốt: 8–15%",
            "Doanh số: Đôi khi đạt KPI",
            "Tốc độ phản hồi TB: < 10 phút",
            "Tỷ lệ bỏ sót lead: < 10%",
            "Điểm KH: 7.0–8.0/10",
            "Referral từ KH cũ: 0–1/tháng",
        ],
        "skills": [
            "Tư vấn sản phẩm cơ bản tốt",
            "Xử lý objection phổ biến",
            "Cần hỗ trợ với KH khó",
            "Đang xây dựng portfolio KH",
        ],
        "suitable_leads": [
            "Warm lead thường",
            "Hot lead đơn giản (< 2 tỷ, KH dễ tính)",
            "Khách mua ở lần đầu có thời gian",
        ],
        "max_leads_min": 5,
        "max_leads_max": 8,
        "priority_note": "",
        "enabled": True,
        "sort_order": 3,
    },
    {
        "id": "c",
        "code": "C",
        "label": "JUNIOR",
        "emoji": "🥉",
        "experience": "< 6 tháng kinh nghiệm",
        "quantitative": [
            "Tỷ lệ chốt: < 8%",
            "Doanh số: Chưa ổn định",
            "Tốc độ phản hồi TB: < 15 phút",
            "Tỷ lệ bỏ sót lead: < 20%",
            "Điểm KH: < 7.0/10",
            "Referral từ KH cũ: Chưa có",
        ],
        "skills": [
            "Nắm kiến thức sản phẩm cơ bản",
            "Script tư vấn theo mẫu",
            "Cần kèm cặp thường xuyên",
            "Đang học cách xử lý lead",
        ],
        "suitable_leads": [
            "Cold lead (học cách tiếp cận)",
            "Warm lead đơn giản, KH không vội",
            "Lead nurturing dài hạn",
        ],
        "max_leads_min": 3,
        "max_leads_max": 5,
        "priority_note": "",
        "enabled": True,
        "sort_order": 4,
    },
]


def _default_by_id() -> dict[str, dict[str, Any]]:
    return {str(d["id"]): dict(d) for d in DEFAULT_STAFF_LEVELS}


def _normalize_str_list(raw: Any, *, max_items: int = 30, max_len: int = 500) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        lines = [ln.strip() for ln in raw.replace("\r", "").split("\n")]
    elif isinstance(raw, list):
        lines = [str(x).strip() for x in raw]
    else:
        raise ValueError("Danh sách tiêu chí phải là mảng hoặc chuỗi.")
    out: list[str] = []
    for ln in lines:
        if not ln:
            continue
        out.append(ln[:max_len])
        if len(out) >= max_items:
            break
    return out


def _normalize_level_item(item: dict[str, Any], *, fallback: dict[str, Any]) -> dict[str, Any]:
    lid = str(item.get("id") or fallback.get("id") or "").strip().lower()
    if lid not in STAFF_LEVEL_IDS:
        raise ValueError(f"Mã cấp bậc «{lid or '?'}» không hợp lệ (s, a, b, c).")
    label = str(item.get("label") or fallback.get("label") or "").strip()
    if not label:
        raise ValueError(f"Cấp {lid.upper()} phải có tên.")
    code = str(item.get("code") or fallback.get("code") or lid.upper()).strip().upper()[:4]
    emoji = str(item.get("emoji") or fallback.get("emoji") or "").strip()[:8]
    experience = str(item.get("experience") or fallback.get("experience") or "").strip()[:200]
    try:
        max_leads_min = int(item.get("max_leads_min", fallback.get("max_leads_min", 0)))
        max_leads_max = int(item.get("max_leads_max", fallback.get("max_leads_max", 0)))
    except (TypeError, ValueError):
        raise ValueError(f"Cấp {code}: số lead tối đa/ngày không hợp lệ.")
    max_leads_min = max(0, min(100, max_leads_min))
    max_leads_max = max(0, min(100, max_leads_max))
    if max_leads_min > max_leads_max:
        raise ValueError(f"Cấp {code}: lead tối thiểu/ngày phải ≤ tối đa.")
    try:
        sort_order = int(item.get("sort_order", fallback.get("sort_order", 99)))
    except (TypeError, ValueError):
        sort_order = int(fallback.get("sort_order") or 99)
    return {
        "id": lid,
        "code": code,
        "label": label[:80],
        "emoji": emoji,
        "experience": experience,
        "quantitative": _normalize_str_list(
            item.get("quantitative", fallback.get("quantitative"))
        ),
        "skills": _normalize_str_list(item.get("skills", fallback.get("skills"))),
        "suitable_leads": _normalize_str_list(
            item.get("suitable_leads", fallback.get("suitable_leads"))
        ),
        "max_leads_min": max_leads_min,
        "max_leads_max": max_leads_max,
        "priority_note": str(item.get("priority_note") or fallback.get("priority_note") or "").strip()[
            :500
        ],
        "enabled": bool(item.get("enabled", fallback.get("enabled", True))),
        "sort_order": sort_order,
    }


def normalize_staff_levels(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("staff_levels phải là mảng.")
    defaults = _default_by_id()
    by_id: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        lid = str(item.get("id") or "").strip().lower()
        if lid not in STAFF_LEVEL_IDS:
            continue
        by_id[lid] = _normalize_level_item(item, fallback=defaults[lid])
    if not by_id:
        return [dict(d) for d in DEFAULT_STAFF_LEVELS]
    out: list[dict[str, Any]] = []
    for lid in ("s", "a", "b", "c"):
        if lid in by_id:
            out.append(by_id[lid])
        else:
            out.append(dict(defaults[lid]))
    out.sort(key=lambda x: int(x.get("sort_order") or 99))
    return out


def merge_staff_levels(raw: list[Any] | None) -> list[dict[str, Any]]:
    if not raw or not isinstance(raw, list):
        return [dict(d) for d in DEFAULT_STAFF_LEVELS]
    try:
        return normalize_staff_levels(raw)
    except ValueError:
        return [dict(d) for d in DEFAULT_STAFF_LEVELS]


def staff_level_labels_map(levels: list[dict[str, Any]] | None = None) -> dict[str, str]:
    active = levels if levels is not None else DEFAULT_STAFF_LEVELS
    out: dict[str, str] = {}
    for lv in active:
        lid = str(lv.get("id") or "").strip().lower()
        if not lid:
            continue
        code = str(lv.get("code") or lid.upper()).strip()
        label = str(lv.get("label") or "").strip()
        emoji = str(lv.get("emoji") or "").strip()
        prefix = f"{emoji} " if emoji else ""
        out[lid] = f"{prefix}Level {code} — {label}" if label else f"{prefix}Level {code}"
    return out


def normalize_sales_level(raw: Any) -> str:
    val = str(raw or "").strip().lower()
    if not val:
        return ""
    if val in STAFF_LEVEL_IDS:
        return val
    raise ValueError("Cấp bậc kinh doanh không hợp lệ (S, A, B, C hoặc để trống).")
