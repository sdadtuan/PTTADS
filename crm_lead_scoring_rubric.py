"""Rubric chấm điểm lead D1–D6 (100 điểm) — phân bổ theo nhóm tiêu chí."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")

EVALUATOR_OPTIONS: list[dict[str, str]] = [
    {"id": "info_completeness", "label": "D1.1 — Mức độ đầy đủ thông tin"},
    {"id": "web_behavior", "label": "D1.2 — Hành vi trên website"},
    {"id": "site_time_minutes", "label": "D1.3 — Thời gian trên website (phút)"},
    {"id": "budget_decl_quality", "label": "D2.1 — Ngân sách được khai báo"},
    {"id": "budget_vs_price_pct", "label": "D2.2 — Ngân sách so với giá dự án (%)"},
    {"id": "purchase_timeline", "label": "D3.1 — Thời gian dự kiến mua"},
    {"id": "urgency_reason", "label": "D3.2 — Lý do tạo cấp thiết"},
    {"id": "lead_source", "label": "D4 — Nguồn lead"},
    {"id": "interaction_count", "label": "D5.1 — Lần tương tác"},
    {"id": "last_interaction_type", "label": "D5.2 — Loại tương tác gần nhất"},
    {"id": "age_years", "label": "D6.1 — Độ tuổi"},
    {"id": "occupation_tier", "label": "D6.2 — Nghề nghiệp / Thu nhập"},
]

VALID_EVALUATORS: frozenset[str] = frozenset(e["id"] for e in EVALUATOR_OPTIONS)


def _slug_id(prefix: str, label: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", str(label or "").strip().lower()).strip("_")
    if raw and _ID_RE.match(raw):
        return raw[:48]
    return f"{prefix}_{abs(hash(label)) % 100000}"


def _band(
    label: str,
    points: int,
    *,
    band_id: str = "",
    min_value: float | None = None,
    max_value: float | None = None,
    min_exclusive: bool = False,
    max_exclusive: bool = False,
    tier_value: int | None = None,
    match_sources: list[str] | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": band_id or _slug_id("band", label),
        "label": label[:120],
        "points": max(0, min(100, int(points))),
        "min_value": min_value,
        "max_value": max_value,
        "min_exclusive": bool(min_exclusive),
        "max_exclusive": bool(max_exclusive),
        "tier_value": tier_value,
        "match_sources": [str(s).strip().lower() for s in (match_sources or []) if str(s).strip()],
        "keywords": [str(k).strip() for k in (keywords or []) if str(k).strip()],
    }


def _crit(
    cid: str,
    code: str,
    label: str,
    max_points: int,
    evaluator: str,
    bands: list[dict[str, Any]],
    *,
    sort_order: int = 0,
) -> dict[str, Any]:
    return {
        "id": cid,
        "code": code[:16],
        "label": label[:200],
        "max_points": max(0, min(100, int(max_points))),
        "evaluator": evaluator if evaluator in VALID_EVALUATORS else "info_completeness",
        "enabled": True,
        "sort_order": sort_order,
        "bands": bands,
    }


DEFAULT_LEAD_SCORING_RUBRIC: dict[str, Any] = {
    "groups": [
        {
            "id": "group_d1",
            "code": "D1",
            "label": "THÔNG TIN & HÀNH VI",
            "max_points": 25,
            "sort_order": 1,
            "criteria": [
                _crit(
                    "d1_1_info",
                    "D1.1",
                    "Mức độ đầy đủ thông tin",
                    10,
                    "info_completeness",
                    [
                        _band("Có SĐT + Tên + Email + Ngân sách + SP", 10, tier_value=6, band_id="d1_1_t6"),
                        _band("Có SĐT + Tên + Email + Ngân sách", 8, tier_value=5, band_id="d1_1_t5"),
                        _band("Có SĐT + Tên + Email", 6, tier_value=4, band_id="d1_1_t4"),
                        _band("Có SĐT + Tên + Ngân sách", 5, tier_value=3, band_id="d1_1_t3"),
                        _band("Có SĐT + Tên", 3, tier_value=2, band_id="d1_1_t2"),
                        _band("Chỉ có SĐT", 1, tier_value=1, band_id="d1_1_t1"),
                    ],
                    sort_order=1,
                ),
                _crit(
                    "d1_2_web",
                    "D1.2",
                    "Hành vi trên website",
                    10,
                    "web_behavior",
                    [
                        _band("Xem bảng giá + Xem tầng căn hộ", 10, tier_value=6, band_id="d1_2_t6"),
                        _band("Xem bảng giá", 8, tier_value=5, band_id="d1_2_t5"),
                        _band("Xem video dự án > 50%", 7, tier_value=4, band_id="d1_2_t4"),
                        _band("Xem trang dự án > 3 lần", 6, tier_value=3, band_id="d1_2_t3"),
                        _band("Xem trang dự án 1–2 lần", 4, tier_value=2, band_id="d1_2_t2"),
                        _band("Chỉ vào trang chủ", 2, tier_value=1, band_id="d1_2_t1"),
                        _band("Không có data hành vi", 0, tier_value=0, band_id="d1_2_t0"),
                    ],
                    sort_order=2,
                ),
                _crit(
                    "d1_3_time",
                    "D1.3",
                    "Thời gian trên website",
                    5,
                    "site_time_minutes",
                    [
                        _band("> 10 phút", 5, min_value=10, min_exclusive=True, band_id="d1_3_b5"),
                        _band("5–10 phút", 4, min_value=5, max_value=10, band_id="d1_3_b4"),
                        _band("3–5 phút", 3, min_value=3, max_value=5, band_id="d1_3_b3"),
                        _band("1–3 phút", 2, min_value=1, max_value=3, band_id="d1_3_b2"),
                        _band("< 1 phút", 0, max_value=1, max_exclusive=True, band_id="d1_3_b1"),
                    ],
                    sort_order=3,
                ),
            ],
        },
        {
            "id": "group_d2",
            "code": "D2",
            "label": "KHẢ NĂNG TÀI CHÍNH",
            "max_points": 20,
            "sort_order": 2,
            "criteria": [
                _crit(
                    "d2_1_budget",
                    "D2.1",
                    "Ngân sách được khai báo",
                    12,
                    "budget_decl_quality",
                    [
                        _band('Khai báo số tiền cụ thể (VD: "3.5 tỷ")', 12, tier_value=4, band_id="d2_1_t4"),
                        _band('Khai báo khoảng (VD: "3–4 tỷ")', 10, tier_value=3, band_id="d2_1_t3"),
                        _band('Khai báo chung (VD: "tầm 3 tỷ")', 7, tier_value=2, band_id="d2_1_t2"),
                        _band('Khai báo rất chung (VD: "vài tỷ")', 4, tier_value=1, band_id="d2_1_t1"),
                        _band("Không khai báo", 0, tier_value=0, band_id="d2_1_t0"),
                    ],
                    sort_order=1,
                ),
                _crit(
                    "d2_2_budget_price",
                    "D2.2",
                    "Mức ngân sách so với giá dự án",
                    8,
                    "budget_vs_price_pct",
                    [
                        _band("Ngân sách = Giá dự án (phù hợp 100%)", 8, min_value=95, max_value=105, band_id="d2_2_b6"),
                        _band("Ngân sách > Giá (dư dả)", 8, min_value=105, min_exclusive=True, band_id="d2_2_b5"),
                        _band("Ngân sách = 80–100% Giá", 6, min_value=80, max_value=100, band_id="d2_2_b4"),
                        _band("Ngân sách = 60–80% Giá", 4, min_value=60, max_value=80, band_id="d2_2_b3"),
                        _band("Ngân sách = 40–60% Giá", 2, min_value=40, max_value=60, band_id="d2_2_b2"),
                        _band("Ngân sách < 40% Giá", 0, max_value=40, max_exclusive=True, band_id="d2_2_b1"),
                    ],
                    sort_order=2,
                ),
            ],
        },
        {
            "id": "group_d3",
            "code": "D3",
            "label": "TIMELINE & ĐỘ CẤP THIẾT",
            "max_points": 20,
            "sort_order": 3,
            "criteria": [
                _crit(
                    "d3_1_timeline",
                    "D3.1",
                    "Thời gian dự kiến mua",
                    12,
                    "purchase_timeline",
                    [
                        _band("Muốn mua ngay / tuần này", 12, tier_value=5, band_id="d3_1_t5"),
                        _band("Trong tháng này", 10, tier_value=4, band_id="d3_1_t4"),
                        _band("1–3 tháng tới", 8, tier_value=3, band_id="d3_1_t3"),
                        _band("3–6 tháng tới", 5, tier_value=2, band_id="d3_1_t2"),
                        _band("6–12 tháng tới", 2, tier_value=1, band_id="d3_1_t1"),
                        _band("Chưa xác định / Chỉ tìm hiểu", 0, tier_value=0, band_id="d3_1_t0"),
                    ],
                    sort_order=1,
                ),
                _crit(
                    "d3_2_urgency",
                    "D3.2",
                    "Lý do tạo cấp thiết",
                    8,
                    "urgency_reason",
                    [
                        _band("Sắp kết hôn / sinh con", 8, tier_value=8, band_id="d3_2_t8"),
                        _band("Đã bán nhà cũ, cần mua gấp", 8, tier_value=7, band_id="d3_2_t7"),
                        _band("Hết hợp đồng thuê nhà", 7, tier_value=6, band_id="d3_2_t6"),
                        _band("Muốn đầu tư trước khi tăng giá", 6, tier_value=5, band_id="d3_2_t5"),
                        _band("Con chuẩn bị vào cấp 1 (gần trường)", 6, tier_value=4, band_id="d3_2_t4"),
                        _band("Về hưu, muốn an cư", 5, tier_value=3, band_id="d3_2_t3"),
                        _band("Không có lý do cụ thể", 0, tier_value=0, band_id="d3_2_t0"),
                    ],
                    sort_order=2,
                ),
            ],
        },
        {
            "id": "group_d4",
            "code": "D4",
            "label": "NGUỒN LEAD",
            "max_points": 15,
            "sort_order": 4,
            "criteria": [
                _crit(
                    "d4_source",
                    "D4",
                    "Nguồn lead",
                    15,
                    "lead_source",
                    [
                        _band("Referral từ KH đã mua", 15, match_sources=["referral", "customer_referral"], band_id="d4_s15"),
                        _band("Đối tác giới thiệu", 14, match_sources=["partner", "partner_referral"], band_id="d4_s14"),
                        _band("Walk-in (showroom)", 14, match_sources=["walk_in", "showroom"], band_id="d4_s14b"),
                        _band("Google Search Ads", 12, match_sources=["google_search", "google_ads_search"], band_id="d4_s12a"),
                        _band("Sự kiện / Hội thảo", 12, match_sources=["event", "seminar"], band_id="d4_s12b"),
                        _band("SEO / Blog", 11, match_sources=["seo", "organic", "website_organic"], band_id="d4_s11"),
                        _band("Google Display Ads", 9, match_sources=["google_display", "google_ads_display"], band_id="d4_s9a"),
                        _band("Facebook Messenger", 9, match_sources=["facebook_messenger", "fb_messenger"], band_id="d4_s9b"),
                        _band("Zalo OA nhắn tin", 9, match_sources=["zalo_oa", "zalo_chat"], band_id="d4_s9c"),
                        _band("Facebook Lead Ads", 7, match_sources=["facebook", "facebook_lead_ads", "fb_leads"], band_id="d4_s7a"),
                        _band("Zalo Ads", 7, match_sources=["zalo", "zalo_ads"], band_id="d4_s7b"),
                        _band("YouTube Ads", 6, match_sources=["youtube", "youtube_ads"], band_id="d4_s6"),
                        _band("TikTok Ads", 5, match_sources=["tiktok", "tiktok_ads"], band_id="d4_s5"),
                        _band("Email Marketing", 5, match_sources=["email", "email_marketing"], band_id="d4_s5b"),
                        _band("Telesale gọi ra", 4, match_sources=["telesale", "outbound_call"], band_id="d4_s4"),
                        _band("Database cũ / Không rõ", 2, match_sources=["import", "database", "other", "manual", "api"], band_id="d4_s2"),
                    ],
                    sort_order=1,
                ),
            ],
        },
        {
            "id": "group_d5",
            "code": "D5",
            "label": "MỨC ĐỘ TƯƠNG TÁC",
            "max_points": 12,
            "sort_order": 5,
            "criteria": [
                _crit(
                    "d5_1_interactions",
                    "D5.1",
                    "Lần tương tác",
                    6,
                    "interaction_count",
                    [
                        _band("> 5 lần", 6, min_value=5, min_exclusive=True, band_id="d5_1_b3"),
                        _band("3–5 lần", 4, min_value=3, max_value=5, band_id="d5_1_b2"),
                        _band("1–2 lần", 2, min_value=1, max_value=2, band_id="d5_1_b1"),
                        _band("Lần đầu tiên", 0, max_value=1, max_exclusive=True, band_id="d5_1_b0"),
                    ],
                    sort_order=1,
                ),
                _crit(
                    "d5_2_last_interaction",
                    "D5.2",
                    "Loại tương tác gần nhất",
                    6,
                    "last_interaction_type",
                    [
                        _band("Gọi điện đến hotline", 6, tier_value=6, band_id="d5_2_t6"),
                        _band("Chat trực tiếp với NV", 5, tier_value=5, band_id="d5_2_t5"),
                        _band("Điền form đăng ký chi tiết", 5, tier_value=4, band_id="d5_2_t4"),
                        _band("Click quảng cáo nhiều lần", 4, tier_value=3, band_id="d5_2_t3"),
                        _band("Mở email và click link", 3, tier_value=2, band_id="d5_2_t2"),
                        _band("Like / Comment bài đăng", 2, tier_value=1, band_id="d5_2_t1"),
                        _band("Chỉ xem, không tương tác", 0, tier_value=0, band_id="d5_2_t0"),
                    ],
                    sort_order=2,
                ),
            ],
        },
        {
            "id": "group_d6",
            "code": "D6",
            "label": "ĐẶC ĐIỂM NHÂN KHẨU",
            "max_points": 8,
            "sort_order": 6,
            "criteria": [
                _crit(
                    "d6_1_age",
                    "D6.1",
                    "Độ tuổi phù hợp phân khúc",
                    4,
                    "age_years",
                    [
                        _band("30–45 tuổi", 4, min_value=30, max_value=45, band_id="d6_1_b4"),
                        _band("25–30 tuổi", 3, min_value=25, max_value=30, band_id="d6_1_b3"),
                        _band("45–55 tuổi", 3, min_value=45, max_value=55, band_id="d6_1_b3b"),
                        _band("55–65 tuổi", 2, min_value=55, max_value=65, band_id="d6_1_b2"),
                        _band("< 25 hoặc > 65 tuổi", 1, band_id="d6_1_b1"),
                    ],
                    sort_order=1,
                ),
                _crit(
                    "d6_2_occupation",
                    "D6.2",
                    "Nghề nghiệp / Thu nhập",
                    4,
                    "occupation_tier",
                    [
                        _band("Doanh nhân / Giám đốc", 4, tier_value=5, band_id="d6_2_t5"),
                        _band("Chuyên gia cao cấp / Bác sĩ / Luật sư", 4, tier_value=4, band_id="d6_2_t4"),
                        _band("Nhân viên văn phòng thu nhập cao", 3, tier_value=3, band_id="d6_2_t3"),
                        _band("Kinh doanh tự do", 3, tier_value=2, band_id="d6_2_t2"),
                        _band("Công chức / Viên chức", 2, tier_value=1, band_id="d6_2_t1"),
                        _band("Không rõ nghề nghiệp", 1, tier_value=0, band_id="d6_2_t0"),
                    ],
                    sort_order=2,
                ),
            ],
        },
    ],
}


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")


def _contains_any(text: str, keywords: tuple[str, ...] | list[str]) -> bool:
    folded = _fold(text)
    return any(_fold(kw) in folded for kw in keywords)


def _parse_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _normalize_band(item: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    base = fallback or {}
    label = str(item.get("label") or base.get("label") or "").strip()
    if not label:
        raise ValueError("Mức điểm phải có nhãn.")
    try:
        points = int(item.get("points", base.get("points", 0)))
    except (TypeError, ValueError):
        raise ValueError(f"Điểm mức «{label}» không hợp lệ.")
    rid = str(item.get("id") or base.get("id") or "").strip().lower()
    if not rid:
        rid = _slug_id("band", label)
    if not _ID_RE.match(rid):
        raise ValueError(f"Mã mức «{rid}» không hợp lệ.")
    tier_raw = item.get("tier_value", base.get("tier_value"))
    tier_value = None if tier_raw is None or tier_raw == "" else int(tier_raw)
    ms = item.get("match_sources", base.get("match_sources", []))
    if isinstance(ms, str):
        ms = [x.strip() for x in ms.replace(";", ",").split(",") if x.strip()]
    elif not isinstance(ms, list):
        ms = []
    kw = item.get("keywords", base.get("keywords", []))
    if isinstance(kw, str):
        kw = [x.strip() for x in kw.replace(";", ",").split(",") if x.strip()]
    elif not isinstance(kw, list):
        kw = []
    return {
        "id": rid[:48],
        "label": label[:120],
        "points": max(0, min(100, points)),
        "min_value": _parse_float(item.get("min_value", base.get("min_value"))),
        "max_value": _parse_float(item.get("max_value", base.get("max_value"))),
        "min_exclusive": bool(item.get("min_exclusive", base.get("min_exclusive", False))),
        "max_exclusive": bool(item.get("max_exclusive", base.get("max_exclusive", False))),
        "tier_value": tier_value,
        "match_sources": [str(s).strip().lower()[:40] for s in ms if str(s).strip()],
        "keywords": [str(k).strip()[:80] for k in kw if str(k).strip()],
    }


def _normalize_criterion(
    item: dict[str, Any],
    *,
    fallback: dict[str, Any] | None,
    group_id: str,
) -> dict[str, Any]:
    base = fallback or {}
    label = str(item.get("label") or base.get("label") or "").strip()
    if not label:
        raise ValueError("Tiêu chí phải có tên.")
    rid = str(item.get("id") or base.get("id") or "").strip().lower()
    if not rid:
        rid = _slug_id("crit", label)
    if not _ID_RE.match(rid):
        raise ValueError(f"Mã tiêu chí «{rid}» không hợp lệ.")
    evaluator = str(item.get("evaluator") or base.get("evaluator") or "").strip()
    if evaluator not in VALID_EVALUATORS:
        raise ValueError(f"Evaluator «{evaluator}» không hợp lệ.")
    try:
        max_points = int(item.get("max_points", base.get("max_points", 0)))
    except (TypeError, ValueError):
        raise ValueError(f"Tiêu chí «{label}»: điểm tối đa không hợp lệ.")
    try:
        sort_order = int(item.get("sort_order", base.get("sort_order", 99)))
    except (TypeError, ValueError):
        sort_order = 99
    raw_bands = item.get("bands", base.get("bands"))
    if not isinstance(raw_bands, list) or not raw_bands:
        raise ValueError(f"Tiêu chí «{label}» cần ít nhất một mức điểm.")
    bands: list[dict[str, Any]] = []
    seen: set[str] = set()
    fb_bands = base.get("bands") if isinstance(base.get("bands"), list) else []
    for bi, b in enumerate(raw_bands):
        if not isinstance(b, dict):
            continue
        fb = fb_bands[bi] if bi < len(fb_bands) and isinstance(fb_bands[bi], dict) else None
        nb = _normalize_band(b, fallback=fb)
        if nb["id"] in seen:
            raise ValueError(f"Tiêu chí «{label}»: trùng mức {nb['id']}.")
        seen.add(nb["id"])
        bands.append(nb)
    if max(b["points"] for b in bands) > max_points:
        raise ValueError(f"Tiêu chí «{label}»: điểm mức vượt tối đa {max_points}.")
    return {
        "id": rid[:48],
        "group_id": group_id,
        "code": str(item.get("code") or base.get("code") or rid.upper()[:8]).strip()[:16],
        "label": label[:200],
        "max_points": max(0, min(100, max_points)),
        "evaluator": evaluator,
        "enabled": bool(item.get("enabled", base.get("enabled", True))),
        "sort_order": sort_order,
        "bands": bands,
    }


def _normalize_group(item: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    base = fallback or {}
    label = str(item.get("label") or base.get("label") or "").strip()
    if not label:
        raise ValueError("Nhóm phải có tên.")
    gid = str(item.get("id") or base.get("id") or "").strip().lower()
    if not gid:
        gid = _slug_id("group", label)
    if not _ID_RE.match(gid):
        raise ValueError(f"Mã nhóm «{gid}» không hợp lệ.")
    try:
        max_points = int(item.get("max_points", base.get("max_points", 0)))
    except (TypeError, ValueError):
        raise ValueError(f"Nhóm «{label}»: tổng điểm không hợp lệ.")
    try:
        sort_order = int(item.get("sort_order", base.get("sort_order", 99)))
    except (TypeError, ValueError):
        sort_order = 99
    raw_crit = item.get("criteria", base.get("criteria"))
    if not isinstance(raw_crit, list):
        raw_crit = []
    fb_map = {str(c["id"]): c for c in (base.get("criteria") or []) if isinstance(c, dict)}
    criteria: list[dict[str, Any]] = []
    seen_c: set[str] = set()
    for c in raw_crit:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip().lower()
        nc = _normalize_criterion(c, fallback=fb_map.get(cid), group_id=gid)
        if nc["id"] in seen_c:
            raise ValueError(f"Nhóm «{label}»: trùng tiêu chí {nc['id']}.")
        seen_c.add(nc["id"])
        criteria.append(nc)
    crit_sum = sum(int(c["max_points"]) for c in criteria if c.get("enabled", True))
    if criteria and crit_sum > max_points:
        raise ValueError(f"Nhóm «{label}»: tổng tiêu chí ({crit_sum}) vượt trần ({max_points}).")
    criteria.sort(key=lambda x: int(x.get("sort_order", 99)))
    return {
        "id": gid[:48],
        "code": str(item.get("code") or base.get("code") or gid.upper()[:8]).strip()[:8],
        "label": label[:120],
        "max_points": max(0, min(100, max_points)),
        "sort_order": sort_order,
        "criteria": criteria,
    }


def normalize_scoring_rubric(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("scoring_rubric phải là object.")
    defaults = {str(g["id"]): g for g in DEFAULT_LEAD_SCORING_RUBRIC["groups"]}
    raw_groups = raw.get("groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("Cần ít nhất một nhóm chấm điểm.")
    groups: list[dict[str, Any]] = []
    seen_g: set[str] = set()
    for g in raw_groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or "").strip().lower()
        ng = _normalize_group(g, fallback=defaults.get(gid))
        if ng["id"] in seen_g:
            raise ValueError(f"Trùng nhóm {ng['id']}.")
        seen_g.add(ng["id"])
        groups.append(ng)
    if not groups:
        raise ValueError("Cần ít nhất một nhóm chấm điểm.")
    groups.sort(key=lambda x: int(x.get("sort_order", 99)))
    return {"groups": groups}


def merge_scoring_rubric(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw or not isinstance(raw, dict):
        return default_scoring_rubric()
    try:
        return normalize_scoring_rubric(raw)
    except ValueError:
        return default_scoring_rubric()


def default_scoring_rubric() -> dict[str, Any]:
    import copy

    return copy.deepcopy(DEFAULT_LEAD_SCORING_RUBRIC)


def band_matches_numeric(value: float, band: dict[str, Any]) -> bool:
    mn = band.get("min_value")
    mx = band.get("max_value")
    if mn is not None:
        if band.get("min_exclusive"):
            if value <= float(mn):
                return False
        elif value < float(mn):
            return False
    if mx is not None:
        if band.get("max_exclusive"):
            if value >= float(mx):
                return False
        elif value > float(mx):
            return False
    return True


def score_bands_tier(tier: int, bands: list[dict[str, Any]]) -> int:
    for band in sorted(bands, key=lambda b: int(b.get("points", 0)), reverse=True):
        if band.get("tier_value") is not None and int(band["tier_value"]) == int(tier):
            return int(band.get("points") or 0)
    return 0


def score_bands_numeric(value: float, bands: list[dict[str, Any]]) -> int:
    ordered = sorted(bands, key=lambda b: int(b.get("points", 0)), reverse=True)
    for band in ordered:
        if band_matches_numeric(float(value), band):
            return int(band.get("points") or 0)
    # age fallback band without bounds
    for band in ordered:
        if band.get("min_value") is None and band.get("max_value") is None and band.get("tier_value") is None:
            if band.get("label") and ("< 25" in band["label"] or "> 65" in band["label"]):
                return int(band.get("points") or 0)
    return 0


def score_bands_source(source: str, bands: list[dict[str, Any]]) -> int:
    src = str(source or "").strip().lower()
    best = 0
    for band in bands:
        sources = band.get("match_sources") or []
        if src in sources and int(band.get("points") or 0) > best:
            best = int(band["points"])
    return best


def _meta_get(meta: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    if not isinstance(meta, dict):
        return default
    for k in keys:
        if k in meta and meta[k] not in (None, ""):
            return meta[k]
    return default


def _text_blob(ctx: dict[str, Any]) -> str:
    parts = [
        str(ctx.get("need") or ""),
        str(ctx.get("product_interest") or ""),
        str(ctx.get("full_name") or ""),
    ]
    meta = ctx.get("meta")
    if isinstance(meta, dict):
        for key in ("message", "note", "form_data", "raw_text", "comment", "budget_text"):
            val = meta.get(key)
            if val:
                parts.append(str(val))
    return " ".join(parts)


def _has_budget(ctx: dict[str, Any]) -> bool:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    if _meta_get(meta, "budget", "budget_vnd", "budget_text"):
        return True
    blob = _text_blob(ctx)
    return bool(re.search(r"\d+[\.,]?\d*\s*(ty|tỷ|trieu|triệu|billion|tỷ vnđ)", _fold(blob)))


def eval_info_completeness(ctx: dict[str, Any]) -> int:
    from crm_lead_store import is_valid_email_format, is_valid_phone_format, normalize_phone

    ph = normalize_phone(str(ctx.get("phone") or ""))
    has_phone = is_valid_phone_format(ph) or len(ph) >= 9
    has_name = len(str(ctx.get("full_name") or "").strip()) >= 2
    has_email = is_valid_email_format(str(ctx.get("email") or ""))
    has_product = len(str(ctx.get("product_interest") or "").strip()) >= 2
    has_budget = _has_budget(ctx)
    if has_phone and has_name and has_email and has_budget and has_product:
        return 6
    if has_phone and has_name and has_email and has_budget:
        return 5
    if has_phone and has_name and has_email:
        return 4
    if has_phone and has_name and has_budget:
        return 3
    if has_phone and has_name:
        return 2
    if has_phone:
        return 1
    return 0


def eval_web_behavior(ctx: dict[str, Any]) -> int:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    tier = _meta_get(meta, "web_behavior_tier", "behavior_tier")
    if tier is not None:
        try:
            return int(tier)
        except (TypeError, ValueError):
            pass
    viewed_price = bool(_meta_get(meta, "viewed_price_table", "viewed_pricing", default=False))
    viewed_floor = bool(_meta_get(meta, "viewed_floor_plan", "viewed_unit_plan", default=False))
    video_pct = _parse_float(_meta_get(meta, "video_watch_pct", "project_video_pct"))
    page_views = _parse_float(_meta_get(meta, "project_page_views", "project_views"))
    homepage_only = bool(_meta_get(meta, "homepage_only", default=False))
    if viewed_price and viewed_floor:
        return 6
    if viewed_price:
        return 5
    if video_pct is not None and video_pct > 50:
        return 4
    if page_views is not None and page_views > 3:
        return 3
    if page_views is not None and page_views >= 1:
        return 2
    if homepage_only:
        return 1
    return 0


def eval_site_time_minutes(ctx: dict[str, Any]) -> float:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    v = _parse_float(_meta_get(meta, "site_time_minutes", "session_minutes", "time_on_site_minutes"))
    return float(v or 0)


def eval_budget_decl_quality(ctx: dict[str, Any]) -> int:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    tier = _meta_get(meta, "budget_decl_tier")
    if tier is not None:
        try:
            return int(tier)
        except (TypeError, ValueError):
            pass
    text = str(_meta_get(meta, "budget_text", "budget") or "") + " " + _text_blob(ctx)
    folded = _fold(text)
    if not _has_budget(ctx):
        return 0
    if re.search(r"\d+[\.,]?\d*\s*[-–]\s*\d+[\.,]?\d*\s*(ty|tỷ)", folded):
        return 3
    if re.search(r"\d+[\.,]?\d*\s*(ty|tỷ)", folded):
        return 4
    if any(k in folded for k in ("tam", "tầm", "khoang", "khoảng")):
        return 2
    if any(k in folded for k in ("vai ty", "vài tỷ", "nhieu ty", "nhiều tỷ")):
        return 1
    return 2


def eval_budget_vs_price_pct(ctx: dict[str, Any]) -> float:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    pct = _parse_float(_meta_get(meta, "budget_vs_price_pct", "budget_price_ratio_pct"))
    if pct is not None:
        return float(pct)
    budget = _parse_float(_meta_get(meta, "budget_vnd", "budget_amount"))
    price = _parse_float(_meta_get(meta, "project_price_vnd", "unit_price_vnd", "listing_price_vnd"))
    if budget is not None and price and price > 0:
        return budget / price * 100.0
    return -1.0


def eval_purchase_timeline(ctx: dict[str, Any]) -> int:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    tier = _meta_get(meta, "purchase_timeline_tier")
    if tier is not None:
        try:
            return int(tier)
        except (TypeError, ValueError):
            pass
    blob = _text_blob(ctx)
    if _contains_any(blob, ("mua ngay", "ngay", "tuan nay", "tuần này", "gap", "gấp", "asap")):
        return 5
    if _contains_any(blob, ("trong thang", "trong tháng", "thang nay", "tháng này")):
        return 4
    if _contains_any(blob, ("1-3 thang", "1–3 tháng", "3 thang toi", "3 tháng tới")):
        return 3
    if _contains_any(blob, ("3-6 thang", "3–6 tháng", "6 thang", "6 tháng")):
        return 2
    if _contains_any(blob, ("6-12 thang", "6–12 tháng", "12 thang", "12 tháng")):
        return 1
    if _contains_any(blob, ("tim hieu", "tìm hiểu", "chua xac dinh", "chưa xác định")):
        return 0
    return 0


def eval_urgency_reason(ctx: dict[str, Any]) -> int:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    tier = _meta_get(meta, "urgency_reason_tier")
    if tier is not None:
        try:
            return int(tier)
        except (TypeError, ValueError):
            pass
    blob = _text_blob(ctx)
    checks = [
        (8, ("ket hon", "kết hôn", "sinh con", "mang thai")),
        (7, ("ban nha cu", "bán nhà cũ", "can mua gap", "cần mua gấp")),
        (6, ("het hop dong thue", "hết hợp đồng thuê", "het han thue", "hết hạn thuê")),
        (5, ("dau tu", "đầu tư", "tang gia", "tăng giá")),
        (4, ("cap 1", "cấp 1", "gan truong", "gần trường")),
        (3, ("ve huu", "về hưu", "an cu", "an cư")),
    ]
    for tier_val, kws in checks:
        if _contains_any(blob, kws):
            return tier_val
    return 0


def eval_lead_source(ctx: dict[str, Any]) -> str:
    from crm_lead_store import normalize_source

    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    detail = str(_meta_get(meta, "source_detail", "lead_channel", "utm_source") or "").strip().lower()
    if detail:
        return detail.replace(" ", "_")
    src = normalize_source(str(ctx.get("source") or ""))
    alias = {
        "website": "website_organic",
        "google_ads": "google_search",
        "facebook": "facebook_lead_ads",
        "zalo": "zalo_ads",
        "referral": "referral",
        "email": "email_marketing",
        "import": "database",
        "manual": "other",
        "api": "other",
        "other": "other",
    }
    return alias.get(src, src)


def eval_interaction_count(ctx: dict[str, Any]) -> float:
    acts = ctx.get("activities") or []
    n = 0
    for act in acts:
        if str(act.get("activity_type") or "").lower() != "system":
            n += 1
    if n == 0 and ctx.get("activity_count"):
        n = int(ctx["activity_count"])
    return float(n)


def eval_last_interaction_type(ctx: dict[str, Any]) -> int:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    tier = _meta_get(meta, "last_interaction_tier", "last_interaction_type")
    if tier is not None:
        try:
            return int(tier)
        except (TypeError, ValueError):
            pass
    acts = ctx.get("activities") or []
    for act in reversed(acts):
        if str(act.get("activity_type") or "").lower() == "system":
            continue
        blob = _fold(f"{act.get('activity_type')} {act.get('content')} {act.get('result')}")
        if "call" in blob or "goi" in blob or "gọi" in blob or "hotline" in blob:
            return 6
        if "chat" in blob or "zalo" in blob or "messenger" in blob:
            return 5
        if "form" in blob:
            return 4
        if "email" in blob:
            return 2
        if "like" in blob or "comment" in blob:
            return 1
        return 2
    return 0


def eval_age_years(ctx: dict[str, Any]) -> float:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    age = _parse_float(_meta_get(meta, "age", "age_years"))
    return float(age if age is not None else -1)


def eval_occupation_tier(ctx: dict[str, Any]) -> int:
    meta = ctx.get("meta") if isinstance(ctx.get("meta"), dict) else {}
    tier = _meta_get(meta, "occupation_tier")
    if tier is not None:
        try:
            return int(tier)
        except (TypeError, ValueError):
            pass
    blob = _fold(str(_meta_get(meta, "occupation", "job_title") or "") + " " + _text_blob(ctx))
    if any(k in blob for k in ("giam doc", "giám đốc", "doanh nhan", "doanh nhân", "ceo", "founder")):
        return 5
    if any(k in blob for k in ("bac si", "bác sĩ", "luat su", "luật sư", "chuyen gia", "chuyên gia")):
        return 4
    if any(k in blob for k in ("van phong", "văn phòng", "thu nhap cao", "thu nhập cao", "manager")):
        return 3
    if any(k in blob for k in ("kinh doanh", "tu do", "tự do", "freelance")):
        return 2
    if any(k in blob for k in ("cong chuc", "công chức", "vien chuc", "viên chức")):
        return 1
    return 0


EVALUATORS = {
    "info_completeness": eval_info_completeness,
    "web_behavior": eval_web_behavior,
    "site_time_minutes": eval_site_time_minutes,
    "budget_decl_quality": eval_budget_decl_quality,
    "budget_vs_price_pct": eval_budget_vs_price_pct,
    "purchase_timeline": eval_purchase_timeline,
    "urgency_reason": eval_urgency_reason,
    "lead_source": eval_lead_source,
    "interaction_count": eval_interaction_count,
    "last_interaction_type": eval_last_interaction_type,
    "age_years": eval_age_years,
    "occupation_tier": eval_occupation_tier,
}


def score_criterion(criterion: dict[str, Any], ctx: dict[str, Any]) -> tuple[int, Any]:
    if not criterion.get("enabled", True):
        return 0, None
    ev_id = str(criterion.get("evaluator") or "")
    fn = EVALUATORS.get(ev_id)
    if fn is None:
        return 0, None
    raw = fn(ctx)
    bands = criterion.get("bands") or []
    if ev_id == "lead_source":
        pts = score_bands_source(str(raw), bands)
    elif ev_id in (
        "info_completeness",
        "web_behavior",
        "budget_decl_quality",
        "purchase_timeline",
        "urgency_reason",
        "last_interaction_type",
        "occupation_tier",
    ):
        pts = score_bands_tier(int(raw), bands)
    elif ev_id == "age_years":
        age = float(raw)
        if age < 0:
            pts = score_bands_numeric(20, bands)  # unknown → lowest non-zero band handling
            for band in sorted(bands, key=lambda b: int(b.get("points", 0))):
                if band.get("min_value") is None and band.get("max_value") is None:
                    pts = int(band.get("points") or 1)
                    break
            else:
                pts = 1
        elif age < 25 or age > 65:
            pts = 1
        else:
            pts = score_bands_numeric(age, bands)
    elif ev_id == "budget_vs_price_pct":
        pct = float(raw)
        pts = 0 if pct < 0 else score_bands_numeric(pct, bands)
    else:
        pts = score_bands_numeric(float(raw), bands)
    max_pts = int(criterion.get("max_points") or 0)
    return min(pts, max_pts), raw


def score_lead_rubric(
    rubric: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    breakdown: list[dict[str, Any]] = []
    total = 0
    for group in rubric.get("groups") or []:
        for crit in group.get("criteria") or []:
            pts, raw_val = score_criterion(crit, ctx)
            total += pts
            breakdown.append(
                {
                    "id": str(crit.get("id") or ""),
                    "code": str(crit.get("code") or ""),
                    "label": str(crit.get("label") or ""),
                    "group_code": str(group.get("code") or ""),
                    "evaluator": str(crit.get("evaluator") or ""),
                    "points": pts,
                    "max_points": int(crit.get("max_points") or 0),
                    "applied": pts > 0,
                    "delta": pts,
                    "raw_value": raw_val,
                }
            )
    score = max(0, min(100, total))
    return {"score": score, "raw_total": total, "breakdown": breakdown, "rubric": True}
