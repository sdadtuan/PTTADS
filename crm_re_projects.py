"""CRM Kinh doanh — Quản lý dự án bất động sản (7 hạng mục)."""
from __future__ import annotations

import copy
import json
import re
import sqlite3
from datetime import datetime
from typing import Any

PROJECT_TYPES = ("can_ho", "nha_pho", "dat_nen", "shophouse", "biet_thu", "mixed")
DEFAULT_PROJECT_TYPE_LABELS: dict[str, str] = {
    "can_ho": "Căn hộ chung cư",
    "nha_pho": "Nhà phố / Townhouse",
    "dat_nen": "Đất nền",
    "shophouse": "Shophouse",
    "biet_thu": "Biệt thự",
    "mixed": "Hỗn hợp",
}
# Giữ alias tương thích import cũ
PROJECT_TYPE_LABELS = DEFAULT_PROJECT_TYPE_LABELS

PROJECT_STATUSES = ("planning", "presale", "selling", "handover", "completed", "paused")
PROJECT_STATUS_LABELS: dict[str, str] = {
    "planning": "Lập kế hoạch",
    "presale": "Mở bán (Presale)",
    "selling": "Đang bán",
    "handover": "Bàn giao",
    "completed": "Hoàn thành",
    "paused": "Tạm dừng",
}

PRODUCT_STATUSES = ("available", "hold", "booked", "sold", "locked")
PRODUCT_STATUS_LABELS: dict[str, str] = {
    "available": "Còn hàng",
    "hold": "Giữ chỗ",
    "booked": "Đặt cọc",
    "sold": "Đã bán",
    "locked": "Khóa",
}

RISK_LEVELS = ("low", "medium", "high", "critical")
RISK_LEVEL_LABELS: dict[str, str] = {
    "low": "Thấp",
    "medium": "Trung bình",
    "high": "Cao",
    "critical": "Nghiêm trọng",
}

RISK_CATEGORIES = ("legal", "market", "finance", "construction", "sales", "partner", "other")
RISK_CATEGORY_LABELS: dict[str, str] = {
    "legal": "Pháp lý",
    "market": "Thị trường",
    "finance": "Tài chính",
    "construction": "Thi công",
    "sales": "Bán hàng",
    "partner": "Đối tác",
    "other": "Khác",
}

BUDGET_CATEGORIES = ("revenue", "cogs", "marketing", "sales", "admin", "other")
BUDGET_CATEGORY_LABELS: dict[str, str] = {
    "revenue": "Doanh thu",
    "cogs": "Giá vốn / COGS",
    "marketing": "Marketing",
    "sales": "Bán hàng",
    "admin": "Quản lý",
    "other": "Khác",
}

KPI_CATEGORIES = ("revenue", "sales", "marketing", "finance", "customer", "operation")
KPI_CATEGORY_LABELS: dict[str, str] = {
    "revenue": "Doanh thu",
    "sales": "Bán hàng",
    "marketing": "Marketing",
    "finance": "Tài chính",
    "customer": "Khách hàng",
    "operation": "Vận hành",
}

# Loại hình sản phẩm trong khu đô thị / dự án hỗn hợp
PRODUCT_LINES = (
    "can_ho",
    "thap_tang_thap",
    "studio",
    "duplex",
    "penthouse",
    "shophouse",
    "nha_pho",
    "song_lap",
    "biet_thu",
    "nha_vuon",
    "lien_ke",
    "dat_nen",
    "dat_nen_noi_khu",
    "dat_nen_ngoai_khu",
    "dat_biet_thu",
    "officetel",
    "condotel",
    "can_ho_dich_vu",
    "mat_bang",
    "tien_ich",
    "nha_xuong",
    "khu_cong_nghiep",
    "other",
)
PRODUCT_LINE_LABELS: dict[str, str] = {
    "can_ho": "Căn hộ chung cư",
    "thap_tang_thap": "Chung cư thấp tầng",
    "studio": "Studio / Căn hộ mini",
    "duplex": "Duplex / Dual key",
    "penthouse": "Penthouse / Sky villa",
    "shophouse": "Shophouse / Nhà phố TM",
    "nha_pho": "Nhà phố / Townhouse",
    "song_lap": "Nhà song lập / Semi-detached",
    "biet_thu": "Biệt thự",
    "nha_vuon": "Nhà vườn",
    "lien_ke": "Liền kề",
    "dat_nen": "Đất nền",
    "dat_nen_noi_khu": "Đất nền nội khu",
    "dat_nen_ngoai_khu": "Đất nền ngoại khu / ven KĐT",
    "dat_biet_thu": "Đất biệt thự",
    "officetel": "Officetel",
    "condotel": "Condotel / Khách sạn căn",
    "can_ho_dich_vu": "Căn hộ dịch vụ / Serviced apt",
    "mat_bang": "Mặt bằng kinh doanh",
    "tien_ich": "Tiện ích / Công cộng",
    "nha_xuong": "Nhà xưởng / Kho bãi",
    "khu_cong_nghiep": "Khu công nghiệp / CCN",
    "other": "Khác",
}

PRODUCT_TYPOLOGIES = (
    "studio",
    "1pn",
    "1pn_plus",
    "2pn",
    "2pn_plus",
    "3pn",
    "3pn_plus",
    "4pn",
    "multi",
    "shophouse",
    "corner",
    "standard",
    "garden",
    "semi_detached",
    "thap_5",
    "thap_8",
    "dat_100",
    "dat_150",
    "dat_200",
    "dat_300",
    "dat_500",
    "other",
)
PRODUCT_TYPOLOGY_LABELS: dict[str, str] = {
    "studio": "Studio",
    "1pn": "1 phòng ngủ",
    "1pn_plus": "1PN+",
    "2pn": "2 phòng ngủ",
    "2pn_plus": "2PN+",
    "3pn": "3 phòng ngủ",
    "3pn_plus": "3PN+",
    "4pn": "4+ phòng ngủ",
    "multi": "Đa phòng / Compound",
    "shophouse": "Shophouse",
    "corner": "Căn góc / End unit",
    "standard": "Căn thường",
    "garden": "Nhà vườn / Garden",
    "semi_detached": "Song lập",
    "thap_5": "Thấp tầng ≤ 5 tầng",
    "thap_8": "Thấp tầng ≤ 8 tầng",
    "dat_100": "Đất ~100 m²",
    "dat_150": "Đất ~150 m²",
    "dat_200": "Đất ~200 m²",
    "dat_300": "Đất ~300 m²",
    "dat_500": "Đất ≥ 500 m²",
    "other": "Khác",
}

KPI_TRACK_STATUSES = ("draft", "active", "completed", "cancelled")
KPI_TRACK_STATUS_LABELS: dict[str, str] = {
    "draft": "Nháp",
    "active": "Đang theo dõi",
    "completed": "Hoàn thành kỳ",
    "cancelled": "Hủy",
}

KPI_METRIC_TEMPLATES: tuple[dict[str, Any], ...] = (
    {"code": "units_sold", "crm_code": "RE_UNITS_SOLD", "metric_name": "Số căn bán ký HĐ", "category": "sales", "unit": "căn", "weight_pct": 25},
    {"code": "revenue_signed", "crm_code": "RE_REVENUE_SIGNED", "metric_name": "Doanh thu ký HĐ", "category": "revenue", "unit": "VND", "weight_pct": 25},
    {"code": "leads_new", "crm_code": "RE_LEADS_NEW", "metric_name": "Lead mới qualified", "category": "marketing", "unit": "lead", "weight_pct": 10},
    {"code": "showroom_visits", "crm_code": "RE_SHOWROOM_VISITS", "metric_name": "Lượt tham quan showroom", "category": "sales", "unit": "lượt", "weight_pct": 10},
    {"code": "conversion_rate", "crm_code": "RE_CONVERSION_RATE", "metric_name": "Tỷ lệ chốt lead → cọc", "category": "sales", "unit": "%", "weight_pct": 15},
    {"code": "deposit_collected", "crm_code": "RE_DEPOSIT_COLLECTED", "metric_name": "Số căn thu cọc", "category": "sales", "unit": "căn", "weight_pct": 10},
    {"code": "collection_rate", "crm_code": "RE_COLLECTION_RATE", "metric_name": "Tỷ lệ thu tiền theo tiến độ", "category": "finance", "unit": "%", "weight_pct": 5},
)

RE_PROJECT_SECTION_IDS = (
    "crm_re_projects",
    "crm_re_projects_business",
    "crm_re_projects_marketing",
    "crm_re_projects_sales",
    "crm_re_projects_kpi",
    "crm_re_projects_products",
    "crm_re_projects_risks",
    "crm_re_projects_budget",
)


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _slug_type_code(raw: str) -> str:
    s = str(raw or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:40]


