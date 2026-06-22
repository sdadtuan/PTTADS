"""Tự động phân lead cho nhân viên — nhiều phương pháp, bật/tắt theo nghiệp vụ."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from crm_sales_pipeline import round_robin_assign
from crm_project_leads import assignment_pool_key

ASSIGNMENT_POOL = "lead_round_robin"

# Phân hạng lead → cấp NV (Phương pháp 2 & 6 — tài liệu nghiệp vụ)
DEFAULT_TIER_LEVEL_MAP: dict[str, list[str]] = {
    "vip": ["s", "a"],
    "hot": ["s", "a"],
    "warm_plus": ["a", "b"],
    "warm": ["b", "c"],
    "cold_plus": ["b", "c"],
    "cold": ["c"],
    # Phân hạng tùy chỉnh thường gặp trên CRM
    "moi": ["b", "c"],
    "normal": ["a", "b"],
    "unclassified": ["a", "b", "c"],
}

STRATEGY_DEFS: list[dict[str, Any]] = [
    {
        "id": "hybrid",
        "label": "Mô hình hỗn hợp (Hybrid)",
        "emoji": "🔀",
        "description": "B1 phân loại → B2 lọc năng lực NV → B3 Round Robin trong nhóm (khuyên dùng).",
        "enabled": True,
        "priority": 10,
        "category": "core",
    },
    {
        "id": "skill_based",
        "label": "Phân theo năng lực (Skill-Based)",
        "emoji": "🎯",
        "description": "VIP/HOT → S/A; WARM+ → A/B; WARM → B/C; COLD → C (theo bảng phân hạng).",
        "enabled": True,
        "priority": 20,
        "category": "core",
    },
    {
        "id": "round_robin",
        "label": "Round Robin (Phân vòng)",
        "emoji": "🔄",
        "description": "Chia lead luân phiên công bằng trong nhóm NV còn lại.",
        "enabled": True,
        "priority": 30,
        "category": "core",
    },
    {
        "id": "region_product",
        "label": "Phân theo khu vực / sản phẩm",
        "emoji": "🗺️",
        "description": "Chỉ xét NV có ghi chú trùng khu vực hoặc sản phẩm lead.",
        "enabled": True,
        "priority": 40,
        "category": "routing",
    },
    {
        "id": "performance",
        "label": "Phân theo hiệu suất",
        "emoji": "📈",
        "description": "NV tỷ lệ chốt cao được ưu tiên nhận lead (khi không dùng Round Robin).",
        "enabled": False,
        "priority": 50,
        "category": "routing",
    },
    {
        "id": "customer_profile",
        "label": "Phân theo đặc điểm KH",
        "emoji": "👤",
        "description": "Match nhu cầu KH (doanh nhân, đầu tư, việt kiều…) với ghi chú NV.",
        "enabled": False,
        "priority": 60,
        "category": "routing",
    },
    {
        "id": "hot_priority_min_load",
        "label": "Hot/VIP → NV ít tải nhất",
        "emoji": "🔥",
        "description": "Lead Hot/VIP gán NV ít lead mở (áp dụng khi không bật Hybrid).",
        "enabled": True,
        "priority": 15,
        "category": "priority",
    },
    {
        "id": "vip_to_level_s",
        "label": "VIP → Level S/A",
        "emoji": "💎",
        "description": "Lead VIP chỉ phân cho NV Level S hoặc A.",
        "enabled": True,
        "priority": 12,
        "category": "priority",
    },
    {
        "id": "respect_daily_cap",
        "label": "Giới hạn lead/ngày",
        "emoji": "📊",
        "description": "Không vượt số lead tối đa/ngày theo cấp NV (S/A/B/C).",
        "enabled": True,
        "priority": 25,
        "category": "guard",
    },
    {
        "id": "cold_to_level_c",
        "label": "Cold → Level C",
        "emoji": "⚫",
        "description": "Lead Cold/COLD+ ưu tiên NV Level C (nuôi dưỡng / automation).",
        "enabled": True,
        "priority": 35,
        "category": "routing",
    },
]

CUSTOMER_PROFILE_KEYWORDS: dict[str, list[str]] = {
    "doanh_nhan": ["doanh nhân", "ceo", "giám đốc", "bận rộn", "cao cấp"],
    "dau_tu": ["đầu tư", "roi", "tài chính", "cho thuê", "lướt sóng"],
    "nuoc_ngoai": ["nước ngoài", "việt kiều", "foreign", "expat", "english"],
    "lan_dau": ["lần đầu", "mua nhà lần đầu", "tân thủ", "mới mua"],
    "gen_z": ["gen z", "20 tuổi", "25 tuổi", "trẻ", "digital"],
    # Phase 2 — VHHM Shophouse · Biệt thự · Liền kề
    "shophouse_sme": [
        "shophouse", "mặt bằng kinh doanh", "chủ shop", "cửa hàng",
        "f&b", "salon", "phòng khám", "nhà thuốc", "nhượng quyền",
        "kinh doanh", "mở tiệm", "văn phòng",
    ],
    "doi_nha": [
        "đổi nhà", "nâng cấp", "bán nhà cũ", "nhà hiện tại",
        "hóc môn", "củ chi", "bình dương", "quận 12", "q12",
    ],
    "da_the_he": [
        "gia đình", "bố mẹ", "ông bà", "con cái", "nhiều thế hệ",
        "cả nhà", "cụm", "2 căn", "3 căn", "mua cho ba mẹ",
    ],
    "viet_kieu": [
        "việt kiều", "mỹ", "úc", "canada", "nhật", "hàn",
        "từ nước ngoài", "gửi tiền về", "mua cho bố mẹ", "ủy quyền",
    ],
    "legacy": [
        "tài sản lâu dài", "để lại cho con", "con cháu", "bền vững",
        "tích lũy", "di sản", "legacy", "đầu tư dài hạn",
    ],
}

HOT_TIERS = frozenset({"vip", "hot", "warm_plus"})
COLD_TIERS = frozenset({"cold", "cold_plus"})


@dataclass
class StaffCandidate:
    id: int
    name: str
    sales_level: str
    notes: str
    open_load: int
    leads_today: int
    daily_cap: int
    performance_score: float = 0.0
    region_score: float = 0.0
    profile_score: float = 0.0


@dataclass
class LeadAssignContext:
    lead_level: str = "warm"
    lead_score: int = 0
    region: str = ""
    product_interest: str = ""
    source: str = ""
    need: str = ""
    prefer_staff_id: int | None = None
    prefer_min_workload: bool = False
    re_project_id: int | None = None
    product_line: str = ""
    zone: str = ""


def _norm(s: str) -> str:
    return str(s or "").strip().lower()


def merge_assign_strategies(raw: list[Any] | None) -> list[dict[str, Any]]:
    by_id = {str(d["id"]): copy.deepcopy(d) for d in STRATEGY_DEFS}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id") or "").strip()
            if sid not in by_id:
                continue
            if "enabled" in item:
                by_id[sid]["enabled"] = bool(item["enabled"])
            if "priority" in item:
                try:
                    by_id[sid]["priority"] = int(item["priority"])
                except (TypeError, ValueError):
                    pass
    out = list(by_id.values())
    out.sort(key=lambda x: int(x.get("priority", 99)))
    return out


def merge_tier_level_map(raw: dict[str, Any] | None) -> dict[str, list[str]]:
    merged = {k: list(v) for k, v in DEFAULT_TIER_LEVEL_MAP.items()}
    if isinstance(raw, dict):
        for tier, levels in raw.items():
            tid = _norm(tier)
            if not tid:
                continue
            if isinstance(levels, list):
                merged[tid] = [str(x).strip().lower() for x in levels if str(x).strip()]
    return merged


def merge_assign_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = raw if isinstance(raw, dict) else {}
    return {
        "auto_assign_enabled": bool(base.get("auto_assign_enabled", True)),
        "strategies": merge_assign_strategies(base.get("strategies")),
        "tier_level_map": merge_tier_level_map(base.get("tier_level_map")),
    }


def normalize_assign_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("assign_config phải là object.")
    cfg = merge_assign_config(raw)
    seen: set[str] = set()
    for s in cfg["strategies"]:
        sid = str(s.get("id") or "")
        if sid in seen:
            raise ValueError(f"Phương pháp phân lead trùng mã: {sid}")
        seen.add(sid)
    return cfg


def config_with_only(*enabled_ids: str, auto_assign: bool = True) -> dict[str, Any]:
    """Helper test — chỉ bật các phương pháp chỉ định (+ skill nếu cần cho hybrid)."""
    strategies = []
    for d in STRATEGY_DEFS:
        strategies.append(
            {
                "id": d["id"],
                "enabled": d["id"] in enabled_ids,
                "priority": d["priority"],
            }
        )
    return merge_assign_config({"auto_assign_enabled": auto_assign, "strategies": strategies})


def _today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _staff_daily_cap(conn: Any, sales_level: str) -> int:
    from crm_staff_levels import merge_staff_levels

    lv = _norm(sales_level)
    for row in merge_staff_levels(None):
        if _norm(row.get("id")) == lv:
            return int(row.get("max_leads_max") or 0)
    return 0


def _staff_leads_today(conn: Any, staff_id: int) -> int:
    prefix = _today_prefix()
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM crm_leads
        WHERE owner_id = ? AND created_at LIKE ? AND COALESCE(is_duplicate, 0) = 0
        """,
        (int(staff_id), f"{prefix}%"),
    ).fetchone()
    return int(row["c"]) if row else 0


