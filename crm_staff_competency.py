"""Chấm điểm năng lực nhân viên — rubric phân bổ lead (100 điểm)."""
from __future__ import annotations

import re
from typing import Any

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")

METRIC_OPTIONS: list[dict[str, str]] = [
    {"id": "close_rate_pct", "label": "Tỷ lệ chốt từ lead (%)"},
    {"id": "kpi_achievement_pct", "label": "Doanh số so với KPI tháng (%)"},
    {"id": "avg_deal_value_billion", "label": "Giá trị TB mỗi deal (tỷ VNĐ)"},
    {"id": "avg_response_minutes", "label": "Tốc độ phản hồi TB (phút)"},
    {"id": "lead_coverage_pct", "label": "Tỷ lệ lead không bỏ sót (%)"},
    {"id": "appointment_conversion_pct", "label": "Tỷ lệ chuyển lead → lịch hẹn (%)"},
    {"id": "customer_rating", "label": "Điểm đánh giá KH sau tư vấn (/10)"},
    {"id": "referrals_per_month", "label": "Số KH giới thiệu / tháng"},
]

VALID_METRICS: frozenset[str] = frozenset(m["id"] for m in METRIC_OPTIONS)


def _slug_id(prefix: str, label: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", str(label or "").strip().lower()).strip("_")
    if raw and _ID_RE.match(raw):
        return raw[:48]
    return f"{prefix}_{abs(hash(label)) % 100000}"


def _band(
    label: str,
    points: int,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
    min_exclusive: bool = False,
    max_exclusive: bool = False,
    band_id: str = "",
) -> dict[str, Any]:
    return {
        "id": band_id or _slug_id("band", label),
        "label": label[:120],
        "points": max(0, min(100, int(points))),
        "min_value": min_value,
        "max_value": max_value,
        "min_exclusive": bool(min_exclusive),
        "max_exclusive": bool(max_exclusive),
    }


def _criterion(
    cid: str,
    code: str,
    label: str,
    max_points: int,
    metric: str,
    bands: list[dict[str, Any]],
    *,
    sort_order: int = 0,
) -> dict[str, Any]:
    return {
        "id": cid,
        "code": code[:16],
        "label": label[:200],
        "max_points": max(0, min(100, int(max_points))),
        "metric": metric if metric in VALID_METRICS else "close_rate_pct",
        "enabled": True,
        "sort_order": sort_order,
        "bands": bands,
    }


DEFAULT_COMPETENCY_GROUPS: list[dict[str, Any]] = [
    {
        "id": "group_a",
        "code": "A",
        "label": "HIỆU SUẤT BÁN HÀNG",
        "max_points": 50,
        "sort_order": 1,
        "criteria": [
            _criterion(
                "a1_close_rate",
                "A1",
                "Tỷ lệ chốt từ lead",
                20,
                "close_rate_pct",
                [
                    _band("> 35%", 20, min_value=35, min_exclusive=True, band_id="a1_b6"),
                    _band("25–35%", 17, min_value=25, max_value=35, band_id="a1_b5"),
                    _band("15–25%", 13, min_value=15, max_value=25, band_id="a1_b4"),
                    _band("8–15%", 8, min_value=8, max_value=15, band_id="a1_b3"),
                    _band("3–8%", 4, min_value=3, max_value=8, band_id="a1_b2"),
                    _band("< 3%", 0, max_value=3, max_exclusive=True, band_id="a1_b1"),
                ],
                sort_order=1,
            ),
            _criterion(
                "a2_kpi",
                "A2",
                "Doanh số so với KPI tháng",
                15,
                "kpi_achievement_pct",
                [
                    _band("> 200% KPI", 15, min_value=200, min_exclusive=True, band_id="a2_b7"),
                    _band("150–200%", 13, min_value=150, max_value=200, band_id="a2_b6"),
                    _band("120–150%", 11, min_value=120, max_value=150, band_id="a2_b5"),
                    _band("100–120%", 9, min_value=100, max_value=120, band_id="a2_b4"),
                    _band("80–100%", 6, min_value=80, max_value=100, band_id="a2_b3"),
                    _band("60–80%", 3, min_value=60, max_value=80, band_id="a2_b2"),
                    _band("< 60%", 0, max_value=60, max_exclusive=True, band_id="a2_b1"),
                ],
                sort_order=2,
            ),
            _criterion(
                "a3_avg_deal",
                "A3",
                "Giá trị trung bình mỗi deal",
                15,
                "avg_deal_value_billion",
                [
                    _band("> 8 tỷ/deal", 15, min_value=8, min_exclusive=True, band_id="a3_b5"),
                    _band("5–8 tỷ", 12, min_value=5, max_value=8, band_id="a3_b4"),
                    _band("3–5 tỷ", 9, min_value=3, max_value=5, band_id="a3_b3"),
                    _band("1–3 tỷ", 6, min_value=1, max_value=3, band_id="a3_b2"),
                    _band("< 1 tỷ", 3, max_value=1, max_exclusive=True, band_id="a3_b1"),
                ],
                sort_order=3,
            ),
        ],
    },
    {
        "id": "group_b",
        "code": "B",
        "label": "KỸ NĂNG XỬ LÝ LEAD",
        "max_points": 30,
        "sort_order": 2,
        "criteria": [
            _criterion(
                "b1_response",
                "B1",
                "Tốc độ phản hồi trung bình",
                10,
                "avg_response_minutes",
                [
                    _band("< 2 phút", 10, max_value=2, max_exclusive=True, band_id="b1_b5"),
                    _band("2–5 phút", 8, min_value=2, max_value=5, band_id="b1_b4"),
                    _band("5–10 phút", 5, min_value=5, max_value=10, band_id="b1_b3"),
                    _band("10–15 phút", 2, min_value=10, max_value=15, band_id="b1_b2"),
                    _band("> 15 phút", 0, min_value=15, min_exclusive=True, band_id="b1_b1"),
                ],
                sort_order=1,
            ),
            _criterion(
                "b2_coverage",
                "B2",
                "Tỷ lệ lead không bỏ sót",
                10,
                "lead_coverage_pct",
                [
                    _band("100%", 10, min_value=100, max_value=100, band_id="b2_b5"),
                    _band("97–99%", 8, min_value=97, max_value=99, band_id="b2_b4"),
                    _band("93–97%", 5, min_value=93, max_value=97, band_id="b2_b3"),
                    _band("88–93%", 2, min_value=88, max_value=93, band_id="b2_b2"),
                    _band("< 88%", 0, max_value=88, max_exclusive=True, band_id="b2_b1"),
                ],
                sort_order=2,
            ),
            _criterion(
                "b3_appointment",
                "B3",
                "Tỷ lệ chuyển lead thành lịch hẹn",
                10,
                "appointment_conversion_pct",
                [
                    _band("> 60%", 10, min_value=60, min_exclusive=True, band_id="b3_b5"),
                    _band("45–60%", 8, min_value=45, max_value=60, band_id="b3_b4"),
                    _band("30–45%", 6, min_value=30, max_value=45, band_id="b3_b3"),
                    _band("15–30%", 3, min_value=15, max_value=30, band_id="b3_b2"),
                    _band("< 15%", 0, max_value=15, max_exclusive=True, band_id="b3_b1"),
                ],
                sort_order=3,
            ),
        ],
    },
    {
        "id": "group_c",
        "code": "C",
        "label": "CHĂM SÓC KHÁCH HÀNG",
        "max_points": 20,
        "sort_order": 3,
        "criteria": [
            _criterion(
                "c1_rating",
                "C1",
                "Điểm đánh giá từ KH sau tư vấn",
                10,
                "customer_rating",
                [
                    _band("9.5–10.0", 10, min_value=9.5, max_value=10, band_id="c1_b6"),
                    _band("9.0–9.4", 8, min_value=9.0, max_value=9.4, band_id="c1_b5"),
                    _band("8.5–8.9", 6, min_value=8.5, max_value=8.9, band_id="c1_b4"),
                    _band("8.0–8.4", 4, min_value=8.0, max_value=8.4, band_id="c1_b3"),
                    _band("7.0–7.9", 2, min_value=7.0, max_value=7.9, band_id="c1_b2"),
                    _band("< 7.0", 0, max_value=7.0, max_exclusive=True, band_id="c1_b1"),
                ],
                sort_order=1,
            ),
            _criterion(
                "c2_referral",
                "C2",
                "Số KH giới thiệu thêm (Referral)",
                10,
                "referrals_per_month",
                [
                    _band("> 6/tháng", 10, min_value=6, min_exclusive=True, band_id="c2_b5"),
                    _band("4–6/tháng", 8, min_value=4, max_value=6, band_id="c2_b4"),
                    _band("2–3/tháng", 5, min_value=2, max_value=3, band_id="c2_b3"),
                    _band("1/tháng", 3, min_value=1, max_value=1, band_id="c2_b2"),
                    _band("0/tháng", 0, min_value=0, max_value=0, band_id="c2_b1"),
                ],
                sort_order=2,
            ),
        ],
    },
]

DEFAULT_COMPETENCY_CLASSIFICATION: list[dict[str, Any]] = [
    {
        "id": "cls_s",
        "min_score": 85,
        "max_score": 100,
        "level_id": "s",
        "label": "Level S",
        "emoji": "💎",
        "sort_order": 1,
    },
    {
        "id": "cls_a",
        "min_score": 65,
        "max_score": 84,
        "level_id": "a",
        "label": "Level A",
        "emoji": "🥇",
        "sort_order": 2,
    },
    {
        "id": "cls_b",
        "min_score": 45,
        "max_score": 64,
        "level_id": "b",
        "label": "Level B",
        "emoji": "🥈",
        "sort_order": 3,
    },
    {
        "id": "cls_c",
        "min_score": 0,
        "max_score": 44,
        "level_id": "c",
        "label": "Level C",
        "emoji": "🥉",
        "sort_order": 4,
    },
]


def _parse_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValueError("Ngưỡng số không hợp lệ.")


def _normalize_band(item: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    base = fallback or {}
    label = str(item.get("label") or base.get("label") or "").strip()
    if not label:
        raise ValueError("Mỗi mức điểm phải có nhãn.")
    try:
        points = int(item.get("points", base.get("points", 0)))
    except (TypeError, ValueError):
        raise ValueError(f"Điểm mức «{label}» không hợp lệ.")
    rid = str(item.get("id") or base.get("id") or "").strip().lower()
    if not rid:
        rid = _slug_id("band", label)
    if not _ID_RE.match(rid):
        raise ValueError(f"Mã mức điểm «{rid}» không hợp lệ.")
    min_value = _parse_float(item.get("min_value", base.get("min_value")))
    max_value = _parse_float(item.get("max_value", base.get("max_value")))
    return {
        "id": rid[:48],
        "label": label[:120],
        "points": max(0, min(100, points)),
        "min_value": min_value,
        "max_value": max_value,
        "min_exclusive": bool(item.get("min_exclusive", base.get("min_exclusive", False))),
        "max_exclusive": bool(item.get("max_exclusive", base.get("max_exclusive", False))),
    }


def _normalize_criterion(
    item: dict[str, Any],
    *,
    fallback: dict[str, Any] | None = None,
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
    code = str(item.get("code") or base.get("code") or rid.upper()[:8]).strip()[:16]
    metric = str(item.get("metric") or base.get("metric") or "close_rate_pct").strip()
    if metric not in VALID_METRICS:
        raise ValueError(f"Chỉ số «{metric}» không hợp lệ.")
    try:
        max_points = int(item.get("max_points", base.get("max_points", 0)))
    except (TypeError, ValueError):
        raise ValueError(f"Tiêu chí «{label}»: điểm tối đa không hợp lệ.")
    max_points = max(0, min(100, max_points))
    try:
        sort_order = int(item.get("sort_order", base.get("sort_order", 99)))
    except (TypeError, ValueError):
        sort_order = 99
    raw_bands = item.get("bands", base.get("bands"))
    if not isinstance(raw_bands, list) or not raw_bands:
        raise ValueError(f"Tiêu chí «{label}» cần ít nhất một mức điểm.")
    bands: list[dict[str, Any]] = []
    seen_band: set[str] = set()
    for bi, b in enumerate(raw_bands):
        if not isinstance(b, dict):
            continue
        fb = base.get("bands", [{}])[bi] if isinstance(base.get("bands"), list) and bi < len(base["bands"]) else None
        nb = _normalize_band(b, fallback=fb if isinstance(fb, dict) else None)
        if nb["id"] in seen_band:
            raise ValueError(f"Tiêu chí «{label}»: trùng mã mức {nb['id']}.")
        seen_band.add(nb["id"])
        bands.append(nb)
    if not bands:
        raise ValueError(f"Tiêu chí «{label}» cần ít nhất một mức điểm.")
    band_pts = [int(b["points"]) for b in bands]
    if max(band_pts) > max_points:
        raise ValueError(f"Tiêu chí «{label}»: điểm mức vượt tối đa {max_points}.")
    return {
        "id": rid[:48],
        "group_id": group_id,
        "code": code,
        "label": label[:200],
        "max_points": max_points,
        "metric": metric,
        "enabled": bool(item.get("enabled", base.get("enabled", True))),
        "sort_order": sort_order,
        "bands": bands,
    }


def _normalize_group(item: dict[str, Any], *, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    base = fallback or {}
    label = str(item.get("label") or base.get("label") or "").strip()
    if not label:
        raise ValueError("Nhóm tiêu chí phải có tên.")
    gid = str(item.get("id") or base.get("id") or "").strip().lower()
    if not gid:
        gid = _slug_id("group", label)
    if not _ID_RE.match(gid):
        raise ValueError(f"Mã nhóm «{gid}» không hợp lệ.")
    code = str(item.get("code") or base.get("code") or gid.upper()[:4]).strip()[:8]
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
    defaults_crit = {str(c["id"]): c for c in (base.get("criteria") or []) if isinstance(c, dict)}
    criteria: list[dict[str, Any]] = []
    seen_crit: set[str] = set()
    for ci, c in enumerate(raw_crit):
        if not isinstance(c, dict):
            continue
        fb = defaults_crit.get(str(c.get("id") or "").strip().lower())
        nc = _normalize_criterion(c, fallback=fb, group_id=gid)
        if nc["id"] in seen_crit:
            raise ValueError(f"Nhóm «{label}»: trùng tiêu chí {nc['id']}.")
        seen_crit.add(nc["id"])
        criteria.append(nc)
    crit_sum = sum(int(c["max_points"]) for c in criteria if c.get("enabled", True))
    if criteria and crit_sum > max_points:
        raise ValueError(
            f"Nhóm «{label}»: tổng điểm tiêu chí ({crit_sum}) vượt trần nhóm ({max_points})."
        )
    criteria.sort(key=lambda x: int(x.get("sort_order", 99)))
    return {
        "id": gid[:48],
        "code": code,
        "label": label[:120],
        "max_points": max(0, min(100, max_points)),
        "sort_order": sort_order,
        "criteria": criteria,
    }


def _normalize_classification_item(
    item: dict[str, Any],
    *,
    fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = fallback or {}
    rid = str(item.get("id") or base.get("id") or "").strip().lower()
    if not rid:
        rid = _slug_id("cls", str(item.get("label") or ""))
    if not _ID_RE.match(rid):
        raise ValueError(f"Mã phân loại «{rid}» không hợp lệ.")
    try:
        min_score = int(item.get("min_score", base.get("min_score", 0)))
        max_score = int(item.get("max_score", base.get("max_score", 100)))
    except (TypeError, ValueError):
        raise ValueError("Ngưỡng phân loại không hợp lệ.")
    min_score = max(0, min(100, min_score))
    max_score = max(0, min(100, max_score))
    if min_score > max_score:
        raise ValueError("Phân loại: điểm từ phải ≤ điểm đến.")
    level_id = str(item.get("level_id") or base.get("level_id") or "").strip().lower()
    if level_id not in ("s", "a", "b", "c"):
        raise ValueError("Phân loại phải gán Level S/A/B/C.")
    try:
        sort_order = int(item.get("sort_order", base.get("sort_order", 99)))
    except (TypeError, ValueError):
        sort_order = 99
    return {
        "id": rid[:48],
        "min_score": min_score,
        "max_score": max_score,
        "level_id": level_id,
        "label": str(item.get("label") or base.get("label") or f"Level {level_id.upper()}")[:80],
        "emoji": str(item.get("emoji") or base.get("emoji") or "").strip()[:8],
        "sort_order": sort_order,
    }


def _validate_classification_overlap(items: list[dict[str, Any]]) -> None:
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if a["min_score"] <= b["max_score"] and b["min_score"] <= a["max_score"]:
                raise ValueError(
                    f"Ngưỡng phân loại trùng: «{a['label']}» ({a['min_score']}–{a['max_score']}) "
                    f"và «{b['label']}» ({b['min_score']}–{b['max_score']})."
                )


def normalize_competency_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("competency phải là object.")
    defaults_by_id = {str(g["id"]): g for g in DEFAULT_COMPETENCY_GROUPS}
    raw_groups = raw.get("groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("Cần ít nhất một nhóm tiêu chí.")
    groups: list[dict[str, Any]] = []
    seen_g: set[str] = set()
    for g in raw_groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or "").strip().lower()
        fb = defaults_by_id.get(gid)
        ng = _normalize_group(g, fallback=fb)
        if ng["id"] in seen_g:
            raise ValueError(f"Trùng nhóm {ng['id']}.")
        seen_g.add(ng["id"])
        groups.append(ng)
    if not groups:
        raise ValueError("Cần ít nhất một nhóm tiêu chí.")
    groups.sort(key=lambda x: int(x.get("sort_order", 99)))

    raw_cls = raw.get("classification")
    if not isinstance(raw_cls, list) or not raw_cls:
        raise ValueError("Cần ít nhất một mức phân loại kết quả.")
    defaults_cls = {str(c["id"]): c for c in DEFAULT_COMPETENCY_CLASSIFICATION}
    classification: list[dict[str, Any]] = []
    seen_c: set[str] = set()
    for c in raw_cls:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip().lower()
        fb = defaults_cls.get(cid)
        nc = _normalize_classification_item(c, fallback=fb)
        if nc["id"] in seen_c:
            raise ValueError(f"Trùng phân loại {nc['id']}.")
        seen_c.add(nc["id"])
        classification.append(nc)
    if not classification:
        raise ValueError("Cần ít nhất một mức phân loại kết quả.")
    classification.sort(key=lambda x: int(x.get("sort_order", 99)))
    _validate_classification_overlap(classification)
    return {"groups": groups, "classification": classification}


def merge_competency_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw or not isinstance(raw, dict):
        return default_competency_config()
    try:
        return normalize_competency_config(raw)
    except ValueError:
        return default_competency_config()


def default_competency_config() -> dict[str, Any]:
    import copy

    return {
        "groups": copy.deepcopy(DEFAULT_COMPETENCY_GROUPS),
        "classification": copy.deepcopy(DEFAULT_COMPETENCY_CLASSIFICATION),
    }


def band_matches_value(value: float, band: dict[str, Any]) -> bool:
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


def score_metric_value(value: float, criterion: dict[str, Any]) -> int:
    if not criterion.get("enabled", True):
        return 0
    bands = criterion.get("bands") or []
    ordered = sorted(bands, key=lambda b: int(b.get("points", 0)), reverse=True)
    for band in ordered:
        if band_matches_value(float(value), band):
            return int(band.get("points") or 0)
    return 0


def score_staff_competency(
    metrics: dict[str, float | int],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tính tổng điểm năng lực từ dict metric → level_id."""
    cfg = config or default_competency_config()
    breakdown: list[dict[str, Any]] = []
    total = 0
    for group in cfg.get("groups") or []:
        group_pts = 0
        for crit in group.get("criteria") or []:
            if not crit.get("enabled", True):
                continue
            key = str(crit.get("metric") or "")
            if key not in metrics:
                continue
            pts = score_metric_value(float(metrics[key]), crit)
            group_pts += pts
            breakdown.append(
                {
                    "criterion_id": crit.get("id"),
                    "code": crit.get("code"),
                    "label": crit.get("label"),
                    "metric": key,
                    "value": metrics[key],
                    "points": pts,
                    "max_points": crit.get("max_points"),
                }
            )
        total += group_pts
    total = max(0, min(100, total))
    level_id = classify_competency_score(total, cfg.get("classification") or [])
    return {
        "total_score": total,
        "level_id": level_id,
        "breakdown": breakdown,
    }


def classify_competency_score(score: int, classification: list[dict[str, Any]]) -> str:
    s = max(0, min(100, int(score)))
    ordered = sorted(classification, key=lambda x: int(x.get("sort_order", 99)))
    for item in ordered:
        if s >= int(item["min_score"]) and s <= int(item["max_score"]):
            return str(item.get("level_id") or "c")
    return "c"