def _seed_project_types(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) AS c FROM crm_re_project_types").fetchone()
    if n and int(n["c"]) > 0:
        return
    ts = _now_ts()
    for i, (code, name) in enumerate(DEFAULT_PROJECT_TYPE_LABELS.items()):
        conn.execute(
            """
            INSERT INTO crm_re_project_types (code, name, description, sort_order, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (code, name, "", (i + 1) * 10, ts, ts),
        )


def list_project_types(conn: sqlite3.Connection, *, include_inactive: bool = False) -> list[dict[str, Any]]:
    where = "" if include_inactive else " WHERE active = 1"
    rows = conn.execute(
        f"SELECT * FROM crm_re_project_types{where} ORDER BY sort_order ASC, name COLLATE NOCASE ASC, id ASC"
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["active"] = bool(int(d.get("active") or 0))
        usage = conn.execute(
            "SELECT COUNT(*) AS c FROM crm_re_projects WHERE lower(project_type) = lower(?)",
            (str(d.get("code") or ""),),
        ).fetchone()
        d["project_count"] = int(usage["c"]) if usage else 0
        out.append(d)
    return out


def project_type_label_map(conn: sqlite3.Connection, *, include_inactive: bool = False) -> dict[str, str]:
    return {str(t["code"]): str(t["name"]) for t in list_project_types(conn, include_inactive=include_inactive)}


def validate_project_type(conn: sqlite3.Connection, code: str, *, allow_inactive: bool = False) -> str:
    c = str(code or "").strip()
    if not c:
        raise ValueError("Thiếu loại BĐS.")

    def _lookup() -> sqlite3.Row | None:
        return conn.execute(
            "SELECT code, active FROM crm_re_project_types WHERE lower(code) = lower(?)",
            (c,),
        ).fetchone()

    row = _lookup()
    if not row:
        # Bảng loại BĐS rỗng (chưa seed / deployment cũ) → trang sẽ hiển thị các
        # loại mặc định, nhưng DB chưa có dòng tương ứng nên mọi giá trị đều bị
        # từ chối. Tự seed lại bộ mặc định rồi tra cứu lần nữa để khớp với UI.
        cnt = conn.execute("SELECT COUNT(*) AS c FROM crm_re_project_types").fetchone()
        if not cnt or int(cnt["c"]) == 0:
            _seed_project_types(conn)
            row = _lookup()
    if not row:
        raise ValueError("Loại BĐS không tồn tại.")
    if not allow_inactive and not int(row["active"] or 0):
        raise ValueError("Loại BĐS đang tắt — không thể gán cho dự án mới.")
    return str(row["code"])


def save_project_type(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    type_id: int | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    ts_val = ts or _now_ts()
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Thiếu tên loại BĐS.")
    description = str(payload.get("description") or "")[:2000]
    sort_order = int(payload.get("sort_order") or 0)
    prev = None
    if type_id:
        prev = conn.execute("SELECT * FROM crm_re_project_types WHERE id = ?", (int(type_id),)).fetchone()
        if not prev:
            raise ValueError("Không tìm thấy loại BĐS.")
        if "active" in payload:
            active = 1 if payload.get("active") in (True, 1, "1", "true", "yes") else 0
        else:
            active = int(prev["active"] or 0)
    else:
        active = 1 if payload.get("active", True) in (True, 1, "1", "true", "yes") else 0
    if type_id:
        assert prev is not None
        code = str(prev["code"])
        new_code = _slug_type_code(payload.get("code") or code)
        if new_code != code:
            dup = conn.execute(
                "SELECT id FROM crm_re_project_types WHERE lower(code)=lower(?) AND id<>?",
                (new_code, int(type_id)),
            ).fetchone()
            if dup:
                raise ValueError("Mã loại BĐS đã tồn tại.")
            used = conn.execute(
                "SELECT COUNT(*) AS c FROM crm_re_projects WHERE lower(project_type)=lower(?)",
                (code,),
            ).fetchone()
            if used and int(used["c"]) > 0:
                raise ValueError("Không đổi mã khi đã có dự án đang dùng loại này.")
            code = new_code
        conn.execute(
            """
            UPDATE crm_re_project_types SET
                code=?, name=?, description=?, sort_order=?, active=?, updated_at=?
            WHERE id=?
            """,
            (code[:40], name[:120], description, sort_order, active, ts_val, int(type_id)),
        )
        rid = int(type_id)
    else:
        code = _slug_type_code(payload.get("code") or name)
        if not code:
            raise ValueError("Mã loại BĐS không hợp lệ.")
        dup = conn.execute(
            "SELECT id FROM crm_re_project_types WHERE lower(code)=lower(?)",
            (code,),
        ).fetchone()
        if dup:
            raise ValueError("Mã loại BĐS đã tồn tại.")
        cur = conn.execute(
            """
            INSERT INTO crm_re_project_types (code, name, description, sort_order, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (code[:40], name[:120], description, sort_order, active, ts_val, ts_val),
        )
        rid = int(cur.lastrowid)
    rows = list_project_types(conn, include_inactive=True)
    row = next((r for r in rows if int(r["id"]) == rid), None)
    if row is None:
        raise ValueError("Không tìm thấy loại BĐS sau khi lưu.")
    return row


def delete_project_type(conn: sqlite3.Connection, type_id: int) -> None:
    row = conn.execute("SELECT code FROM crm_re_project_types WHERE id = ?", (int(type_id),)).fetchone()
    if not row:
        raise ValueError("Không tìm thấy loại BĐS.")
    code = str(row["code"])
    used = conn.execute(
        "SELECT COUNT(*) AS c FROM crm_re_projects WHERE lower(project_type)=lower(?)",
        (code,),
    ).fetchone()
    if used and int(used["c"]) > 0:
        raise ValueError(f"Không xóa được — còn {int(used['c'])} dự án đang dùng loại «{code}».")
    conn.execute("DELETE FROM crm_re_project_types WHERE id = ?", (int(type_id),))


def _merge_plan(stored: dict[str, Any], default: dict[str, Any]) -> dict[str, Any]:
    """Gộp JSON đã lưu với schema mặc định — tương thích khi bổ sung trường mới."""
    out = copy.deepcopy(default)
    for k, v in (stored or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            nested = copy.deepcopy(out[k])
            nested.update(v)
            out[k] = nested
        else:
            out[k] = copy.deepcopy(v) if isinstance(v, (dict, list)) else v
    return out


def default_business_plan() -> dict[str, Any]:
    return {
        "vision": "",
        "mission": "",
        "strategic_goals": [],
        "value_proposition": "",
        "product_positioning": "",
        "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        "target_market": "",
        "competitive_advantage": "",
        "market_analysis": {
            "market_size_notes": "",
            "demand_supply_notes": "",
            "price_trend_notes": "",
            "competitors": [],
        },
        "pestel": {
            "political": "",
            "economic": "",
            "social": "",
            "technology": "",
            "environment": "",
            "legal": "",
        },
        "customer_analysis": {
            "primary_persona": "",
            "secondary_persona": "",
            "buyer_journey": "",
            "decision_factors": [],
        },
        "revenue_target_vnd": 0,
        "cost_structure_notes": "",
        "financial_plan": {
            "total_investment_vnd": 0,
            "land_cost_vnd": 0,
            "construction_cost_vnd": 0,
            "marketing_cost_vnd": 0,
            "sales_cost_vnd": 0,
            "profit_margin_target_pct": 0,
            "cash_flow_notes": "",
        },
        "break_even_units": 0,
        "break_even_month": "",
        "milestones": [],
        "gantt_phases": [],
        "approval_status": "draft",
        "notes": "",
    }


def default_marketing_plan() -> dict[str, Any]:
    return {
        "objectives": [],
        "stp": {
            "segmentation_criteria": "",
            "primary_target": "",
            "secondary_target": "",
            "differentiation": "",
        },
        "target_segments": [],
        "positioning": "",
        "key_messages": [],
        "brand_guidelines": "",
        "marketing_mix": {
            "product_notes": "",
            "price_notes": "",
            "place_notes": "",
            "promotion_notes": "",
        },
        "competitor_marketing": "",
        "funnel": {
            "awareness_target": 0,
            "mql_target_monthly": 0,
            "site_visit_target_monthly": 0,
            "booking_target_monthly": 0,
            "conversion_lead_to_visit_pct": 0,
            "conversion_visit_to_book_pct": 0,
        },
        "channels": [],
        "budget_breakdown": [],
        "content_themes": [],
        "creative_direction": "",
        "campaigns": [],
        "lead_target_monthly": 0,
        "cpl_target_vnd": 0,
        "budget_total_vnd": 0,
        "kpi_marketing": {
            "reach_target": 0,
            "engagement_rate_pct": 0,
            "cac_target_vnd": 0,
            "roi_target_pct": 0,
        },
        "launch_timeline": [],
        "approval_status": "draft",
        "notes": "",
    }


def default_sales_plan() -> dict[str, Any]:
    return {
        "revenue_target_vnd": 0,
        "units_target": 0,
        "avg_price_target_vnd": 0,
        "monthly_targets": [],
        "pricing_strategy": "",
        "commission_policy": "",
        "channel_mix": {"direct_pct": 60, "agent_pct": 30, "online_pct": 10},
        "sales_process": [],
        "team_structure": [],
        "incentive_programs": [],
        "approval_status": "draft",
        "notes": "",
    }


def ensure_re_projects_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            project_type TEXT NOT NULL DEFAULT 'can_ho',
            status TEXT NOT NULL DEFAULT 'planning',
            location_address TEXT NOT NULL DEFAULT '',
            district TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            developer_name TEXT NOT NULL DEFAULT '',
            investor_name TEXT NOT NULL DEFAULT '',
            total_land_area_m2 REAL,
            total_units INTEGER NOT NULL DEFAULT 0,
            sold_units INTEGER NOT NULL DEFAULT 0,
            revenue_target_vnd INTEGER NOT NULL DEFAULT 0,
            start_date TEXT NOT NULL DEFAULT '',
            presale_date TEXT NOT NULL DEFAULT '',
            handover_date TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            business_plan_json TEXT NOT NULL DEFAULT '{}',
            marketing_plan_json TEXT NOT NULL DEFAULT '{}',
            sales_plan_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_re_projects_status ON crm_re_projects(status, updated_at)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_re_project_types_code "
        "ON crm_re_project_types(lower(trim(code))) WHERE trim(code) != ''"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_re_project_types_active "
        "ON crm_re_project_types(active, sort_order)"
    )
    _seed_project_types(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            unit_code TEXT NOT NULL DEFAULT '',
            tower TEXT NOT NULL DEFAULT '',
            floor TEXT NOT NULL DEFAULT '',
            product_type TEXT NOT NULL DEFAULT '',
            area_m2 REAL,
            bedrooms INTEGER,
            direction TEXT NOT NULL DEFAULT '',
            view_type TEXT NOT NULL DEFAULT '',
            list_price_vnd INTEGER NOT NULL DEFAULT 0,
            net_price_vnd INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'available',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_re_products_project ON crm_re_project_products(project_id, status)"
    )
    _ensure_re_product_extended_columns(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_re_products_line ON crm_re_project_products(project_id, product_line, zone)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_kpis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            category TEXT NOT NULL DEFAULT 'sales',
            metric_name TEXT NOT NULL,
            target_value REAL NOT NULL DEFAULT 0,
            actual_value REAL NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT '',
            period_month TEXT NOT NULL DEFAULT '',
            weight_pct REAL NOT NULL DEFAULT 0,
            owner_name TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    _ensure_re_kpi_extended_columns(conn)
    seed_re_kpi_metrics(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            category TEXT NOT NULL DEFAULT 'market',
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            probability_pct REAL NOT NULL DEFAULT 0,
            impact_pct REAL NOT NULL DEFAULT 0,
            risk_level TEXT NOT NULL DEFAULT 'medium',
            mitigation TEXT NOT NULL DEFAULT '',
            owner_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            due_date TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_budget_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            category TEXT NOT NULL DEFAULT 'revenue',
            line_item TEXT NOT NULL,
            period_month TEXT NOT NULL DEFAULT '',
            planned_vnd INTEGER NOT NULL DEFAULT 0,
            actual_vnd INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    if conn.execute("SELECT COUNT(*) AS c FROM crm_re_projects").fetchone()["c"] == 0:
        ts = _now_ts()
        conn.execute(
            """
            INSERT INTO crm_re_projects (
                code, name, project_type, status, location_address, district, city,
                developer_name, total_units, revenue_target_vnd,
                business_plan_json, marketing_plan_json, sales_plan_json,
                description, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "DA-MAU",
                "Dự án mẫu — Green City Tower",
                "can_ho",
                "planning",
                "123 Nguyễn Văn Linh",
                "q.7",
                "TP.HCM",
                "PTT Development",
                500,
                500_000_000_000,
                json.dumps(default_business_plan(), ensure_ascii=False),
                json.dumps(default_marketing_plan(), ensure_ascii=False),
                json.dumps(default_sales_plan(), ensure_ascii=False),
                "Dự án mẫu để tham khảo cấu trúc 7 hạng mục quản lý.",
                ts,
                ts,
            ),
        )
    from crm_re_price_lists import ensure_price_lists_schema
    from crm_re_project_accounting import ensure_accounting_schema

    ensure_price_lists_schema(conn)
    ensure_accounting_schema(conn)


def _parse_json(raw: str, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        obj = json.loads(raw or "{}")
        return obj if isinstance(obj, dict) else copy.deepcopy(fallback)
    except json.JSONDecodeError:
        return copy.deepcopy(fallback)


def _project_row_to_dict(row: sqlite3.Row, *, type_labels: dict[str, str] | None = None) -> dict[str, Any]:
    d = dict(row)
    bp = _merge_plan(_parse_json(str(d.get("business_plan_json") or ""), default_business_plan()), default_business_plan())
    mp = _merge_plan(_parse_json(str(d.get("marketing_plan_json") or ""), default_marketing_plan()), default_marketing_plan())
    sp = _merge_plan(_parse_json(str(d.get("sales_plan_json") or ""), default_sales_plan()), default_sales_plan())
    pt = str(d.get("project_type") or "can_ho")
    labels = type_labels or DEFAULT_PROJECT_TYPE_LABELS
    st = str(d.get("status") or "planning")
    total = int(d.get("total_units") or 0)
    sold = int(d.get("sold_units") or 0)
    return {
        "id": int(d["id"]),
        "code": str(d.get("code") or ""),
        "name": str(d.get("name") or ""),
        "project_type": pt,
        "project_type_label": labels.get(pt, pt),
        "status": st,
        "status_label": PROJECT_STATUS_LABELS.get(st, st),
        "location_address": str(d.get("location_address") or ""),
        "district": str(d.get("district") or ""),
        "city": str(d.get("city") or ""),
        "developer_name": str(d.get("developer_name") or ""),
        "investor_name": str(d.get("investor_name") or ""),
        "total_land_area_m2": d.get("total_land_area_m2"),
        "total_units": total,
        "sold_units": sold,
        "sell_through_pct": round(sold / total * 100, 1) if total > 0 else 0,
        "revenue_target_vnd": int(d.get("revenue_target_vnd") or 0),
        "start_date": str(d.get("start_date") or ""),
        "presale_date": str(d.get("presale_date") or ""),
        "handover_date": str(d.get("handover_date") or ""),
        "description": str(d.get("description") or ""),
        "notes": str(d.get("notes") or ""),
        "business_plan": bp,
        "marketing_plan": mp,
        "sales_plan": sp,
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
    }


def list_projects(conn: sqlite3.Connection, *, q: str = "") -> list[dict[str, Any]]:
    labels = project_type_label_map(conn, include_inactive=True)
    params: list[Any] = []
    where = ""
    if q.strip():
        like = f"%{q.strip()}%"
        where = " WHERE name LIKE ? OR code LIKE ? OR district LIKE ? OR city LIKE ?"
        params = [like, like, like, like]
    rows = conn.execute(
        f"SELECT * FROM crm_re_projects{where} ORDER BY updated_at DESC, id DESC",
        params,
    ).fetchall()
    return [_project_row_to_dict(r, type_labels=labels) for r in rows]


def fetch_project(conn: sqlite3.Connection, project_id: int) -> dict[str, Any] | None:
    labels = project_type_label_map(conn, include_inactive=True)
    row = conn.execute("SELECT * FROM crm_re_projects WHERE id = ?", (int(project_id),)).fetchone()
    return _project_row_to_dict(row, type_labels=labels) if row else None


def create_project(conn: sqlite3.Connection, payload: dict[str, Any], *, ts: str | None = None) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Thiếu tên dự án.")
    ts_val = ts or _now_ts()
    pt = validate_project_type(conn, str(payload.get("project_type") or "can_ho"))
    st = str(payload.get("status") or "planning")
    if st not in PROJECT_STATUSES:
        st = "planning"
    cur = conn.execute(
        """
        INSERT INTO crm_re_projects (
            code, name, project_type, status, location_address, district, city,
            developer_name, investor_name, total_land_area_m2, total_units, sold_units,
            revenue_target_vnd, start_date, presale_date, handover_date,
            description, notes, business_plan_json, marketing_plan_json, sales_plan_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload.get("code") or "")[:40],
            name[:240],
            pt,
            st,
            str(payload.get("location_address") or "")[:500],
            str(payload.get("district") or "")[:120],
            str(payload.get("city") or "")[:120],
            str(payload.get("developer_name") or "")[:240],
            str(payload.get("investor_name") or "")[:240],
            payload.get("total_land_area_m2"),
            int(payload.get("total_units") or 0),
            int(payload.get("sold_units") or 0),
            int(payload.get("revenue_target_vnd") or 0),
            str(payload.get("start_date") or "")[:10],
            str(payload.get("presale_date") or "")[:10],
            str(payload.get("handover_date") or "")[:10],
            str(payload.get("description") or "")[:4000],
            str(payload.get("notes") or "")[:4000],
            json.dumps(payload.get("business_plan") or default_business_plan(), ensure_ascii=False),
            json.dumps(payload.get("marketing_plan") or default_marketing_plan(), ensure_ascii=False),
            json.dumps(payload.get("sales_plan") or default_sales_plan(), ensure_ascii=False),
            ts_val,
            ts_val,
        ),
    )
    pid = int(cur.lastrowid)
    out = fetch_project(conn, pid)
    assert out is not None
    return out


def update_project(conn: sqlite3.Connection, project_id: int, payload: dict[str, Any], *, ts: str | None = None) -> dict[str, Any]:
    prev = fetch_project(conn, project_id)
    if prev is None:
        raise ValueError("Không tìm thấy dự án.")
    ts_val = ts or _now_ts()
    merged = {**prev, **payload}
    if "project_type" in payload:
        pt = validate_project_type(conn, str(payload.get("project_type") or prev["project_type"]), allow_inactive=True)
    else:
        pt = str(prev["project_type"])
    st = str(merged.get("status") or prev["status"])
    if st not in PROJECT_STATUSES:
        st = prev["status"]
    bp = payload.get("business_plan") if "business_plan" in payload else prev["business_plan"]
    mp = payload.get("marketing_plan") if "marketing_plan" in payload else prev["marketing_plan"]
    sp = payload.get("sales_plan") if "sales_plan" in payload else prev["sales_plan"]
    conn.execute(
        """
        UPDATE crm_re_projects SET
            code=?, name=?, project_type=?, status=?,
            location_address=?, district=?, city=?,
            developer_name=?, investor_name=?, total_land_area_m2=?,
            total_units=?, sold_units=?, revenue_target_vnd=?,
            start_date=?, presale_date=?, handover_date=?,
            description=?, notes=?,
            business_plan_json=?, marketing_plan_json=?, sales_plan_json=?,
            updated_at=?
        WHERE id=?
        """,
        (
            str(merged.get("code") or "")[:40],
            str(merged.get("name") or "")[:240],
            pt,
            st,
            str(merged.get("location_address") or "")[:500],
            str(merged.get("district") or "")[:120],
            str(merged.get("city") or "")[:120],
            str(merged.get("developer_name") or "")[:240],
            str(merged.get("investor_name") or "")[:240],
            merged.get("total_land_area_m2"),
            int(merged.get("total_units") or 0),
            int(merged.get("sold_units") or 0),
            int(merged.get("revenue_target_vnd") or 0),
            str(merged.get("start_date") or "")[:10],
            str(merged.get("presale_date") or "")[:10],
            str(merged.get("handover_date") or "")[:10],
            str(merged.get("description") or "")[:4000],
            str(merged.get("notes") or "")[:4000],
            json.dumps(bp, ensure_ascii=False),
            json.dumps(mp, ensure_ascii=False),
            json.dumps(sp, ensure_ascii=False),
            ts_val,
            int(project_id),
        ),
    )
    out = fetch_project(conn, project_id)
    assert out is not None
    return out


def delete_project(conn: sqlite3.Connection, project_id: int) -> None:
    conn.execute("DELETE FROM crm_re_projects WHERE id = ?", (int(project_id),))


def _ensure_re_product_extended_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_re_project_products)")}
    extra: list[tuple[str, str]] = [
        ("product_line", "ALTER TABLE crm_re_project_products ADD COLUMN product_line TEXT NOT NULL DEFAULT ''"),
        ("zone", "ALTER TABLE crm_re_project_products ADD COLUMN zone TEXT NOT NULL DEFAULT ''"),
        ("typology", "ALTER TABLE crm_re_project_products ADD COLUMN typology TEXT NOT NULL DEFAULT ''"),
        ("is_corner", "ALTER TABLE crm_re_project_products ADD COLUMN is_corner INTEGER NOT NULL DEFAULT 0"),
        ("sales_staff_id", "ALTER TABLE crm_re_project_products ADD COLUMN sales_staff_id INTEGER"),
        (
            "hold_lead_id",
            "ALTER TABLE crm_re_project_products ADD COLUMN hold_lead_id INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL",
        ),
        ("hold_at", "ALTER TABLE crm_re_project_products ADD COLUMN hold_at TEXT NOT NULL DEFAULT ''"),
        ("price_batch", "ALTER TABLE crm_re_project_products ADD COLUMN price_batch TEXT NOT NULL DEFAULT ''"),
    ]
    for col, ddl in extra:
        if col not in cols:
            try:
                conn.execute(ddl)
            except sqlite3.Error:
                pass


def _ensure_re_kpi_extended_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_re_project_kpis)")}
    extra: list[tuple[str, str]] = [
        ("owner_staff_id", "ALTER TABLE crm_re_project_kpis ADD COLUMN owner_staff_id INTEGER"),
        ("track_status", "ALTER TABLE crm_re_project_kpis ADD COLUMN track_status TEXT NOT NULL DEFAULT 'active'"),
        ("metric_code", "ALTER TABLE crm_re_project_kpis ADD COLUMN metric_code TEXT NOT NULL DEFAULT ''"),
        ("metric_id", "ALTER TABLE crm_re_project_kpis ADD COLUMN metric_id INTEGER"),
        ("staff_kpi_id", "ALTER TABLE crm_re_project_kpis ADD COLUMN staff_kpi_id INTEGER"),
    ]
    for col, ddl in extra:
        if col not in cols:
            try:
                conn.execute(ddl)
            except sqlite3.Error:
                pass


