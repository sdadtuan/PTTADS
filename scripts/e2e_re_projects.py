#!/usr/bin/env python3
"""E2E — CRM Dự án BĐS qua Flask API."""
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
    print("OK login")

    page_req = urllib.request.Request(f"{BASE}/crm/re-projects")
    with c.opener.open(page_req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
        if "crm-re-projects-meta" not in html:
            raise RuntimeError("Trang /crm/re-projects thiếu meta JSON")
        if "crm_re_projects.js" not in html and "crm_re_projects.min.js" not in html:
            raise RuntimeError("Trang thiếu JS bundle")
    print("OK page HTML")

    listed = c.request("GET", "/api/crm/re-projects")
    projects = listed.get("projects") or []
    if not projects:
        created = c.request(
            "POST",
            "/api/crm/re-projects",
            data={"name": "E2E Test Tower", "code": "E2E-01", "total_units": 50},
            expect=201,
        )
        pid = int(created["id"])
        print(f"OK create project id={pid}")
    else:
        pid = int(projects[0]["id"])
        print(f"OK list projects ({len(projects)}), using id={pid}")

    proj = c.request("GET", f"/api/crm/re-projects/{pid}")
    assert proj.get("name"), "project missing name"
    print("OK get project")

    bp = proj.get("business_plan") or {}
    bp["vision"] = "E2E vision test"
    updated = c.request("PUT", f"/api/crm/re-projects/{pid}", data={"business_plan": bp})
    assert updated["business_plan"]["vision"] == "E2E vision test"
    print("OK update business plan")

    mp = updated.get("marketing_plan") or {}
    mp["lead_target_monthly"] = 120
    c.request("PUT", f"/api/crm/re-projects/{pid}", data={"marketing_plan": mp})
    print("OK update marketing plan")

    sp = updated.get("sales_plan") or {}
    sp["units_target"] = 40
    c.request("PUT", f"/api/crm/re-projects/{pid}", data={"sales_plan": sp})
    print("OK update sales plan")

    types = c.request("GET", "/api/crm/re-projects/types?include_inactive=1")
    assert (types.get("types") or []), "missing project types"
    new_type = c.request(
        "POST",
        "/api/crm/re-projects/types",
        data={"code": "e2e_loai", "name": "E2E Loại test", "sort_order": 888},
        expect=201,
    )
    type_id = int(new_type["id"])
    print("OK create project type")

    product = c.request(
        "POST",
        f"/api/crm/re-projects/{pid}/products",
        data={"unit_code": "E2E-A01", "list_price_vnd": 3_000_000_000, "status": "available"},
        expect=201,
    )
    prod_id = int(product["id"])
    assert product.get("status_label"), "product missing status_label"
    print("OK create product")

    kpi = c.request(
        "POST",
        f"/api/crm/re-projects/{pid}/kpis",
        data={
            "metric_name": "Doanh thu Q2",
            "target_value": 100,
            "actual_value": 75,
            "unit": "%",
            "period_month": "2026-06",
        },
        expect=201,
    )
    kpi_id = int(kpi["id"])
    assert kpi.get("achievement_pct") == 75.0
    print("OK create KPI")

    risk = c.request(
        "POST",
        f"/api/crm/re-projects/{pid}/risks",
        data={
            "title": "E2E risk",
            "probability_pct": 50,
            "impact_pct": 60,
            "risk_level": "high",
        },
        expect=201,
    )
    risk_id = int(risk["id"])
    assert risk.get("category_label") or risk.get("risk_level_label"), "risk missing labels"
    print("OK create risk")

    budget = c.request(
        "POST",
        f"/api/crm/re-projects/{pid}/budget",
        data={
            "line_item": "Doanh thu E2E",
            "category": "revenue",
            "planned_vnd": 10_000_000_000,
            "actual_vnd": 8_000_000_000,
        },
        expect=201,
    )
    line_id = int(budget["id"])
    assert "variance_vnd" in budget
    print("OK create budget line")

    summary = c.request("GET", f"/api/crm/re-projects/{pid}/summary")
    assert summary.get("product_count", 0) >= 1
    assert summary.get("kpi_count", 0) >= 1
    assert summary.get("risk_count", 0) >= 1
    print("OK summary")

    c.request(
        "PUT",
        f"/api/crm/re-projects/{pid}/products/{prod_id}",
        data={"unit_code": "E2E-A01", "status": "sold", "list_price_vnd": 3_000_000_000},
    )
    c.request(
        "PUT",
        f"/api/crm/re-projects/{pid}/kpis/{kpi_id}",
        data={"metric_name": "Doanh thu Q2", "target_value": 100, "actual_value": 90},
    )
    print("OK update child entities")

    c.request("DELETE", f"/api/crm/re-projects/{pid}/budget/{line_id}")
    c.request("DELETE", f"/api/crm/re-projects/{pid}/risks/{risk_id}")
    c.request("DELETE", f"/api/crm/re-projects/{pid}/kpis/{kpi_id}")
    c.request("DELETE", f"/api/crm/re-projects/{pid}/products/{prod_id}")
    c.request("DELETE", f"/api/crm/re-projects/types/{type_id}")
    print("OK delete project type")
    print("OK delete child entities")

    if proj.get("code") == "E2E-01" or proj.get("name") == "E2E Test Tower":
        c.request("DELETE", f"/api/crm/re-projects/{pid}")
        print("OK delete test project")

    print("\n=== E2E RE Projects: ALL PASS ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
