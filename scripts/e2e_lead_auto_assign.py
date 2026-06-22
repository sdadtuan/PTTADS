#!/usr/bin/env python3
"""E2E — phân lead tự động qua Flask API (server đang chạy)."""
from __future__ import annotations

import copy
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crm_lead_auto_assign import config_with_only  # noqa: E402

BASE = os.getenv("PTT_BASE_URL", "http://127.0.0.1:5050").rstrip("/")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "12345678")

# Bootstrap NV cho test (id → patch) — khôi phục sau khi chạy
STAFF_BOOTSTRAP: dict[int, dict] = {
    1: {"sales_level": "c", "notes": "việt kiều english nuôi dưỡng cold"},
    2: {"sales_level": "a", "notes": "q.1 nhà phố facebook"},
    3: {"sales_level": "b", "notes": "q.9 biệt thự warm"},
    4: {"sales_level": "s", "notes": "vip q.7 căn hộ chung cư"},
    5: {"sales_level": "b", "notes": "q.7 căn hộ nhà phố"},
    6: {"sales_level": "a", "notes": "q.2 căn hộ referral"},
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
        headers: dict[str, str] = {}
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
            raise RuntimeError(f"{method} {path} → HTTP {code}: {raw[:600]}")
        return json.loads(raw) if raw.strip() else {}

    def login(self) -> None:
        form = urllib.parse.urlencode({"username": ADMIN_USER, "password": ADMIN_PASS}).encode()
        req = urllib.request.Request(
            f"{BASE}/admin/login",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with self.opener.open(req, timeout=30) as resp:
            if resp.status not in (200, 302):
                raise RuntimeError(f"Login failed HTTP {resp.status}")


def staff_by_id(staff: list[dict]) -> dict[int, dict]:
    return {int(s["id"]): s for s in staff}


def unique_phone(tag: str) -> str:
    ts = int(time.time() * 1000) % 10_000_000
    return f"09{ts:07d}{abs(hash(tag)) % 10}"


def build_assign_payload(*enabled_ids: str) -> dict:
    return {"assign_config": config_with_only(*enabled_ids)}


def enrich_config_for_test(cfg: dict) -> dict:
    """Bổ sung map phân hạng tùy chỉnh (moi/normal) vào assign_config."""
    out = copy.deepcopy(cfg)
    ac = out.setdefault("assign_config", {})
    tmap = dict(ac.get("tier_level_map") or {})
    for k, v in {
        "moi": ["b", "c"],
        "normal": ["a", "b"],
        "vip": ["s", "a"],
    }.items():
        tmap.setdefault(k, v)
    ac["tier_level_map"] = tmap
    return out


def create_lead(c: Client, *, name: str, tag: str, **fields) -> dict:
    ts = int(time.time() * 1000) % 10_000_000
    payload = {
        "full_name": name,
        "phone": unique_phone(tag),
        "email": fields.pop("email", f"e2e{abs(hash(tag)) % 10_000_000}_{ts}@example.com"),
        "source": fields.pop("source", "manual"),
        "region": fields.pop("region", ""),
        "product_interest": fields.pop("product_interest", ""),
        "need": fields.pop("need", ""),
        "status": "new",
    }
    if "meta" in fields:
        payload["meta"] = fields.pop("meta")
    payload.update(fields)
    return c.request("POST", "/api/crm/leads", data=payload, expect=(201, 200))["lead"]


def check_level(staff_map: dict[int, dict], owner_id: int | None, allowed: set[str]) -> bool:
    if not owner_id:
        return False
    lv = str(staff_map.get(owner_id, {}).get("sales_level") or "").lower()
    return lv in allowed if lv else False


def notes_match(staff_map: dict[int, dict], owner_id: int | None, keywords: list[str]) -> bool:
    if not owner_id:
        return False
    notes = str(staff_map.get(owner_id, {}).get("notes") or "").lower()
    return all(kw.lower() in notes for kw in keywords)


def notes_any(staff_map: dict[int, dict], owner_id: int | None, keywords: list[str]) -> bool:
    if not owner_id:
        return False
    notes = str(staff_map.get(owner_id, {}).get("notes") or "").lower()
    return any(kw.lower() in notes for kw in keywords)


def bootstrap_staff(c: Client) -> dict[int, dict]:
    """Bootstrap qua DB trực tiếp — tránh lỗi validate đăng nhập NV trên PATCH API."""
    import sqlite3

    db_path = ROOT / "ptt.db"
    saved: dict[int, dict] = {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for sid, patch in STAFF_BOOTSTRAP.items():
            row = conn.execute(
                "SELECT sales_level, notes FROM crm_staff WHERE id = ?", (sid,)
            ).fetchone()
            if row is None:
                continue
            saved[sid] = {"sales_level": row["sales_level"], "notes": row["notes"]}
            conn.execute(
                "UPDATE crm_staff SET sales_level = ?, notes = ? WHERE id = ?",
                (
                    str(patch.get("sales_level") or ""),
                    str(patch.get("notes") or ""),
                    sid,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return saved


def restore_staff(c: Client, saved: dict[int, dict]) -> None:
    import sqlite3

    db_path = ROOT / "ptt.db"
    conn = sqlite3.connect(db_path)
    try:
        for sid, patch in saved.items():
            conn.execute(
                "UPDATE crm_staff SET sales_level = ?, notes = ? WHERE id = ?",
                (
                    str(patch.get("sales_level") or ""),
                    str(patch.get("notes") or ""),
                    sid,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def run_case(c: Client, smap: dict[int, dict], base_cfg: dict, case: dict) -> dict:
    cfg = enrich_config_for_test(base_cfg)
    tiers = copy.deepcopy(cfg.get("level_tiers") or [])

    if case.get("level_tiers_override"):
        tiers = copy.deepcopy(case["level_tiers_override"])
    else:
        if case.get("tier_patch"):
            for t in tiers:
                if t.get("id") == case["tier_patch"]["id"]:
                    t.update(case["tier_patch"]["values"])
        for extra in case.get("extra_tiers") or []:
            tiers = [t for t in tiers if t.get("id") != extra.get("id")]
            tiers.append(extra)
        for tid, vals in (case.get("tier_shrink") or {}).items():
            for t in tiers:
                if t.get("id") == tid:
                    t.update(vals)

    cfg["level_tiers"] = tiers

    assign_only = build_assign_payload(*case["enabled"])
    cfg["assign_config"] = assign_only["assign_config"]
    cfg["assign_config"]["tier_level_map"] = enrich_config_for_test({})["assign_config"]["tier_level_map"]

    c.request("PUT", "/api/crm/leads/config", data=cfg)
    lead = create_lead(c, tag=case["label"], **case["lead_kwargs"])
    ok, detail = case["verify"](lead, smap)
    return {
        "method": case["label"],
        "enabled": ", ".join(case["enabled"]),
        "lead_id": lead.get("id"),
        "owner": lead.get("owner_name") or lead.get("owner_id"),
        "level": lead.get("lead_level"),
        "score": lead.get("lead_score"),
        "ok": ok,
        "detail": detail,
    }


def main() -> int:
    print(f"=== E2E phân lead tự động — {BASE} ===\n")
    c = Client()
    c.login()
    print("✓ Đăng nhập admin OK")

    staff_saved = bootstrap_staff(c)
    print(f"✓ Bootstrap {len(staff_saved)} NV (sales_level + ghi chú test)\n")

    smap = staff_by_id(c.request("GET", "/api/crm/staff").get("staff") or [])
    base_cfg = c.request("GET", "/api/crm/leads/config")["config"]
    orig_cfg = copy.deepcopy(base_cfg)

    cases = [
        {
            "label": "PP1 Round Robin",
            "enabled": ("round_robin",),
            "lead_kwargs": {"name": "E2E Round Robin", "need": "Lead test round robin"},
            "verify": lambda lead, _m: (bool(lead.get("owner_id")), f"owner={lead.get('owner_name')}"),
        },
        {
            "label": "PP2 Skill-Based (moi→B/C)",
            "enabled": ("skill_based",),
            "lead_kwargs": {
                "name": "E2E Skill Moi",
                "phone": unique_phone("skill"),
                "need": "Lead mới cần tư vấn",
            },
            "verify": lambda lead, m: (
                check_level(m, lead.get("owner_id"), {"b", "c"}),
                f"tier={lead.get('lead_level')} owner={lead.get('owner_name')} lv={m.get(lead.get('owner_id'), {}).get('sales_level')}",
            ),
        },
        {
            "label": "PP3 Khu vực q.7",
            "enabled": ("region_product", "round_robin"),
            "lead_kwargs": {
                "name": "E2E Region Q7",
                "region": "q.7",
                "product_interest": "căn hộ",
                "need": "Mua căn hộ q.7",
            },
            "verify": lambda lead, m: (
                notes_match(m, lead.get("owner_id"), ["q.7"]),
                f"owner={lead.get('owner_name')} notes={(m.get(lead.get('owner_id'), {}).get('notes') or '')[:45]}",
            ),
        },
        {
            "label": "PP4 Hiệu suất",
            "enabled": ("performance",),
            "lead_kwargs": {"name": "E2E Performance", "need": "Lead test hiệu suất"},
            "verify": lambda lead, _m: (bool(lead.get("owner_id")), f"owner={lead.get('owner_name')}"),
        },
        {
            "label": "PP5 Profile việt kiều",
            "enabled": ("customer_profile",),
            "lead_kwargs": {
                "name": "E2E Viet Kieu",
                "need": "Khách việt kiều cần tư vấn tiếng Anh",
            },
            "verify": lambda lead, m: (
                notes_any(m, lead.get("owner_id"), ["việt kiều", "english"]),
                f"owner={lead.get('owner_name')} notes={(m.get(lead.get('owner_id'), {}).get('notes') or '')[:45]}",
            ),
        },
        {
            "label": "PP6 Hybrid (moi→B/C + RR)",
            "enabled": ("hybrid",),
            "lead_kwargs": {"name": "E2E Hybrid", "need": "Lead hybrid test"},
            "verify": lambda lead, m: (
                check_level(m, lead.get("owner_id"), {"b", "c"}),
                f"tier={lead.get('lead_level')} owner={lead.get('owner_name')}",
            ),
        },
        {
            "label": "Hot min-load (warm_plus→A/B)",
            "enabled": ("skill_based", "hot_priority_min_load"),
            "lead_kwargs": {
                "name": "E2E Hot MinLoad",
                "source": "referral",
                "need": "Hỏi giá gấp xin demo tuần này đầu tư cho thuê ROI",
                "product_interest": "căn hộ cao cấp",
                "region": "q.7",
                "meta": {"budget_vnd": 10_000_000_000, "web_pages_viewed": 20},
            },
            "extra_tiers": [
                {
                    "id": "warm_plus",
                    "label": "WARM+",
                    "min_score": 50,
                    "max_score": 79,
                    "enabled": True,
                    "sort_order": 2,
                    "emoji": "",
                    "description": "",
                    "sla_label": "",
                }
            ],
            "tier_shrink": {"moi": {"max_score": 45}, "normal": {"enabled": False}},
            "verify": lambda lead, m: (
                check_level(m, lead.get("owner_id"), {"a", "b"}),
                f"tier={lead.get('lead_level')} score={lead.get('lead_score')} owner={lead.get('owner_name')}",
            ),
        },
        {
            "label": "VIP → Level S/A",
            "enabled": ("vip_to_level_s", "skill_based"),
            "lead_kwargs": {
                "name": "E2E VIP Client",
                "source": "referral",
                "need": "Hỏi giá gấp xin demo tuần này đầu tư cho thuê ROI",
                "product_interest": "căn hộ cao cấp",
                "region": "q.7",
                "meta": {"budget_vnd": 10_000_000_000, "web_pages_viewed": 20},
            },
            "tier_patch": {"id": "vip", "values": {"min_score": 50, "max_score": 100}},
            "tier_shrink": {"normal": {"enabled": False}, "moi": {"max_score": 49}},
            "verify": lambda lead, m: (
                check_level(m, lead.get("owner_id"), {"s", "a"}),
                f"tier={lead.get('lead_level')} score={lead.get('lead_score')} owner={lead.get('owner_name')}",
            ),
        },
        {
            "label": "Cold → Level C",
            "enabled": ("cold_to_level_c", "skill_based"),
            "lead_kwargs": {
                "name": "E2E Cold Lead",
                "need": "Chỉ hỏi tham khảo",
                "source": "facebook",
            },
            "level_tiers_override": [
                {
                    "id": "cold",
                    "label": "COLD",
                    "min_score": 0,
                    "max_score": 100,
                    "enabled": True,
                    "sort_order": 1,
                    "emoji": "",
                    "description": "",
                    "sla_label": "",
                }
            ],
            "verify": lambda lead, m: (
                check_level(m, lead.get("owner_id"), {"c"}),
                f"tier={lead.get('lead_level')} owner={lead.get('owner_name')} lv={m.get(lead.get('owner_id'), {}).get('sales_level')}",
            ),
        },
    ]

    results = []
    try:
        for case in cases:
            try:
                r = run_case(c, smap, base_cfg, case)
            except Exception as exc:
                r = {
                    "method": case["label"],
                    "enabled": ", ".join(case["enabled"]),
                    "ok": False,
                    "detail": str(exc),
                    "owner": "-",
                    "level": "-",
                    "score": "-",
                    "lead_id": "-",
                }
            results.append(r)
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"[{mark}] {r['method']}")
            print(f"       Lead #{r.get('lead_id')} | tier={r.get('level')} score={r.get('score')}")
            print(f"       → {r.get('owner')} | {r.get('detail')}\n")
    finally:
        c.request("PUT", "/api/crm/leads/config", data=orig_cfg)
        restore_staff(c, staff_saved)
        print("✓ Đã khôi phúc cấu hình và dữ liệu NV\n")

    passed = sum(1 for r in results if r["ok"])
    print("=" * 60)
    print(f"Kết quả E2E: {passed}/{len(results)} PASS")
    print("=" * 60)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    ADMIN_USER = os.getenv("ADMIN_USERNAME", ADMIN_USER)
    ADMIN_PASS = os.getenv("ADMIN_PASSWORD", ADMIN_PASS)
    raise SystemExit(main())