def seed_re_kpi_metrics(conn: sqlite3.Connection) -> None:
    """Đưa chỉ tiêu BĐS vào danh mục KPI nhân sự CRM (crm_kpi_metrics)."""
    try:
        conn.execute("SELECT 1 FROM crm_kpi_metrics LIMIT 1")
    except sqlite3.Error:
        return
    ts_d = datetime.now().strftime("%Y-%m-%d")
    ts = _now_ts()
    for i, tpl in enumerate(KPI_METRIC_TEMPLATES):
        code = str(tpl.get("crm_code") or f"RE_{str(tpl.get('code') or '').upper()}").strip()
        if not code:
            continue
        name = str(tpl.get("metric_name") or "")
        unit = str(tpl.get("unit") or "")
        desc = f"Chỉ tiêu dự án BĐS — {name}"
        existing = conn.execute(
            "SELECT id FROM crm_kpi_metrics WHERE lower(trim(code)) = lower(?)",
            (code,),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO crm_kpi_metrics (
                code, name, unit, description, sort_order, active,
                created_at, updated_at, higher_is_better, warn_ratio
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1, 0.9)
            """,
            (code, name, unit, desc, 100 + i * 10, ts_d, ts),
        )


def _parse_period_month(period_month: str) -> tuple[int | None, int | None]:
    raw = str(period_month or "").strip()
    m = re.match(r"^(\d{4})-(\d{1,2})$", raw)
    if not m:
        return None, None
    year = int(m.group(1))
    month = int(m.group(2))
    if month < 1 or month > 12 or year < 2000 or year > 2100:
        return None, None
    return year, month


def _map_re_track_to_staff_status(track: str) -> str:
    return {
        "draft": "draft",
        "active": "at_risk",
        "completed": "achieved",
        "cancelled": "missed",
    }.get(str(track or "active"), "draft")


def _map_staff_to_re_track_status(staff_status: str) -> str:
    return {
        "draft": "draft",
        "at_risk": "active",
        "achieved": "completed",
        "missed": "cancelled",
    }.get(str(staff_status or "draft"), "active")


def _resolve_crm_metric(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    metric_name: str,
    unit: str,
) -> tuple[int | None, str, str, str]:
    """Trả về metric_id, metric_code, metric_name, unit từ payload hoặc crm_kpi_metrics."""
    metric_id: int | None = None
    raw_mid = payload.get("metric_id")
    if raw_mid is not None and str(raw_mid).strip() != "":
        try:
            metric_id = int(raw_mid)
        except (TypeError, ValueError):
            metric_id = None
    metric_code = str(payload.get("metric_code") or "").strip()
    resolved_name = metric_name
    resolved_unit = unit
    try:
        if metric_id and metric_id > 0:
            row = conn.execute(
                "SELECT id, code, name, unit FROM crm_kpi_metrics WHERE id = ? AND active = 1",
                (metric_id,),
            ).fetchone()
            if row:
                return int(row["id"]), str(row["code"]), str(row["name"]), str(row["unit"] or unit)
        codes_to_try: list[str] = []
        if metric_code:
            codes_to_try.extend([metric_code, metric_code.upper(), f"RE_{metric_code.upper()}"])
        for tpl in KPI_METRIC_TEMPLATES:
            if metric_code and tpl.get("code") == metric_code:
                codes_to_try.append(str(tpl.get("crm_code") or ""))
            if metric_name and tpl.get("metric_name") == metric_name:
                codes_to_try.append(str(tpl.get("crm_code") or ""))
        for code_try in codes_to_try:
            if not code_try:
                continue
            row = conn.execute(
                """
                SELECT id, code, name, unit FROM crm_kpi_metrics
                WHERE lower(trim(code)) = lower(?) AND active = 1
                """,
                (code_try,),
            ).fetchone()
            if row:
                return int(row["id"]), str(row["code"]), str(row["name"]), str(row["unit"] or unit)
    except sqlite3.Error:
        pass
    return None, metric_code[:40], resolved_name, resolved_unit


def _sync_kpi_to_staff_module(
    conn: sqlite3.Connection,
    kpi_id: int,
    project_id: int,
    *,
    ts: str | None = None,
) -> bool:
    row = conn.execute(
        "SELECT * FROM crm_re_project_kpis WHERE id = ? AND project_id = ?",
        (int(kpi_id), int(project_id)),
    ).fetchone()
    if row is None:
        return False
    d = dict(row)
    staff_id = int(d.get("owner_staff_id") or 0)
    metric_id = int(d.get("metric_id") or 0)
    if not metric_id:
        mid, code, _, _ = _resolve_crm_metric(
            conn,
            d,
            metric_name=str(d.get("metric_name") or ""),
            unit=str(d.get("unit") or ""),
        )
        metric_id = int(mid or 0)
        if metric_id:
            conn.execute(
                "UPDATE crm_re_project_kpis SET metric_id=?, metric_code=? WHERE id=?",
                (metric_id, code, int(kpi_id)),
            )
    if staff_id <= 0 or metric_id <= 0:
        return False
    year, month = _parse_period_month(str(d.get("period_month") or ""))
    if year is None or month is None:
        return False
    proj = fetch_project(conn, project_id)
    proj_name = str((proj or {}).get("name") or "")
    note = str(d.get("notes") or "").strip()
    sync_note = f"[Dự án BĐS: {proj_name} (#{project_id})] {note}".strip()[:2000]
    staff_status = _map_re_track_to_staff_status(str(d.get("track_status") or "active"))
    ts_val = ts or _now_ts()
    ts_d = datetime.now().strftime("%Y-%m-%d")
    try:
        conn.execute(
            """
            INSERT INTO crm_staff_kpi (
                staff_id, metric_id, year, month,
                target_value, actual_value, status, note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(staff_id, metric_id, year, month) DO UPDATE SET
                target_value = excluded.target_value,
                actual_value = excluded.actual_value,
                status = excluded.status,
                note = excluded.note,
                updated_at = excluded.updated_at
            """,
            (
                staff_id,
                metric_id,
                year,
                month,
                float(d.get("target_value") or 0),
                float(d.get("actual_value") or 0),
                staff_status,
                sync_note,
                ts_d,
                ts_val,
            ),
        )
        sk = conn.execute(
            """
            SELECT id FROM crm_staff_kpi
            WHERE staff_id = ? AND metric_id = ? AND year = ? AND month = ?
            """,
            (staff_id, metric_id, year, month),
        ).fetchone()
        if sk:
            conn.execute(
                "UPDATE crm_re_project_kpis SET staff_kpi_id = ?, metric_id = ?, updated_at = ? WHERE id = ?",
                (int(sk["id"]), metric_id, ts_val, int(kpi_id)),
            )
    except sqlite3.Error:
        return False
    return True


def sync_project_kpis_to_staff(conn: sqlite3.Connection, project_id: int, *, ts: str | None = None) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT id FROM crm_re_project_kpis WHERE project_id = ? ORDER BY id",
        (int(project_id),),
    ).fetchall()
    synced = 0
    skipped = 0
    for r in rows:
        if _sync_kpi_to_staff_module(conn, int(r["id"]), project_id, ts=ts):
            synced += 1
        else:
            skipped += 1
    return {"synced": synced, "skipped": skipped, "total": len(rows)}


def pull_project_kpis_from_staff(conn: sqlite3.Connection, project_id: int, *, ts: str | None = None) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT * FROM crm_re_project_kpis WHERE project_id = ? AND staff_kpi_id IS NOT NULL",
        (int(project_id),),
    ).fetchall()
    updated = 0
    ts_val = ts or _now_ts()
    for r in rows:
        sk = conn.execute(
            "SELECT actual_value, status FROM crm_staff_kpi WHERE id = ?",
            (int(r["staff_kpi_id"]),),
        ).fetchone()
        if sk is None:
            continue
        actual = sk["actual_value"]
        track = _map_staff_to_re_track_status(str(sk["status"] or "draft"))
        conn.execute(
            """
            UPDATE crm_re_project_kpis
            SET actual_value = ?, track_status = ?, updated_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (
                float(actual or 0),
                track,
                ts_val,
                int(r["id"]),
                int(project_id),
            ),
        )
        updated += 1
    return {"updated": updated, "total_linked": len(rows)}


def list_crm_kpi_metrics(conn: sqlite3.Connection, *, re_only: bool = False) -> list[dict[str, Any]]:
    try:
        if re_only:
            rows = conn.execute(
                """
                SELECT * FROM crm_kpi_metrics
                WHERE active = 1 AND code LIKE 'RE_%'
                ORDER BY sort_order ASC, name COLLATE NOCASE ASC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM crm_kpi_metrics
                WHERE active = 1
                ORDER BY sort_order ASC, name COLLATE NOCASE ASC
                """
            ).fetchall()
    except sqlite3.Error:
        return []
    return [_child_row(r) for r in rows]


def _staff_lookup(conn: sqlite3.Connection, staff_ids: set[int]) -> dict[int, dict[str, Any]]:
    ids = sorted({int(i) for i in staff_ids if int(i or 0) > 0})
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    try:
        rows = conn.execute(
            f"SELECT id, name, job_title, department FROM crm_staff WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
    except sqlite3.Error:
        rows = conn.execute(
            f"SELECT id, name FROM crm_staff WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        return {int(r["id"]): {"name": r["name"], "job_title": "", "department": ""} for r in rows}
    return {int(r["id"]): dict(r) for r in rows}


def _resolve_owner_staff(conn: sqlite3.Connection, payload: dict[str, Any]) -> tuple[int | None, str]:
    raw_id = payload.get("owner_staff_id")
    staff_id: int | None = None
    if raw_id is not None and str(raw_id).strip() != "":
        try:
            staff_id = int(raw_id)
        except (TypeError, ValueError):
            staff_id = None
    owner_name = str(payload.get("owner_name") or "").strip()
    if staff_id and staff_id > 0:
        row = conn.execute(
            "SELECT name FROM crm_staff WHERE id = ?",
            (staff_id,),
        ).fetchone()
        if row:
            owner_name = str(row["name"] or owner_name)
    return staff_id if staff_id and staff_id > 0 else None, owner_name[:120]


def _enrich_product_row(d: dict[str, Any], staff_map: dict[int, dict[str, Any]] | None = None) -> dict[str, Any]:
    line = str(d.get("product_line") or "")
    typo = str(d.get("typology") or "")
    d["product_line_label"] = PRODUCT_LINE_LABELS.get(line, line or "—")
    d["typology_label"] = PRODUCT_TYPOLOGY_LABELS.get(typo, typo or "—")
    sid = int(d.get("sales_staff_id") or 0)
    if staff_map and sid in staff_map:
        st = staff_map[sid]
        d["sales_staff_name"] = st.get("name") or ""
        d["sales_staff_title"] = st.get("job_title") or ""
    else:
        d["sales_staff_name"] = ""
        d["sales_staff_title"] = ""
    return d


def compute_product_inventory_stats(products: list[dict[str, Any]]) -> dict[str, Any]:
    by_line: dict[str, dict[str, Any]] = {}
    by_zone: dict[str, dict[str, Any]] = {}
    by_typology: dict[str, dict[str, Any]] = {}
    by_status: dict[str, int] = {}
    total_value = 0
    available_value = 0
    for p in products:
        line = str(p.get("product_line") or "other") or "other"
        zone = str(p.get("zone") or "").strip() or "Chưa phân khu"
        typo = str(p.get("typology") or "other") or "other"
        st = str(p.get("status") or "available")
        price = int(p.get("list_price_vnd") or 0)
        total_value += price
        if st == "available":
            available_value += price
        by_status[st] = by_status.get(st, 0) + 1
        for bucket, key, labels in (
            (by_line, line, PRODUCT_LINE_LABELS),
            (by_zone, zone, None),
            (by_typology, typo, PRODUCT_TYPOLOGY_LABELS),
        ):
            if key not in bucket:
                label = labels.get(key, key) if labels else key
                bucket[key] = {
                    "key": key,
                    "label": label,
                    "total": 0,
                    "available": 0,
                    "sold": 0,
                    "booked": 0,
                    "list_value_vnd": 0,
                }
            bucket[key]["total"] += 1
            if st == "available":
                bucket[key]["available"] += 1
            elif st == "sold":
                bucket[key]["sold"] += 1
            elif st in ("booked", "hold"):
                bucket[key]["booked"] += 1
            bucket[key]["list_value_vnd"] += price
    return {
        "total": len(products),
        "available": sum(1 for p in products if p.get("status") == "available"),
        "sold": sum(1 for p in products if p.get("status") == "sold"),
        "booked": sum(1 for p in products if p.get("status") in ("booked", "hold")),
        "total_list_value_vnd": total_value,
        "available_list_value_vnd": available_value,
        "by_product_line": sorted(by_line.values(), key=lambda x: (-x["total"], x["label"])),
        "by_zone": sorted(by_zone.values(), key=lambda x: (-x["total"], x["label"])),
        "by_typology": sorted(by_typology.values(), key=lambda x: (-x["total"], x["label"])),
        "by_status": by_status,
    }


def compute_kpi_board_stats(kpis: list[dict[str, Any]]) -> dict[str, Any]:
    by_staff: dict[str, dict[str, Any]] = {}
    by_category: dict[str, dict[str, Any]] = {}
    weight_total = 0.0
    achievement_sum = 0.0
    with_owner = 0
    for k in kpis:
        cat = str(k.get("category") or "sales")
        sid = int(k.get("owner_staff_id") or 0)
        owner_key = str(sid) if sid > 0 else str(k.get("owner_name") or "").strip() or "unassigned"
        owner_label = str(k.get("owner_display") or k.get("owner_name") or "Chưa gán")
        if sid > 0 or str(k.get("owner_name") or "").strip():
            with_owner += 1
        weight = float(k.get("weight_pct") or 0)
        ach = float(k.get("achievement_pct") or 0)
        weight_total += weight
        achievement_sum += ach
        if owner_key not in by_staff:
            by_staff[owner_key] = {
                "owner_key": owner_key,
                "owner_staff_id": sid or None,
                "owner_name": owner_label,
                "count": 0,
                "weight_pct": 0.0,
                "avg_achievement_pct": 0.0,
                "_ach_sum": 0.0,
            }
        by_staff[owner_key]["count"] += 1
        by_staff[owner_key]["weight_pct"] += weight
        by_staff[owner_key]["_ach_sum"] += ach
        if cat not in by_category:
            by_category[cat] = {
                "category": cat,
                "label": KPI_CATEGORY_LABELS.get(cat, cat),
                "count": 0,
                "avg_achievement_pct": 0.0,
                "_ach_sum": 0.0,
            }
        by_category[cat]["count"] += 1
        by_category[cat]["_ach_sum"] += ach
    staff_rows = []
    for row in by_staff.values():
        cnt = row["count"] or 1
        row["avg_achievement_pct"] = round(row.pop("_ach_sum") / cnt, 1)
        row["weight_pct"] = round(row["weight_pct"], 1)
        staff_rows.append(row)
    cat_rows = []
    for row in by_category.values():
        cnt = row["count"] or 1
        row["avg_achievement_pct"] = round(row.pop("_ach_sum") / cnt, 1)
        cat_rows.append(row)
    n = len(kpis) or 1
    return {
        "total": len(kpis),
        "with_owner_count": with_owner,
        "weight_total_pct": round(weight_total, 1),
        "avg_achievement_pct": round(achievement_sum / n, 1) if kpis else 0.0,
        "by_staff": sorted(staff_rows, key=lambda x: (-x["count"], x["owner_name"])),
        "by_category": sorted(cat_rows, key=lambda x: (-x["count"], x["label"])),
    }


def _child_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def list_products(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_re_project_products WHERE project_id = ? ORDER BY zone, product_line, tower, unit_code",
        (int(project_id),),
    ).fetchall()
    staff_ids = {int(r["sales_staff_id"]) for r in rows if r["sales_staff_id"]}
    staff_map = _staff_lookup(conn, staff_ids)
    out = []
    for r in rows:
        d = _child_row(r)
        st = str(d.get("status") or "available")
        d["status_label"] = PRODUCT_STATUS_LABELS.get(st, st)
        _enrich_product_row(d, staff_map)
        out.append(d)
    return out


def save_product(conn: sqlite3.Connection, project_id: int, payload: dict[str, Any], *, product_id: int | None = None, ts: str | None = None) -> dict[str, Any]:
    ts_val = ts or _now_ts()
    st = str(payload.get("status") or "available")
    if st not in PRODUCT_STATUSES:
        st = "available"
    line = str(payload.get("product_line") or "")
    if line and line not in PRODUCT_LINES:
        line = "other"
    typo = str(payload.get("typology") or "")
    if typo and typo not in PRODUCT_TYPOLOGIES:
        typo = "other"
    sales_staff_id: int | None = None
    raw_sid = payload.get("sales_staff_id")
    if raw_sid is not None and str(raw_sid).strip() != "":
        try:
            sales_staff_id = int(raw_sid)
        except (TypeError, ValueError):
            sales_staff_id = None
    if sales_staff_id is not None and sales_staff_id <= 0:
        sales_staff_id = None
    is_corner = 1 if payload.get("is_corner") in (1, True, "1", "true", "on") else 0
    fields = (
        str(payload.get("unit_code") or "")[:40],
        str(payload.get("tower") or "")[:40],
        str(payload.get("floor") or "")[:20],
        line[:40],
        str(payload.get("zone") or "")[:60],
        typo[:40],
        is_corner,
        sales_staff_id,
        str(payload.get("product_type") or "")[:80],
        payload.get("area_m2"),
        payload.get("bedrooms"),
        str(payload.get("direction") or "")[:40],
        str(payload.get("view_type") or "")[:80],
        int(payload.get("list_price_vnd") or 0),
        int(payload.get("net_price_vnd") or 0),
        st,
        str(payload.get("notes") or "")[:2000],
        str(payload.get("price_batch") or "")[:80],
        ts_val,
    )
    if product_id:
        conn.execute(
            """
            UPDATE crm_re_project_products SET
                unit_code=?, tower=?, floor=?, product_line=?, zone=?, typology=?, is_corner=?,
                sales_staff_id=?, product_type=?, area_m2=?, bedrooms=?,
                direction=?, view_type=?, list_price_vnd=?, net_price_vnd=?, status=?, notes=?, price_batch=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (*fields, int(product_id), int(project_id)),
        )
        rid = int(product_id)
    else:
        cur = conn.execute(
            """
            INSERT INTO crm_re_project_products (
                project_id, unit_code, tower, floor, product_line, zone, typology, is_corner,
                sales_staff_id, product_type, area_m2, bedrooms,
                direction, view_type, list_price_vnd, net_price_vnd, status, notes, price_batch, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(project_id),
                *fields[:-1],
                ts_val,
                fields[-1],
            ),
        )
        rid = int(cur.lastrowid)
    row = conn.execute("SELECT * FROM crm_re_project_products WHERE id = ?", (rid,)).fetchone()
    assert row is not None
    d = _child_row(row)
    d["status_label"] = PRODUCT_STATUS_LABELS.get(str(d.get("status")), "")
    staff_map = _staff_lookup(conn, {int(d.get("sales_staff_id") or 0)})
    _enrich_product_row(d, staff_map)
    return d


def delete_product(conn: sqlite3.Connection, project_id: int, product_id: int) -> None:
    conn.execute(
        "DELETE FROM crm_re_project_products WHERE id = ? AND project_id = ?",
        (int(product_id), int(project_id)),
    )


def list_kpis(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_re_project_kpis WHERE project_id = ? ORDER BY period_month DESC, owner_staff_id, id",
        (int(project_id),),
    ).fetchall()
    staff_ids = {int(r["owner_staff_id"]) for r in rows if r["owner_staff_id"]}
    staff_map = _staff_lookup(conn, staff_ids)
    out = []
    for r in rows:
        d = _child_row(r)
        cat = str(d.get("category") or "")
        d["category_label"] = KPI_CATEGORY_LABELS.get(cat, cat)
        tgt = float(d.get("target_value") or 0)
        act = float(d.get("actual_value") or 0)
        d["achievement_pct"] = round(act / tgt * 100, 1) if tgt > 0 else 0
        tr = str(d.get("track_status") or "active")
        if tr not in KPI_TRACK_STATUSES:
            tr = "active"
        d["track_status"] = tr
        d["track_status_label"] = KPI_TRACK_STATUS_LABELS.get(tr, tr)
        sid = int(d.get("owner_staff_id") or 0)
        if sid and sid in staff_map:
            st = staff_map[sid]
            d["owner_display"] = str(st.get("name") or d.get("owner_name") or "")
            d["owner_job_title"] = str(st.get("job_title") or "")
            d["owner_department"] = str(st.get("department") or "")
        else:
            d["owner_display"] = str(d.get("owner_name") or "")
            d["owner_job_title"] = ""
            d["owner_department"] = ""
        sk_id = int(d.get("staff_kpi_id") or 0)
        d["synced_to_staff"] = sk_id > 0
        if sk_id > 0:
            sk = conn.execute(
                "SELECT actual_value, status FROM crm_staff_kpi WHERE id = ?",
                (sk_id,),
            ).fetchone()
            if sk is not None:
                d["staff_kpi_status"] = str(sk["status"] or "")
                if sk["actual_value"] is not None:
                    d["staff_kpi_actual"] = float(sk["actual_value"])
        out.append(d)
    return out


def save_kpi(conn: sqlite3.Connection, project_id: int, payload: dict[str, Any], *, kpi_id: int | None = None, ts: str | None = None) -> dict[str, Any]:
    ts_val = ts or _now_ts()
    cat = str(payload.get("category") or "sales")
    if cat not in KPI_CATEGORIES:
        cat = "sales"
    name = str(payload.get("metric_name") or "").strip()
    if not name:
        raise ValueError("Thiếu tên chỉ tiêu KPI.")
    owner_staff_id, owner_name = _resolve_owner_staff(conn, payload)
    tr = str(payload.get("track_status") or "active")
    if tr not in KPI_TRACK_STATUSES:
        tr = "active"
    unit = str(payload.get("unit") or "")[:40]
    metric_id, metric_code, metric_name_resolved, unit_resolved = _resolve_crm_metric(
        conn,
        payload,
        metric_name=name,
        unit=unit,
    )
    name = metric_name_resolved[:200]
    unit = unit_resolved[:40]
    values = (
        cat,
        name,
        float(payload.get("target_value") or 0),
        float(payload.get("actual_value") or 0),
        unit,
        str(payload.get("period_month") or "")[:7],
        float(payload.get("weight_pct") or 0),
        owner_staff_id,
        owner_name,
        tr,
        metric_code,
        metric_id,
        str(payload.get("notes") or "")[:2000],
        ts_val,
    )
    if kpi_id:
        conn.execute(
            """
            UPDATE crm_re_project_kpis SET
                category=?, metric_name=?, target_value=?, actual_value=?, unit=?,
                period_month=?, weight_pct=?, owner_staff_id=?, owner_name=?, track_status=?,
                metric_code=?, metric_id=?, notes=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (*values, int(kpi_id), int(project_id)),
        )
        rid = int(kpi_id)
    else:
        cur = conn.execute(
            """
            INSERT INTO crm_re_project_kpis (
                project_id, category, metric_name, target_value, actual_value, unit,
                period_month, weight_pct, owner_staff_id, owner_name, track_status,
                metric_code, metric_id, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(project_id),
                *values[:-1],
                ts_val,
                values[-1],
            ),
        )
        rid = int(cur.lastrowid)
    if owner_staff_id and (metric_id or metric_code):
        _sync_kpi_to_staff_module(conn, rid, project_id, ts=ts_val)
    row = conn.execute("SELECT * FROM crm_re_project_kpis WHERE id = ?", (rid,)).fetchone()
    assert row is not None
    enriched = list_kpis(conn, project_id)
    for d in enriched:
        if int(d.get("id") or 0) == rid:
            return d
    d = _child_row(row)
    d["category_label"] = KPI_CATEGORY_LABELS.get(str(d.get("category")), "")
    tgt = float(d.get("target_value") or 0)
    act = float(d.get("actual_value") or 0)
    d["achievement_pct"] = round(act / tgt * 100, 1) if tgt > 0 else 0
    return d


def delete_kpi(conn: sqlite3.Connection, project_id: int, kpi_id: int) -> None:
    conn.execute("DELETE FROM crm_re_project_kpis WHERE id = ? AND project_id = ?", (int(kpi_id), int(project_id)))


RE_LEADS_NEW_METRIC_CODE = "RE_LEADS_NEW"
RE_LEADS_NEW_EXCLUDED_STATUSES: tuple[str, ...] = ("lost", "junk", "spam", "duplicate")


def count_project_leads_new_actual(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    period_month: str = "",
) -> int:
    """Đếm lead đủ chuẩn trong tháng — nguồn KPI RE_LEADS_NEW (thống nhất)."""
    from crm_lead_kpi_metrics import count_qualified_leads_in_month

    pm = str(period_month or "").strip()[:7] or datetime.now().strftime("%Y-%m")
    try:
        y, m = pm.split("-", 1)
        return count_qualified_leads_in_month(
            conn, year=int(y), month=int(m), re_project_id=int(project_id)
        )
    except (TypeError, ValueError):
        return 0


def refresh_project_re_leads_new_kpi(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    period_month: str = "",
    ts: str | None = None,
    sync_staff: bool = True,
) -> dict[str, Any]:
    """Cập nhật actual_value KPI RE_LEADS_NEW từ crm_leads."""
    from crm_project_leads import validate_re_project_id

    validate_re_project_id(conn, int(project_id))
    ts_val = ts or _now_ts()
    pm = str(period_month or "").strip()[:7] or datetime.now().strftime("%Y-%m")
    actual = count_project_leads_new_actual(conn, int(project_id), period_month=pm)
    row = conn.execute(
        """
        SELECT id FROM crm_re_project_kpis
        WHERE project_id = ? AND metric_code = ? AND period_month = ?
        ORDER BY id DESC LIMIT 1
        """,
        (int(project_id), RE_LEADS_NEW_METRIC_CODE, pm),
    ).fetchone()
    kpi_id: int | None = None
    if row:
        kpi_id = int(row["id"])
        conn.execute(
            "UPDATE crm_re_project_kpis SET actual_value = ?, updated_at = ? WHERE id = ?",
            (float(actual), ts_val, kpi_id),
        )
    else:
        tmpl = next(
            (t for t in KPI_METRIC_TEMPLATES if str(t.get("crm_code") or "") == RE_LEADS_NEW_METRIC_CODE),
            None,
        )
        if tmpl:
            cur = conn.execute(
                """
                INSERT INTO crm_re_project_kpis (
                    project_id, category, metric_name, target_value, actual_value, unit,
                    period_month, weight_pct, owner_name, track_status, metric_code,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, '', 'active', ?, '', ?, ?)
                """,
                (
                    int(project_id),
                    str(tmpl.get("category") or "marketing"),
                    str(tmpl.get("metric_name") or "Lead mới qualified"),
                    float(actual),
                    str(tmpl.get("unit") or "lead"),
                    pm,
                    float(tmpl.get("weight_pct") or 0),
                    RE_LEADS_NEW_METRIC_CODE,
                    ts_val,
                    ts_val,
                ),
            )
            kpi_id = int(cur.lastrowid)
    if sync_staff and kpi_id:
        _sync_kpi_to_staff_module(conn, kpi_id, int(project_id), ts=ts_val)
    return {
        "updated": kpi_id is not None,
        "kpi_id": kpi_id,
        "actual": actual,
        "period_month": pm,
        "project_id": int(project_id),
    }


def list_risks(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_re_project_risks WHERE project_id = ? ORDER BY risk_level DESC, id",
        (int(project_id),),
    ).fetchall()
    out = []
    for r in rows:
        d = _child_row(r)
        cat = str(d.get("category") or "")
        lv = str(d.get("risk_level") or "")
        d["category_label"] = RISK_CATEGORY_LABELS.get(cat, cat)
        d["risk_level_label"] = RISK_LEVEL_LABELS.get(lv, lv)
        d["score"] = round(float(d.get("probability_pct") or 0) * float(d.get("impact_pct") or 0) / 100, 1)
        out.append(d)
    return out


def save_risk(conn: sqlite3.Connection, project_id: int, payload: dict[str, Any], *, risk_id: int | None = None, ts: str | None = None) -> dict[str, Any]:
    ts_val = ts or _now_ts()
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Thiếu tiêu đề rủi ro.")
    cat = str(payload.get("category") or "market")
    if cat not in RISK_CATEGORIES:
        cat = "market"
    lv = str(payload.get("risk_level") or "medium")
    if lv not in RISK_LEVELS:
        lv = "medium"
    if risk_id:
        conn.execute(
            """
            UPDATE crm_re_project_risks SET
                category=?, title=?, description=?, probability_pct=?, impact_pct=?,
                risk_level=?, mitigation=?, owner_name=?, status=?, due_date=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (
                cat,
                title[:200],
                str(payload.get("description") or "")[:4000],
                float(payload.get("probability_pct") or 0),
                float(payload.get("impact_pct") or 0),
                lv,
                str(payload.get("mitigation") or "")[:4000],
                str(payload.get("owner_name") or "")[:120],
                str(payload.get("status") or "open")[:40],
                str(payload.get("due_date") or "")[:10],
                ts_val,
                int(risk_id),
                int(project_id),
            ),
        )
        rid = int(risk_id)
    else:
        cur = conn.execute(
            """
            INSERT INTO crm_re_project_risks (
                project_id, category, title, description, probability_pct, impact_pct,
                risk_level, mitigation, owner_name, status, due_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(project_id),
                cat,
                title[:200],
                str(payload.get("description") or "")[:4000],
                float(payload.get("probability_pct") or 0),
                float(payload.get("impact_pct") or 0),
                lv,
                str(payload.get("mitigation") or "")[:4000],
                str(payload.get("owner_name") or "")[:120],
                str(payload.get("status") or "open")[:40],
                str(payload.get("due_date") or "")[:10],
                ts_val,
                ts_val,
            ),
        )
        rid = int(cur.lastrowid)
    row = conn.execute("SELECT * FROM crm_re_project_risks WHERE id = ?", (rid,)).fetchone()
    assert row is not None
    d = _child_row(row)
    cat = str(d.get("category") or "")
    lv = str(d.get("risk_level") or "")
    d["category_label"] = RISK_CATEGORY_LABELS.get(cat, cat)
    d["risk_level_label"] = RISK_LEVEL_LABELS.get(lv, lv)
    d["score"] = round(float(d.get("probability_pct") or 0) * float(d.get("impact_pct") or 0) / 100, 1)
    return d


def delete_risk(conn: sqlite3.Connection, project_id: int, risk_id: int) -> None:
    conn.execute("DELETE FROM crm_re_project_risks WHERE id = ? AND project_id = ?", (int(risk_id), int(project_id)))


def list_budget_lines(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_re_project_budget_lines WHERE project_id = ? ORDER BY period_month, category, id",
        (int(project_id),),
    ).fetchall()
    out = []
    for r in rows:
        d = _child_row(r)
        cat = str(d.get("category") or "")
        d["category_label"] = BUDGET_CATEGORY_LABELS.get(cat, cat)
        pl = int(d.get("planned_vnd") or 0)
        ac = int(d.get("actual_vnd") or 0)
        d["variance_vnd"] = ac - pl
        d["variance_pct"] = round((ac - pl) / pl * 100, 1) if pl else 0
        out.append(d)
    return out


def save_budget_line(conn: sqlite3.Connection, project_id: int, payload: dict[str, Any], *, line_id: int | None = None, ts: str | None = None) -> dict[str, Any]:
    ts_val = ts or _now_ts()
    item = str(payload.get("line_item") or "").strip()
    if not item:
        raise ValueError("Thiếu hạng mục ngân sách.")
    cat = str(payload.get("category") or "revenue")
    if cat not in BUDGET_CATEGORIES:
        cat = "revenue"
    if line_id:
        conn.execute(
            """
            UPDATE crm_re_project_budget_lines SET
                category=?, line_item=?, period_month=?, planned_vnd=?, actual_vnd=?, notes=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (
                cat,
                item[:200],
                str(payload.get("period_month") or "")[:7],
                int(payload.get("planned_vnd") or 0),
                int(payload.get("actual_vnd") or 0),
                str(payload.get("notes") or "")[:2000],
                ts_val,
                int(line_id),
                int(project_id),
            ),
        )
        rid = int(line_id)
    else:
        cur = conn.execute(
            """
            INSERT INTO crm_re_project_budget_lines (
                project_id, category, line_item, period_month, planned_vnd, actual_vnd, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(project_id),
                cat,
                item[:200],
                str(payload.get("period_month") or "")[:7],
                int(payload.get("planned_vnd") or 0),
                int(payload.get("actual_vnd") or 0),
                str(payload.get("notes") or "")[:2000],
                ts_val,
                ts_val,
            ),
        )
        rid = int(cur.lastrowid)
    row = conn.execute("SELECT * FROM crm_re_project_budget_lines WHERE id = ?", (rid,)).fetchone()
    assert row is not None
    d = _child_row(row)
    d["category_label"] = BUDGET_CATEGORY_LABELS.get(str(d.get("category")), "")
    pl = int(d.get("planned_vnd") or 0)
    ac = int(d.get("actual_vnd") or 0)
    d["variance_vnd"] = ac - pl
    d["variance_pct"] = round((ac - pl) / pl * 100, 1) if pl else 0
    return d


def delete_budget_line(conn: sqlite3.Connection, project_id: int, line_id: int) -> None:
    conn.execute(
        "DELETE FROM crm_re_project_budget_lines WHERE id = ? AND project_id = ?",
        (int(line_id), int(project_id)),
    )


def fetch_project_summary(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    proj = fetch_project(conn, project_id)
    if proj is None:
        raise ValueError("Không tìm thấy dự án.")
    products = list_products(conn, project_id)
    kpis = list_kpis(conn, project_id)
    risks = list_risks(conn, project_id)
    budget = list_budget_lines(conn, project_id)
    rev_planned = sum(int(b.get("planned_vnd") or 0) for b in budget if b.get("category") == "revenue")
    rev_actual = sum(int(b.get("actual_vnd") or 0) for b in budget if b.get("category") == "revenue")
    cost_planned = sum(int(b.get("planned_vnd") or 0) for b in budget if b.get("category") != "revenue")
    cost_actual = sum(int(b.get("actual_vnd") or 0) for b in budget if b.get("category") != "revenue")
    high_risks = sum(1 for r in risks if r.get("risk_level") in ("high", "critical"))
    kpi_avg = 0.0
    kpi_with_owner = 0
    if kpis:
        kpi_avg = round(sum(float(k.get("achievement_pct") or 0) for k in kpis) / len(kpis), 1)
        kpi_with_owner = sum(
            1 for k in kpis
            if int(k.get("owner_staff_id") or 0) > 0 or str(k.get("owner_name") or "").strip()
        )
    inv = compute_product_inventory_stats(products)
    kpi_board = compute_kpi_board_stats(kpis)
    return {
        "project": proj,
        "product_count": len(products),
        "products_available": sum(1 for p in products if p.get("status") == "available"),
        "products_sold": sum(1 for p in products if p.get("status") == "sold"),
        "product_lines_count": len(inv.get("by_product_line") or []),
        "product_zones_count": len(inv.get("by_zone") or []),
        "kpi_count": len(kpis),
        "kpi_with_owner_count": kpi_with_owner,
        "kpi_avg_achievement_pct": kpi_avg,
        "kpi_weight_total_pct": kpi_board.get("weight_total_pct") or 0,
        "inventory": inv,
        "kpi_board": kpi_board,
        "risk_count": len(risks),
        "high_risk_count": high_risks,
        "budget_revenue_planned_vnd": rev_planned,
        "budget_revenue_actual_vnd": rev_actual,
        "budget_cost_planned_vnd": cost_planned,
        "budget_cost_actual_vnd": cost_actual,
        "profit_planned_vnd": rev_planned - cost_planned,
        "profit_actual_vnd": rev_actual - cost_actual,
    }


RE_PROJECT_WORKFLOW_STEPS: tuple[dict[str, Any], ...] = (
    {
        "id": "overview",
        "label": "Thông tin dự án",
        "hint": "Khởi tạo hồ sơ dự án trên CRM",
        "phase": "initiate",
        "phase_label": "Khởi tạo",
        "criteria": "Mã, tên, vị trí và tổng số căn",
    },
    {
        "id": "business",
        "label": "Kế hoạch kinh doanh",
        "hint": "SWOT, chiến lược, phân tích thị trường",
        "phase": "strategy",
        "phase_label": "Chiến lược",
        "criteria": "Tầm nhìn, SWOT và doanh thu mục tiêu (hoặc duyệt KH)",
    },
    {
        "id": "budget",
        "label": "Ngân sách & P&L",
        "hint": "Khung tài chính trước khi triển khai bán",
        "phase": "finance",
        "phase_label": "Tài chính",
        "criteria": "Có dòng doanh thu và chi phí kế hoạch",
    },
    {
        "id": "products",
        "label": "Tồn kho sản phẩm",
        "hint": "Master data căn hộ trước khi lập giá & bán",
        "phase": "product",
        "phase_label": "Sản phẩm",
        "criteria": "Nhập tồn kho theo phân khu & loại hình sản phẩm",
    },
    {
        "id": "sales",
        "label": "Kế hoạch bán hàng",
        "hint": "Chỉ tiêu, chính sách giá và hoa hồng",
        "phase": "sales",
        "phase_label": "Bán hàng",
        "criteria": "Doanh thu + số căn mục tiêu (hoặc duyệt KH)",
    },
    {
        "id": "marketing",
        "label": "Marketing & GTM",
        "hint": "Go-to-market sau khi có mục tiêu bán",
        "phase": "gtm",
        "phase_label": "Go-to-market",
        "criteria": "Định vị, lead/tháng và ngân sách MKT",
    },
    {
        "id": "kpi",
        "label": "KPI vận hành",
        "hint": "Chỉ tiêu đo lường theo kỳ",
        "phase": "monitor",
        "phase_label": "Đo lường",
        "criteria": "Ít nhất 3 KPI gán nhân viên phụ trách",
    },
    {
        "id": "risks",
        "label": "Quản trị rủi ro",
        "hint": "Risk register — cập nhật xuyên suốt vòng đời dự án",
        "phase": "governance",
        "phase_label": "Quản trị",
        "criteria": "Đăng ký ít nhất 1 rủi ro chính",
        "optional": True,
    },
)

WORKFLOW_METHODOLOGY = (
    "Luồng theo thực hành dự án BĐS: Khởi tạo → Chiến lược → Tài chính → "
    "Sản phẩm → Bán hàng → Marketing → KPI → Quản trị rủi ro (song song)."
)


def _plan_status(plan: dict[str, Any], *, content_keys: tuple[str, ...], approved_key: str = "approval_status") -> str:
    if str(plan.get(approved_key) or "") == "approved":
        return "done"
    for k in content_keys:
        v = plan.get(k)
        if isinstance(v, list) and v:
            return "in_progress"
        if isinstance(v, dict) and any(v.values()):
            return "in_progress"
        if v not in (None, "", 0):
            return "in_progress"
    return "pending"


def _business_step_status(proj: dict[str, Any]) -> str:
    bp = proj.get("business_plan") or {}
    if str(bp.get("approval_status") or "") == "approved":
        return "done"
    sw = bp.get("swot") or {}
    has_swot = any(sw.get(k) for k in ("strengths", "weaknesses", "opportunities", "threats"))
    has_content = bool(
        bp.get("vision")
        or bp.get("mission")
        or has_swot
        or int(bp.get("revenue_target_vnd") or 0) > 0
    )
    if has_content:
        return "in_progress"
    return "pending"


def _marketing_step_status(proj: dict[str, Any]) -> str:
    mp = proj.get("marketing_plan") or {}
    if str(mp.get("approval_status") or "") == "approved":
        return "done"
    has_content = bool(
        mp.get("positioning")
        or int(mp.get("lead_target_monthly") or 0) > 0
        or mp.get("objectives")
        or mp.get("channels")
    )
    if has_content:
        return "in_progress"
    return _plan_status(
        mp,
        content_keys=("objectives", "target_segments", "key_messages", "channels", "positioning"),
    )


def _sales_step_status(proj: dict[str, Any]) -> str:
    sp = proj.get("sales_plan") or {}
    if str(sp.get("approval_status") or "") == "approved":
        return "done"
    has_content = bool(
        int(sp.get("revenue_target_vnd") or 0) > 0
        or int(sp.get("units_target") or 0) > 0
        or sp.get("pricing_strategy")
        or sp.get("commission_policy")
    )
    if has_content:
        return "in_progress"
    return _plan_status(
        sp,
        content_keys=("pricing_strategy", "commission_policy", "revenue_target_vnd", "units_target"),
    )


def _overview_step_status(proj: dict[str, Any]) -> str:
    has_name = bool(str(proj.get("name") or "").strip())
    has_code = bool(str(proj.get("code") or "").strip())
    has_location = bool(
        str(proj.get("district") or "").strip()
        or str(proj.get("city") or "").strip()
        or str(proj.get("location_address") or "").strip()
    )
    has_scale = int(proj.get("total_units") or 0) > 0
    if has_name and has_code and has_location and has_scale:
        return "done"
    if has_name and (has_code or has_location):
        return "in_progress"
    return "pending"


def _products_step_status(proj: dict[str, Any], summary: dict[str, Any]) -> str:
    count = int(summary.get("product_count") or 0)
    total = int(proj.get("total_units") or 0)
    if count >= 1 and (total <= 0 or count >= min(3, max(1, total // 10))):
        return "done"
    if count >= 1 or total > 0:
        return "in_progress"
    return "pending"


def _kpi_step_status(summary: dict[str, Any]) -> str:
    n = int(summary.get("kpi_count") or 0)
    with_owner = int(summary.get("kpi_with_owner_count") or 0)
    if n >= 3 and with_owner >= 3:
        return "done"
    if n >= 1 or with_owner >= 1:
        return "in_progress"
    return "pending"


def _budget_step_status(summary: dict[str, Any]) -> str:
    rev = int(summary.get("budget_revenue_planned_vnd") or 0)
    cost = int(summary.get("budget_cost_planned_vnd") or 0)
    if rev > 0 and cost > 0:
        return "done"
    if rev > 0 or cost > 0:
        return "in_progress"
    return "pending"


def _risks_step_status(summary: dict[str, Any]) -> str:
    if int(summary.get("risk_count") or 0) >= 1:
        return "done"
    return "pending"


def compute_project_workflow(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    proj = fetch_project(conn, project_id)
    if proj is None:
        raise ValueError("Không tìm thấy dự án.")
    summary = fetch_project_summary(conn, project_id)
    status_map = {
        "overview": _overview_step_status(proj),
        "business": _business_step_status(proj),
        "budget": _budget_step_status(summary),
        "products": _products_step_status(proj, summary),
        "sales": _sales_step_status(proj),
        "marketing": _marketing_step_status(proj),
        "kpi": _kpi_step_status(summary),
        "risks": _risks_step_status(summary),
    }
    status_labels = {
        "done": "Hoàn thành",
        "in_progress": "Đang làm",
        "pending": "Chưa bắt đầu",
    }
    steps: list[dict[str, Any]] = []
    done_n = 0
    next_step_id = ""
    for i, meta in enumerate(RE_PROJECT_WORKFLOW_STEPS):
        st = status_map.get(meta["id"], "pending")
        optional = bool(meta.get("optional"))
        prev_meta = RE_PROJECT_WORKFLOW_STEPS[i - 1] if i > 0 else None
        prev_id = prev_meta["id"] if prev_meta else ""
        next_id = RE_PROJECT_WORKFLOW_STEPS[i + 1]["id"] if i < len(RE_PROJECT_WORKFLOW_STEPS) - 1 else ""
        # Các bước kinh doanh mở tự do — không khóa theo thứ tự tuần tự.
        accessible = True
        locked = False
        blocked_by = ""
        if st == "done":
            done_n += 1
        elif not next_step_id:
            next_step_id = meta["id"]
        label = status_labels.get(st, st)
        if optional and st == "pending":
            label = "Khuyến nghị"
        steps.append(
            {
                **meta,
                "status": st,
                "status_label": label,
                "prev_step_id": prev_id,
                "next_step_id": next_id,
                "order": i + 1,
                "blocked_by": blocked_by,
                "optional": optional,
                "accessible": accessible,
                "locked": locked,
            }
        )
    if not next_step_id:
        for s in steps:
            if s["status"] != "done":
                next_step_id = s["id"]
                break
        if not next_step_id and steps:
            next_step_id = steps[-1]["id"]
    next_step = next((s for s in steps if s["id"] == next_step_id), None)
    next_hint = ""
    if next_step:
        crit = next_step.get("criteria") or next_step.get("hint") or ""
        next_hint = f'{next_step["label"]}: {crit}'
    total = len(steps)
    return {
        "project_id": int(project_id),
        "steps": steps,
        "done_count": done_n,
        "total_steps": total,
        "progress_pct": round(done_n / total * 100, 1) if total else 0,
        "next_step_id": next_step_id,
        "next_step_hint": next_hint,
        "methodology_note": WORKFLOW_METHODOLOGY,
    }


def _export_join(val: Any) -> str:
    if isinstance(val, list):
        return "; ".join(str(x).strip() for x in val if str(x).strip())
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False)
    return str(val or "")


def project_export_summary_rows(proj: dict[str, Any], summary: dict[str, Any], workflow: dict[str, Any]) -> list[list[Any]]:
    p = proj
    return [
        ["Mã dự án", p.get("code")],
        ["Tên dự án", p.get("name")],
        ["Loại hình", p.get("project_type_label")],
        ["Trạng thái", p.get("status_label")],
        ["Địa chỉ", p.get("location_address")],
        ["Quận/Huyện", p.get("district")],
        ["Tỉnh/TP", p.get("city")],
        ["Chủ đầu tư", p.get("developer_name")],
        ["Tổng căn", p.get("total_units")],
        ["Đã bán", p.get("sold_units")],
        ["Tiến độ bán (%)", p.get("sell_through_pct")],
        ["Doanh thu mục tiêu (VND)", p.get("revenue_target_vnd")],
        ["Căn còn hàng", summary.get("products_available")],
        ["Căn đã bán (tồn kho)", summary.get("products_sold")],
        ["Số KPI", summary.get("kpi_count")],
        ["KPI đạt TB (%)", summary.get("kpi_avg_achievement_pct")],
        ["Số rủi ro", summary.get("risk_count")],
        ["Rủi ro cao", summary.get("high_risk_count")],
        ["DT kế hoạch (VND)", summary.get("budget_revenue_planned_vnd")],
        ["DT thực tế (VND)", summary.get("budget_revenue_actual_vnd")],
        ["Chi phí KH (VND)", summary.get("budget_cost_planned_vnd")],
        ["Chi phí TT (VND)", summary.get("budget_cost_actual_vnd")],
        ["LNTT kế hoạch (VND)", summary.get("profit_planned_vnd")],
        ["LNTT thực tế (VND)", summary.get("profit_actual_vnd")],
        ["Tiến độ quy trình (%)", workflow.get("progress_pct")],
        ["Bước tiếp theo", workflow.get("next_step_id")],
    ]


def project_export_workflow_rows(workflow: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    headers = ["STT", "Bước", "Mô tả", "Trạng thái"]
    rows = [
        [s.get("order"), s.get("label"), s.get("hint"), s.get("status_label")]
        for s in workflow.get("steps") or []
    ]
    return headers, rows


def project_export_kpi_rows(kpis: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    headers = [
        "Chỉ tiêu", "Mã", "Loại", "Kỳ", "Mục tiêu", "Thực tế", "Đạt (%)",
        "Trọng số", "Nhân viên", "Phòng ban", "Trạng thái", "Ghi chú",
    ]
    rows = [
        [
            k.get("metric_name"),
            k.get("metric_code"),
            k.get("category_label"),
            k.get("period_month"),
            k.get("target_value"),
            k.get("actual_value"),
            k.get("achievement_pct"),
            k.get("weight_pct"),
            k.get("owner_display") or k.get("owner_name"),
            k.get("owner_department"),
            k.get("track_status_label") or k.get("track_status"),
            k.get("notes"),
        ]
        for k in kpis
    ]
    return headers, rows


def project_export_product_rows(products: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    headers = [
        "Mã căn", "Phân khu", "Block", "Tầng", "Dòng SP", "Typology", "Loại chi tiết",
        "DT (m²)", "PN", "Căn góc", "Giá niêm yết", "Trạng thái", "NV phụ trách", "Ghi chú",
    ]
    rows = [
        [
            p.get("unit_code"),
            p.get("zone"),
            p.get("tower"),
            p.get("floor"),
            p.get("product_line_label") or p.get("product_line"),
            p.get("typology_label") or p.get("typology"),
            p.get("product_type"),
            p.get("area_m2"),
            p.get("bedrooms"),
            "Có" if p.get("is_corner") else "",
            p.get("list_price_vnd"),
            p.get("status_label"),
            p.get("sales_staff_name"),
            p.get("notes"),
        ]
        for p in products
    ]
    return headers, rows


def project_export_risk_rows(risks: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    headers = ["Rủi ro", "Loại", "Mức", "Xác suất", "Tác động", "Điểm", "Biện pháp", "Owner", "Trạng thái"]
    rows = [
        [
            r.get("title"),
            r.get("category_label"),
            r.get("risk_level_label"),
            r.get("probability_pct"),
            r.get("impact_pct"),
            r.get("score"),
            r.get("mitigation"),
            r.get("owner_name"),
            r.get("status"),
        ]
        for r in risks
    ]
    return headers, rows


def project_export_budget_rows(budget: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    headers = ["Hạng mục", "Loại", "Kỳ", "Kế hoạch (VND)", "Thực tế (VND)", "Chênh lệch (VND)", "Ghi chú"]
    rows = [
        [
            b.get("line_item"),
            b.get("category_label"),
            b.get("period_month"),
            b.get("planned_vnd"),
            b.get("actual_vnd"),
            b.get("variance_vnd"),
            b.get("notes"),
        ]
        for b in budget
    ]
    return headers, rows


def project_export_plan_rows(proj: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    bp = proj.get("business_plan") or {}
    mp = proj.get("marketing_plan") or {}
    sp = proj.get("sales_plan") or {}
    sw = bp.get("swot") or {}
    headers = ["Hạng mục", "Trường", "Giá trị"]
    rows = [
        ["Kế hoạch KD", "Tầm nhìn", bp.get("vision")],
        ["Kế hoạch KD", "Sứ mệnh", bp.get("mission")],
        ["Kế hoạch KD", "Thị trường mục tiêu", bp.get("target_market")],
        ["Kế hoạch KD", "Doanh thu mục tiêu", bp.get("revenue_target_vnd")],
        ["Kế hoạch KD", "Điểm mạnh", _export_join(sw.get("strengths"))],
        ["Kế hoạch KD", "Điểm yếu", _export_join(sw.get("weaknesses"))],
        ["Kế hoạch KD", "Trạng thái duyệt", bp.get("approval_status")],
        ["Marketing", "Định vị", mp.get("positioning")],
        ["Marketing", "Lead/tháng", mp.get("lead_target_monthly")],
        ["Marketing", "Ngân sách", mp.get("budget_total_vnd")],
        ["Marketing", "Mục tiêu", _export_join(mp.get("objectives"))],
        ["Marketing", "Kênh", _export_join(mp.get("channels"))],
        ["Marketing", "Trạng thái duyệt", mp.get("approval_status")],
        ["Bán hàng", "Doanh thu mục tiêu", sp.get("revenue_target_vnd")],
        ["Bán hàng", "Số căn mục tiêu", sp.get("units_target")],
        ["Bán hàng", "Chiến lược giá", sp.get("pricing_strategy")],
        ["Bán hàng", "Trạng thái duyệt", sp.get("approval_status")],
    ]
    return headers, rows


def fetch_project_export_data(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    proj = fetch_project(conn, project_id)
    if proj is None:
        raise ValueError("Không tìm thấy dự án.")
    summary = fetch_project_summary(conn, project_id)
    workflow = compute_project_workflow(conn, project_id)
    return {
        "project": proj,
        "summary": summary,
        "workflow": workflow,
        "kpis": list_kpis(conn, project_id),
        "products": list_products(conn, project_id),
        "risks": list_risks(conn, project_id),
        "budget": list_budget_lines(conn, project_id),
    }


def seed_re_project_section_permissions(conn: sqlite3.Connection) -> None:
    """Reserved — quyền RE theo chức vụ lấy từ admin_page_permissions._POSITION_DEFAULT."""
    return