def _staff_open_load(conn: Any, staff_id: int) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM crm_leads
        WHERE owner_id = ? AND status NOT IN ('won', 'lost')
        """,
        (int(staff_id),),
    ).fetchone()
    return int(row["c"]) if row else 0


def _staff_performance_score(conn: Any, staff_id: int) -> float:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS won
        FROM crm_leads
        WHERE owner_id = ? AND COALESCE(is_duplicate, 0) = 0
        """,
        (int(staff_id),),
    ).fetchone()
    total = int(row["total"] or 0) if row else 0
    won = int(row["won"] or 0) if row else 0
    close_rate = (won / total) if total > 0 else 0.05
    load = _staff_open_load(conn, staff_id)
    return close_rate * 100.0 - load * 1.5


def _staff_has_sales_level(conn: Any) -> bool:
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_staff)").fetchall()}
        return "sales_level" in cols
    except Exception:
        return False


def _fetch_candidates(conn: Any, ctx: LeadAssignContext) -> list[StaffCandidate]:
    has_sl = _staff_has_sales_level(conn)
    sl_expr = "COALESCE(sales_level, '') AS sales_level" if has_sl else "'' AS sales_level"
    params: list[Any] = []
    where = "COALESCE(active, 1) = 1"
    if ctx.re_project_id:
        from crm_project_leads import fetch_project_assign_staff_ids

        staff_ids = fetch_project_assign_staff_ids(
            conn,
            int(ctx.re_project_id),
            product_line=str(ctx.product_line or ""),
            zone=str(ctx.zone or ""),
        )
        if not staff_ids:
            return []
        placeholders = ",".join("?" * len(staff_ids))
        where += f" AND id IN ({placeholders})"
        params.extend(staff_ids)
    rows = conn.execute(
        f"""
        SELECT id, name, notes, {sl_expr}
        FROM crm_staff
        WHERE {where}
        ORDER BY id
        """,
        params,
    ).fetchall()
    out: list[StaffCandidate] = []
    reg = _norm(ctx.region)
    prod = _norm(ctx.product_interest)
    need = _norm(ctx.need)
    line_code = _norm(ctx.product_line)
    zone_n = _norm(ctx.zone)
    line_label = ""
    if line_code:
        try:
            from crm_re_projects import PRODUCT_LINE_LABELS

            line_label = _norm(PRODUCT_LINE_LABELS.get(ctx.product_line, ctx.product_line))
        except Exception:
            line_label = line_code
    for r in rows:
        sid = int(r["id"])
        notes = str(r["notes"] or "")
        notes_l = notes.lower()
        sl = _norm(r["sales_level"])
        region_score = 0.0
        if reg and (reg in notes_l or reg in _norm(r["name"])):
            region_score += 2.0
        if prod and prod in notes_l:
            region_score += 1.5
        if line_code and (line_code in notes_l or (line_label and line_label in notes_l)):
            region_score += 2.0
        if zone_n and zone_n in notes_l:
            region_score += 1.5
        profile_score = 0.0
        for _tag, kws in CUSTOMER_PROFILE_KEYWORDS.items():
            need_hit = any(kw in need for kw in kws)
            staff_hit = any(kw in notes_l for kw in kws)
            if need_hit and staff_hit:
                profile_score += 2.0
            elif need_hit or staff_hit:
                profile_score += 0.25
        out.append(
            StaffCandidate(
                id=sid,
                name=str(r["name"] or ""),
                sales_level=sl,
                notes=notes,
                open_load=_staff_open_load(conn, sid),
                leads_today=_staff_leads_today(conn, sid),
                daily_cap=_staff_daily_cap(conn, sl),
                performance_score=_staff_performance_score(conn, sid),
                region_score=region_score,
                profile_score=profile_score,
            )
        )
    return out


