#!/usr/bin/env python3
"""Seed dữ liệu dự án VHHM Phase 2 vào PTT.

Tạo dự án Vinhomes Saigon Park (Hóc Môn), cấu hình sản phẩm Phase 2
(shophouse · biệt thự · liền kề), lead config và rubric chấm điểm
phù hợp chu kỳ bán 30–90 ngày.

Chạy:
    python scripts/seed_vhhm_phase2.py

Env vars:
    PTT_BASE_URL     (default: http://127.0.0.1:5050)
    ADMIN_USERNAME   (default: admin)
    ADMIN_PASSWORD   (default: 12345678)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = os.getenv("PTT_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "12345678")

VHHM_CODE = "VHHM-P2"
VHHM_NAME = "Vinhomes Saigon Park — Phase 2 (Hóc Môn)"

# 5 ngách khách hàng Phase 2 → product_line tương ứng trong PTT
PHASE2_PRODUCTS = [
    {
        "unit_code": "SH-VHHM-P2",
        "product_line": "shophouse",
        "zone": "shophouse_central",
        "list_price_vnd": 12_000_000_000,
        "status": "available",
        "notes": "Shophouse mặt tiền — ngách SME chủ shop / F&B / phòng khám",
    },
    {
        "unit_code": "BT-VHHM-P2",
        "product_line": "biet_thu",
        "zone": "biet_thu_block",
        "list_price_vnd": 20_000_000_000,
        "status": "available",
        "notes": "Biệt thự — ngách doanh nhân thành đạt / legacy / Việt kiều",
    },
    {
        "unit_code": "LK-DOI-VHHM",
        "product_line": "lien_ke",
        "zone": "lien_ke_block_a",
        "list_price_vnd": 8_500_000_000,
        "status": "available",
        "notes": "Liền kề — ngách đổi nhà từ Hóc Môn / Củ Chi / Q12",
    },
    {
        "unit_code": "LK-DTH-VHHM",
        "product_line": "lien_ke",
        "zone": "lien_ke_block_b",
        "list_price_vnd": 9_000_000_000,
        "status": "available",
        "notes": "Liền kề cụm — ngách gia đình đa thế hệ (mua 2-3 căn liền nhau)",
    },
]

# Rubric Phase 2: điều chỉnh timeline dài hơn, trọng số tài chính cao hơn
VHHM_PHASE2_LEAD_CONFIG = {
    "duplicate_policy": "flag",
    "hot_priority_assign": True,
    "inactive_owner_fallback": "round_robin",
    "activity_sla_enabled": True,
    "scoring_mode": "rubric",
    "scoring_rules": None,
    "level_tiers": [
        {"min": 75, "max": 100, "tier": "hot",       "label": "Nóng — ưu tiên gọi ngay"},
        {"min": 50, "max": 74,  "tier": "warm",      "label": "Ấm — theo dõi tuần 1-2"},
        {"min": 25, "max": 49,  "tier": "cold",      "label": "Lạnh — drip content 30 ngày"},
        {"min": 0,  "max": 24,  "tier": "very_cold", "label": "Rất lạnh — newsletter only"},
    ],
    "scoring_rubric": {
        "groups": [
            {
                "id": "group_d1",
                "code": "D1",
                "label": "THÔNG TIN & HÀNH VI",
                "max_points": 20,
                "sort_order": 1,
                "criteria": [
                    {
                        "id": "d1_1_info",
                        "code": "D1.1",
                        "label": "Mức độ đầy đủ thông tin",
                        "max_points": 10,
                        "evaluator": "info_completeness",
                        "enabled": True,
                        "sort_order": 1,
                        "bands": [
                            {"id": "d1_1_t6", "label": "SĐT + Tên + Email + Ngân sách + SP ngách",   "points": 10, "tier_value": 6},
                            {"id": "d1_1_t5", "label": "SĐT + Tên + Email + Ngân sách",              "points": 8,  "tier_value": 5},
                            {"id": "d1_1_t4", "label": "SĐT + Tên + Email",                          "points": 6,  "tier_value": 4},
                            {"id": "d1_1_t3", "label": "SĐT + Tên + Ngân sách",                      "points": 5,  "tier_value": 3},
                            {"id": "d1_1_t2", "label": "SĐT + Tên",                                   "points": 3,  "tier_value": 2},
                            {"id": "d1_1_t1", "label": "Chỉ có SĐT",                                  "points": 1,  "tier_value": 1},
                        ],
                    },
                    {
                        "id": "d1_2_web",
                        "code": "D1.2",
                        "label": "Hành vi trên website / landing page",
                        "max_points": 10,
                        "evaluator": "web_behavior",
                        "enabled": True,
                        "sort_order": 2,
                        "bands": [
                            {"id": "d1_2_t6", "label": "Xem bảng giá + form đăng ký tư vấn",         "points": 10, "tier_value": 6},
                            {"id": "d1_2_t5", "label": "Xem bảng giá shophouse/biệt thự/liền kề",   "points": 8,  "tier_value": 5},
                            {"id": "d1_2_t4", "label": "Xem video dự án > 50%",                       "points": 6,  "tier_value": 4},
                            {"id": "d1_2_t3", "label": "Xem trang dự án > 3 lần",                    "points": 4,  "tier_value": 3},
                            {"id": "d1_2_t2", "label": "Xem trang dự án 1–2 lần",                    "points": 2,  "tier_value": 2},
                            {"id": "d1_2_t0", "label": "Không có data hành vi",                       "points": 0,  "tier_value": 0},
                        ],
                    },
                ],
            },
            {
                "id": "group_d2",
                "code": "D2",
                "label": "KHẢ NĂNG TÀI CHÍNH",
                "max_points": 25,
                "sort_order": 2,
                "criteria": [
                    {
                        "id": "d2_1_budget",
                        "code": "D2.1",
                        "label": "Ngân sách khai báo",
                        "max_points": 15,
                        "evaluator": "budget_decl_quality",
                        "enabled": True,
                        "sort_order": 1,
                        "bands": [
                            {"id": "d2_1_t4", "label": 'Khai báo số cụ thể (VD: "12 tỷ")',            "points": 15, "tier_value": 4},
                            {"id": "d2_1_t3", "label": 'Khai báo khoảng (VD: "10–15 tỷ")',            "points": 12, "tier_value": 3},
                            {"id": "d2_1_t2", "label": 'Khai báo chung (VD: "tầm 10 tỷ")',            "points": 8,  "tier_value": 2},
                            {"id": "d2_1_t1", "label": 'Khai báo rất chung (VD: "vài tỷ")',           "points": 4,  "tier_value": 1},
                            {"id": "d2_1_t0", "label": "Không khai báo",                               "points": 0,  "tier_value": 0},
                        ],
                    },
                    {
                        "id": "d2_2_budget_price",
                        "code": "D2.2",
                        "label": "Ngân sách so với giá Phase 2",
                        "max_points": 10,
                        "evaluator": "budget_vs_price_pct",
                        "enabled": True,
                        "sort_order": 2,
                        "bands": [
                            {"id": "d2_2_b6", "label": "Ngân sách dư dả (> 100% giá)",  "points": 10, "min_value": 100, "min_exclusive": True},
                            {"id": "d2_2_b5", "label": "Ngân sách phù hợp (90–100%)",   "points": 10, "min_value": 90, "max_value": 100},
                            {"id": "d2_2_b4", "label": "Ngân sách 75–90%",               "points": 7,  "min_value": 75, "max_value": 90},
                            {"id": "d2_2_b3", "label": "Ngân sách 60–75%",               "points": 4,  "min_value": 60, "max_value": 75},
                            {"id": "d2_2_b2", "label": "Ngân sách 40–60%",               "points": 2,  "min_value": 40, "max_value": 60},
                            {"id": "d2_2_b1", "label": "Ngân sách < 40%",                "points": 0,  "max_value": 40, "max_exclusive": True},
                        ],
                    },
                ],
            },
            {
                "id": "group_d3",
                "code": "D3",
                "label": "TIMELINE & ĐỘ CẤP THIẾT",
                "max_points": 20,
                "sort_order": 3,
                "criteria": [
                    {
                        "id": "d3_1_timeline",
                        "code": "D3.1",
                        "label": "Thời gian dự kiến mua (Phase 2 chu kỳ dài)",
                        "max_points": 20,
                        "evaluator": "purchase_timeline",
                        "enabled": True,
                        "sort_order": 1,
                        "bands": [
                            {"id": "d3_1_t5", "label": "Mua trong tháng này",              "points": 20, "tier_value": 5},
                            {"id": "d3_1_t4", "label": "1–3 tháng tới",                    "points": 16, "tier_value": 4},
                            {"id": "d3_1_t3", "label": "3–6 tháng tới",                    "points": 12, "tier_value": 3},
                            {"id": "d3_1_t2", "label": "6–12 tháng tới",                   "points": 8,  "tier_value": 2},
                            {"id": "d3_1_t1", "label": "Chưa xác định / > 12 tháng",       "points": 3,  "tier_value": 1},
                        ],
                    },
                ],
            },
            {
                "id": "group_d4",
                "code": "D4",
                "label": "NGUỒN LEAD",
                "max_points": 15,
                "sort_order": 4,
                "criteria": [
                    {
                        "id": "d4_source",
                        "code": "D4",
                        "label": "Nguồn lead",
                        "max_points": 15,
                        "evaluator": "lead_source",
                        "enabled": True,
                        "sort_order": 1,
                        "bands": [
                            {"id": "d4_ref",       "label": "Khách giới thiệu",                         "points": 15, "match_sources": ["referral", "gioi_thieu"]},
                            {"id": "d4_event",     "label": "Sự kiện / mở bán",                         "points": 12, "match_sources": ["event", "su_kien"]},
                            {"id": "d4_zalo_chat", "label": "Zalo OA / chat trực tiếp",                  "points": 10, "match_sources": ["zalo", "chat"]},
                            {"id": "d4_fb_form",   "label": "Facebook Lead Form",                        "points": 8,  "match_sources": ["facebook", "fb_lead_form"]},
                            {"id": "d4_web_form",  "label": "Form landing page",                         "points": 7,  "match_sources": ["web", "landing_page", "website"]},
                            {"id": "d4_seo",       "label": "SEO / Google organic",                      "points": 6,  "match_sources": ["seo", "organic", "google"]},
                            {"id": "d4_paid",      "label": "Google Ads / Meta Ads",                     "points": 5,  "match_sources": ["google_ads", "meta_ads", "gg_ads"]},
                            {"id": "d4_other",     "label": "Khác / chưa rõ nguồn",                      "points": 2,  "match_sources": []},
                        ],
                    },
                ],
            },
            {
                "id": "group_d5",
                "code": "D5",
                "label": "TƯƠNG TÁC",
                "max_points": 10,
                "sort_order": 5,
                "criteria": [
                    {
                        "id": "d5_1_interactions",
                        "code": "D5.1",
                        "label": "Số lần tương tác",
                        "max_points": 6,
                        "evaluator": "interaction_count",
                        "enabled": True,
                        "sort_order": 1,
                        "bands": [
                            {"id": "d5_1_b5", "label": "> 5 lần",  "points": 6,  "min_value": 5,  "min_exclusive": True},
                            {"id": "d5_1_b4", "label": "3–5 lần",  "points": 5,  "min_value": 3,  "max_value": 5},
                            {"id": "d5_1_b3", "label": "2 lần",    "points": 4,  "min_value": 2,  "max_value": 2},
                            {"id": "d5_1_b2", "label": "1 lần",    "points": 2,  "min_value": 1,  "max_value": 1},
                            {"id": "d5_1_b1", "label": "0 lần",    "points": 0,  "max_value": 0},
                        ],
                    },
                    {
                        "id": "d5_2_last_type",
                        "code": "D5.2",
                        "label": "Loại tương tác gần nhất",
                        "max_points": 4,
                        "evaluator": "last_interaction_type",
                        "enabled": True,
                        "sort_order": 2,
                        "bands": [
                            {"id": "d5_2_t4", "label": "Gặp mặt / tham quan thực tế",   "points": 4, "tier_value": 4},
                            {"id": "d5_2_t3", "label": "Gọi điện thoại",                 "points": 3, "tier_value": 3},
                            {"id": "d5_2_t2", "label": "Zalo / chat",                    "points": 2, "tier_value": 2},
                            {"id": "d5_2_t1", "label": "Email / SMS",                    "points": 1, "tier_value": 1},
                            {"id": "d5_2_t0", "label": "Chưa có tương tác",              "points": 0, "tier_value": 0},
                        ],
                    },
                ],
            },
            {
                "id": "group_d6",
                "code": "D6",
                "label": "HỒ SƠ KHÁCH HÀNG",
                "max_points": 10,
                "sort_order": 6,
                "criteria": [
                    {
                        "id": "d6_2_occupation",
                        "code": "D6.2",
                        "label": "Nghề nghiệp / Thu nhập (Phase 2 ưu tiên chủ DN & thu nhập cao)",
                        "max_points": 10,
                        "evaluator": "occupation_tier",
                        "enabled": True,
                        "sort_order": 1,
                        "bands": [
                            {"id": "d6_2_t5", "label": "Chủ doanh nghiệp / CEO / Giám đốc",       "points": 10, "tier_value": 5},
                            {"id": "d6_2_t4", "label": "Việt kiều / Thu nhập ngoại tệ",            "points": 10, "tier_value": 4},
                            {"id": "d6_2_t3", "label": "Thu nhập > 60tr/tháng",                    "points": 8,  "tier_value": 3},
                            {"id": "d6_2_t2", "label": "Thu nhập 30–60tr/tháng",                   "points": 6,  "tier_value": 2},
                            {"id": "d6_2_t1", "label": "Thu nhập 15–30tr/tháng",                   "points": 3,  "tier_value": 1},
                            {"id": "d6_2_t0", "label": "Chưa rõ / Thu nhập < 15tr",                "points": 0,  "tier_value": 0},
                        ],
                    },
                ],
            },
        ]
    },
    "facebook_config": {
        "page_id": "",
        "slug": "vhhm-phase2",
        "verify_token": "vhhm_p2_verify_2026",
        "app_secret": "",
        "default_product_line": "shophouse",
        "field_map": {
            "full_name": ["full_name", "ho_ten"],
            "phone": ["phone_number", "so_dien_thoai"],
            "email": ["email"],
            "budget": ["ngan_sach", "budget"],
            "product_interest": ["san_pham", "loai_nha"],
        },
    },
    "assign_config": {
        "strategy": "hybrid",
        "skill_tags": ["shophouse", "biet_thu", "lien_ke"],
    },
}


class Client:
    def __init__(self) -> None:
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(
        self,
        method: str,
        path: str,
        *,
        data: dict | None = None,
        expect: int | tuple[int, ...] = 200,
    ) -> dict:
        url = f"{BASE}{path}"
        body = None
        headers: dict[str, str] = {"Accept": "application/json"}
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        try:
            with self.opener.open(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                code = resp.status
        except urllib.error.HTTPError as e:
            code = e.code
            raw = e.read().decode("utf-8", errors="replace")
        exp = (expect,) if isinstance(expect, int) else expect
        if code not in exp:
            raise RuntimeError(f"{method} {path} → HTTP {code}: {raw[:800]}")
        return json.loads(raw) if raw.strip() else {}

    def login(self) -> None:
        for pw in (ADMIN_PASS, "changeme", "12345678"):
            form = urllib.parse.urlencode({"username": ADMIN_USER, "password": pw}).encode()
            req = urllib.request.Request(
                f"{BASE}/admin/login",
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            try:
                with self.opener.open(req, timeout=30) as resp:
                    if resp.status in (200, 302):
                        test = self.request("GET", "/api/crm/re-projects")
                        if "projects" in test:
                            return
            except urllib.error.HTTPError:
                continue
        raise RuntimeError("Không đăng nhập được admin")


def main() -> int:
    c = Client()
    c.login()
    print("✓ Đăng nhập thành công")

    # 1. Tìm hoặc tạo dự án VHHM Phase 2
    listed = c.request("GET", "/api/crm/re-projects")
    projects = listed.get("projects") or []
    vhhm = next((p for p in projects if p.get("code") == VHHM_CODE), None)

    if vhhm is None:
        vhhm = c.request(
            "POST",
            "/api/crm/re-projects",
            data={
                "name": VHHM_NAME,
                "code": VHHM_CODE,
                "total_units": 200,
                "project_type_code": "can_ho_chung_cu",
                "status": "selling",
                "province": "Hồ Chí Minh",
                "district": "Hóc Môn",
                "address": "Quốc lộ 22, Hóc Môn, TP.HCM",
                "legal_status": "so_do",
                "marketing_plan": {
                    "lead_target_monthly": 300,
                    "channels": ["facebook", "zalo", "seo", "event", "referral"],
                    "target_niches": [
                        "shophouse_sme",
                        "doi_nha",
                        "da_the_he",
                        "viet_kieu",
                        "legacy",
                    ],
                },
                "sales_plan": {
                    "units_target": 50,
                    "avg_cycle_days": 60,
                    "phase": "2",
                    "products": ["shophouse", "biet_thu", "lien_ke"],
                },
            },
            expect=201,
        )
        print(f"✓ Tạo dự án mới: {vhhm['name']} (id={vhhm['id']})")
    else:
        print(f"✓ Dự án đã tồn tại: {vhhm['name']} (id={vhhm['id']})")

    pid = int(vhhm["id"])

    # 2. Thêm sản phẩm Phase 2 (skip nếu unit_code đã có)
    existing_products = c.request("GET", f"/api/crm/re-projects/{pid}/products")
    existing_codes = {p["unit_code"] for p in (existing_products.get("products") or [])}

    for prod in PHASE2_PRODUCTS:
        if prod["unit_code"] in existing_codes:
            print(f"  - Sản phẩm {prod['unit_code']} đã tồn tại — bỏ qua")
            continue
        result = c.request(
            "POST",
            f"/api/crm/re-projects/{pid}/products",
            data=prod,
            expect=201,
        )
        print(f"  ✓ Thêm sản phẩm: {result['unit_code']} ({prod['product_line']})")

    # 3. Lưu lead config (rubric Phase 2 + facebook webhook config)
    c.request(
        "PUT",
        f"/api/crm/re-projects/{pid}/lead-config",
        data=VHHM_PHASE2_LEAD_CONFIG,
    )
    print("✓ Đã lưu lead config (rubric Phase 2 + facebook webhook + assign strategy)")

    # 4. Summary
    print()
    print("=" * 60)
    print(f"VHHM Phase 2 seed hoàn tất — project_id={pid}")
    print(f"  Dự án   : {VHHM_NAME}")
    print(f"  Mã      : {VHHM_CODE}")
    print(f"  Sản phẩm: Shophouse · Biệt thự · Liền kề (đổi nhà / đa thế hệ)")
    print(f"  Facebook: webhook slug = vhhm-phase2")
    print(f"  Rubric  : D1(20) + D2(25) + D3(20) + D4(15) + D5(10) + D6(10) = 100đ")
    print()
    print("Bước tiếp theo:")
    print("  1. Vào CRM → Dự án BĐS → VHHM Phase 2 → Phân quyền nhân viên")
    print("     Gán scope_product_lines: shophouse, biet_thu, lien_ke")
    print("  2. Cấu hình Facebook webhook:")
    print("     App Secret + Page ID tại CRM → Dự án → Cấu hình Facebook")
    print("  3. Test lead ingest:")
    print("     POST /api/crm/integration/webhooks/facebook/vhhm-phase2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