def _is_enabled(strategies: list[dict[str, Any]], sid: str) -> bool:
    for s in strategies:
        if str(s.get("id")) == sid:
            return bool(s.get("enabled", False))
    return False


def _allowed_levels(tier: str, tier_map: dict[str, list[str]]) -> list[str]:
    t = _norm(tier)
    if t in tier_map and tier_map[t]:
        return tier_map[t]
    unc = tier_map.get("unclassified") or DEFAULT_TIER_LEVEL_MAP.get("unclassified") or []
    if unc:
        return unc
    if t in ("hot", "vip"):
        return ["s", "a"]
    if t in ("warm", "warm_plus", "normal", "moi"):
        return ["a", "b"] if t in ("warm_plus", "normal") else ["b", "c"]
    if t in ("cold", "cold_plus"):
        return ["c"]
    return ["a", "b", "c"]


def _filter_level(
    candidates: list[StaffCandidate],
    levels: list[str],
    *,
    strict: bool = False,
) -> list[StaffCandidate]:
    allow = {str(x).lower() for x in levels}
    filtered = [c for c in candidates if c.sales_level and c.sales_level in allow]
    if filtered:
        return filtered
    if strict:
        return []
    # NV chưa gán cấp — giữ pool gốc
    unassigned = [c for c in candidates if not c.sales_level]
    return unassigned or candidates


def _filter_daily_cap(candidates: list[StaffCandidate]) -> list[StaffCandidate]:
    filtered = [c for c in candidates if c.daily_cap <= 0 or c.leads_today < c.daily_cap]
    return filtered or candidates


def _filter_region_product(
    candidates: list[StaffCandidate], ctx: LeadAssignContext
) -> list[StaffCandidate]:
    reg = _norm(ctx.region)
    prod = _norm(ctx.product_interest)
    if not reg and not prod:
        return candidates
    matched = [c for c in candidates if c.region_score > 0]
    return matched or candidates


def _filter_customer_profile(
    candidates: list[StaffCandidate], ctx: LeadAssignContext
) -> list[StaffCandidate]:
    need = _norm(ctx.need)
    if not need:
        return candidates
    need_tags = {
        tag
        for tag, kws in CUSTOMER_PROFILE_KEYWORDS.items()
        if any(kw in need for kw in kws)
    }
    if not need_tags:
        return candidates
    matched = [c for c in candidates if c.profile_score >= 2.0]
    return matched or candidates


def _ensure_assignment_state_table(conn: Any) -> None:
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_assignment_state (
                pool_key TEXT PRIMARY KEY,
                last_staff_id INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    except Exception:
        pass


def _pick_round_robin(
    conn: Any,
    candidates: list[StaffCandidate],
    *,
    pool_key: str | None = None,
) -> StaffCandidate:
    if not candidates:
        raise ValueError("Không có NV candidate.")
    pk = pool_key or ASSIGNMENT_POOL
    ids = sorted({c.id for c in candidates})
    _ensure_assignment_state_table(conn)
    last_id = 0
    try:
        state = conn.execute(
            "SELECT last_staff_id FROM crm_assignment_state WHERE pool_key = ?",
            (pk,),
        ).fetchone()
        if state:
            last_id = int(state["last_staff_id"] or 0)
    except Exception:
        last_id = 0
    try:
        idx = ids.index(last_id)
        next_id = ids[(idx + 1) % len(ids)]
    except ValueError:
        next_id = ids[0]
    try:
        conn.execute(
            """
            INSERT INTO crm_assignment_state (pool_key, last_staff_id)
            VALUES (?, ?)
            ON CONFLICT(pool_key) DO UPDATE SET last_staff_id = excluded.last_staff_id
            """,
            (pk, next_id),
        )
        conn.commit()
    except Exception:
        pass
    return next(c for c in candidates if c.id == next_id)


def _pick_min_load(candidates: list[StaffCandidate]) -> StaffCandidate:
    return sorted(candidates, key=lambda c: (c.open_load, c.leads_today, c.id))[0]


def _pick_top_performance(candidates: list[StaffCandidate]) -> StaffCandidate:
    return sorted(candidates, key=lambda c: (-c.performance_score, c.open_load, c.id))[0]


def _pick_top_profile(candidates: list[StaffCandidate]) -> StaffCandidate:
    return sorted(candidates, key=lambda c: (-c.profile_score, c.open_load, c.id))[0]


def auto_assign_lead_owner(
    conn: Any,
    ctx: LeadAssignContext,
    *,
    config: dict[str, Any] | None = None,
) -> tuple[int | None, str, str]:
    """
    Pipeline theo tài liệu nghiệp vụ:
    1) Lọc NV (VIP, năng lực, cold, cap, khu vực, profile)
    2) Chọn NV: Hybrid/RR trong nhóm | Hot min-load | Performance | Profile | Min-load
    """
    cfg = config or merge_assign_config(None)
    if not cfg.get("auto_assign_enabled", True):
        return None, "", "disabled"

    strategies = cfg.get("strategies") or merge_assign_strategies(None)
    tier_map = cfg.get("tier_level_map") or DEFAULT_TIER_LEVEL_MAP

    if ctx.prefer_staff_id:
        if ctx.re_project_id:
            from crm_project_leads import staff_may_receive_project_lead

            if not staff_may_receive_project_lead(conn, int(ctx.re_project_id), int(ctx.prefer_staff_id)):
                return None, "", "staff_not_in_project"
        row = conn.execute(
            "SELECT id, name FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
            (ctx.prefer_staff_id,),
        ).fetchone()
        if row:
            return int(row["id"]), str(row["name"]), "prefer_staff"

    pool_key = assignment_pool_key(ctx.re_project_id)
    candidates = _fetch_candidates(conn, ctx)
    if not candidates:
        if ctx.re_project_id:
            return None, "", "no_project_staff"
        try:
            _, aid = round_robin_assign(conn, pool_key=ASSIGNMENT_POOL)
            if aid:
                nm = conn.execute("SELECT name FROM crm_staff WHERE id = ?", (aid,)).fetchone()
                return aid, str(nm["name"]) if nm else "", "round_robin_fallback"
        except Exception:
            pass
        return None, "", "none"

    tier = _norm(ctx.lead_level)
    hybrid_on = _is_enabled(strategies, "hybrid")
    skill_on = _is_enabled(strategies, "skill_based") or hybrid_on
    used_filters: list[str] = []

    # --- Bước lọc (theo thứ tự nghiệp vụ) ---
    if _is_enabled(strategies, "vip_to_level_s") and tier == "vip":
        nxt = _filter_level(candidates, ["s", "a"], strict=True)
        if nxt:
            candidates = nxt
            used_filters.append("vip_to_level_s")

    if skill_on:
        levels = _allowed_levels(tier, tier_map)
        nxt = _filter_level(candidates, levels, strict=True)
        if nxt:
            candidates = nxt
            used_filters.append("hybrid" if hybrid_on else "skill_based")

    if _is_enabled(strategies, "cold_to_level_c") and tier in COLD_TIERS:
        nxt = _filter_level(candidates, ["c"], strict=True)
        if nxt:
            candidates = nxt
            used_filters.append("cold_to_level_c")

    if _is_enabled(strategies, "respect_daily_cap"):
        candidates = _filter_daily_cap(candidates)
        used_filters.append("respect_daily_cap")

    if _is_enabled(strategies, "region_product"):
        nxt = _filter_region_product(candidates, ctx)
        if len(nxt) < len(candidates):
            used_filters.append("region_product")
        candidates = nxt

    if _is_enabled(strategies, "customer_profile"):
        nxt = _filter_customer_profile(candidates, ctx)
        if len(nxt) < len(candidates):
            used_filters.append("customer_profile")
        candidates = nxt

    if not candidates:
        return None, "", "no_candidate_after_filter"

    # --- Bước chọn NV ---
    if ctx.prefer_min_workload:
        pick = _pick_min_load(candidates)
        return pick.id, pick.name, "min_workload"

    # Hybrid (PP6): luôn Round Robin trong nhóm sau khi lọc năng lực
    if hybrid_on:
        pick = _pick_round_robin(conn, candidates, pool_key=pool_key)
        return pick.id, pick.name, "hybrid"

    if _is_enabled(strategies, "round_robin"):
        pick = _pick_round_robin(conn, candidates, pool_key=pool_key)
        return pick.id, pick.name, "round_robin"

    # Hot/VIP ít tải — chỉ khi không dùng Hybrid/RR (PP2 quy trình thực tế bước 2)
    if _is_enabled(strategies, "hot_priority_min_load") and tier in HOT_TIERS:
        pick = _pick_min_load(candidates)
        return pick.id, pick.name, "hot_priority_min_load"

    if _is_enabled(strategies, "performance"):
        pick = _pick_top_performance(candidates)
        return pick.id, pick.name, "performance"

    if _is_enabled(strategies, "customer_profile"):
        pick = _pick_top_profile(candidates)
        return pick.id, pick.name, "customer_profile"

    pick = _pick_min_load(candidates)
    tag = used_filters[-1] if used_filters else "min_load_fallback"
    return pick.id, pick.name, tag
