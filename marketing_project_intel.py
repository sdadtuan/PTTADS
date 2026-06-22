"""Tra cứu dự án PTT + nghiên cứu thị trường — phục vụ chatbox KPI/KHMKT."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from marketing_execution import normalize_query

# Gợi ý dự án thị trường (fallback khi không có OpenAI / web)
MARKET_PROJECT_HINTS: dict[str, dict[str, Any]] = {
    "vinhomes saigon park": {
        "project_name": "Vinhomes Saigon Park",
        "aliases": ["vinhomes hoc mon", "vinhomes hóc môn", "sai gon park", "khu do thi dai hoc quoc te"],
        "developer": "Vingroup (Vinhomes)",
        "location": "Xã Xuân Thới Sơn / Tân Thới Nhì, Hóc Môn — cửa ngõ Tây Bắc TP.HCM (QL22, Đặng Công Bình)",
        "segment": "BĐS đại đô thị — Campus City / đô thị đại học quốc tế",
        "scale": "~880–1.080 ha · ~135.000 cư dân · ~60.000 sinh viên dự kiến",
        "products": "Căn hộ, nhà phố, shophouse, biệt thự đơn/song lập",
        "timeline_market": "Khởi công 2025–2026 · mở bán GĐ1 ~Q2/2026 · bàn giao thấp tầng 2027–2028",
        "usp": "Siêu đô thị tích hợp giáo dục quốc tế, hạ tầng QL22/Vành đai 3/Metro mở rộng, thương hiệu Vinhomes",
        "icp": "Gia đình trẻ TP.HCM & vùng ven (Bình Dương, Long An), nhà đầu tư BĐS, người mua ở thực 35–55 tuổi, thu nhập trung–cao",
        "competitors": "Masteri, Ecopark, Gem Sky World, các dự án ven TP.HCM cùng phân khúc",
        "smart_goal": "Thu hút ≥2.000 lead chất lượng/tháng giai đoạn pre-launch, CPL ≤350k, chuyển đổi giữ chỗ/booking ≥8%",
        "recommended_channels": [
            {"name": "Meta Ads", "goal": "Lead + video awareness", "kpi": "CPL ≤280k", "budget_pct": 30},
            {"name": "Google Search/YouTube", "goal": "Intent mua nhà", "kpi": "CPL ≤400k", "budget_pct": 25},
            {"name": "TikTok/Video", "goal": "Awareness tiến độ", "kpi": "CPV ≤900", "budget_pct": 15},
            {"name": "Landing/CRO", "goal": "Giữ chỗ / form", "kpi": "CVR ≥5%", "budget_pct": 10},
            {"name": "Telesales/SDR", "goal": "Qualify & booking", "kpi": "Contact ≥55%", "budget_pct": 10},
            {"name": "KOL/PR địa phương", "goal": "Tin cậy vùng Hóc Môn", "kpi": "Reach + branded search", "budget_pct": 5},
            {"name": "Dự phòng", "goal": "Test creative", "kpi": "—", "budget_pct": 5},
        ],
        "risks_market": "Cạnh tranh lead BĐS; pháp lý/chính sách; kỳ vọng giá cao; lead ảo từ ads",
        "sources_note": "Thông tin công khai Vinhomes, báo chí BĐS 2025–2026 (quy mô, vị trí, timeline pre-launch).",
    },
}

FORCE_GENERATE_KEYWORDS = (
    "tao file",
    "tạo file",
    "ta file",
    "du roi",
    "đủ rồi",
    "ok tao",
    "ok tạo",
    "generate",
    "tạo ngay",
    "tao ngay",
    "bo qua",
    "bỏ qua",
    "khong can hoi",
    "không cần hỏi",
)

MARKET_BRAND_KEYWORDS = (
    "vinhomes",
    "masteri",
    "ecopark",
    "novaland",
    "gamuda",
    "capitaland",
    "metropolics",
    "sunshine",
    "bds",
    "bat dong san",
    "bất động sản",
    "chung cu",
    "chung cư",
    "du an",
    "dự án",
    "can ho",
    "căn hộ",
    "nha pho",
    "nhà phố",
    "shophouse",
    "biet thu",
    "biệt thự",
)


def _norm_tokens(text: str) -> set[str]:
    q = normalize_query(text)
    return {t for t in re.split(r"[\s\-_/]+", q) if len(t) >= 2}


def _similarity(a: str, b: str) -> float:
    ta, tb = _norm_tokens(a), _norm_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return inter / max(len(ta), len(tb))


def match_ptt_project(brief: str, projects: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    """Tìm dự án trong portfolio PTT (admin/projects)."""
    best: dict[str, Any] | None = None
    best_score = 0.0
    brief_norm = normalize_query(brief)
    for p in projects:
        title = str(p.get("title") or "").strip()
        if not title:
            continue
        score = _similarity(brief, title)
        if normalize_query(title) in brief_norm or brief_norm in normalize_query(title):
            score = max(score, 0.75)
        if score > best_score:
            best_score = score
            best = p
    if best_score >= 0.45:
        return best, best_score
    return None, best_score


def _detect_market_hint_key(brief: str) -> str | None:
    q = normalize_query(brief)
    for key, data in MARKET_PROJECT_HINTS.items():
        if key in q:
            return key
        for alias in data.get("aliases") or []:
            if normalize_query(str(alias)) in q:
                return key
    return None


def _looks_like_market_project(brief: str) -> bool:
    q = normalize_query(brief)
    return any(k in q for k in MARKET_BRAND_KEYWORDS) or _detect_market_hint_key(brief) is not None


def _openai_market_research(project_name: str, brief: str, *, api_key: str) -> dict[str, Any] | None:
    system = (
        "Bạn là chuyên gia nghiên cứu thị trường marketing Việt Nam. "
        "Phân tích dự án/chiến dịch và trả JSON (không markdown) với key: "
        "project_name, developer, location, segment, products, usp, icp, competitors, "
        "smart_goal, timeline_market, recommended_channels (array {name, goal, kpi, budget_pct}), "
        "risks_market, sources_note. "
        "Chỉ dùng thông tin bạn biết chắc về dự án thị trường VN; nếu không chắc ghi 'Cần xác minh'."
    )
    payload = json.dumps(
        {
            "model": os.environ.get("OPENAI_MODEL") or os.environ.get("AI_CHAT_MODEL") or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Dự án: {project_name}\n\nBrief:\n{brief[:2500]}"},
            ],
            "max_tokens": 1800,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw = str(data["choices"][0]["message"]["content"]).strip()
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def research_market_project(brief: str, project_name: str) -> dict[str, Any] | None:
    hint_key = _detect_market_hint_key(brief) or _detect_market_hint_key(project_name)
    if hint_key:
        return dict(MARKET_PROJECT_HINTS[hint_key])
    if not _looks_like_market_project(brief):
        return None
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        ai = _openai_market_research(project_name, brief, api_key=api_key)
        if ai:
            ai["source"] = "openai_research"
            return ai
    return None


def _brief_has_budget(brief: str) -> bool:
    q = normalize_query(brief)
    if any(k in q for k in ("ty", "tỷ", "trieu", "triệu", "tr ", " ty", "vnd", "vnđ", "ngan sach", "ngân sách", "budget")):
        return bool(re.search(r"\d", brief))
    return False


def _brief_has_objective(brief: str) -> bool:
    q = normalize_query(brief)
    return any(
        k in q
        for k in (
            "lead",
            "mql",
            "ban hang",
            "bán hàng",
            "nhan dien",
            "nhận diện",
            "brand",
            "awareness",
            "giu chan",
            "giữ chân",
            "chuyen doi",
            "chuyển đổi",
            "booking",
            "giu cho",
            "giữ chỗ",
            "pre-launch",
            "mo ban",
            "mở bán",
        )
    )


def _brief_has_icp(brief: str) -> bool:
    q = normalize_query(brief)
    if any(k in q for k in ("icp", "doi tuong", "đối tượng", "khach hang", "khách hàng", "phan khuc", "phân khúc")):
        return True
    return any(k in q for k in ("b2b", "b2c", "gia dinh", "gia đình", "doanh nghiep", "doanh nghiệp", "tuoi", "tuổi"))


def _brief_has_duration(brief: str) -> bool:
    q = normalize_query(brief)
    return bool(
        re.search(r"q[1-4]", q)
        or re.search(r"\d+\s*(tuan|tuần|thang|tháng)", q)
        or "2026" in q
        or "2027" in q
    )


def _extract_project_name_simple(brief: str) -> str:
    raw = str(brief or "").strip()
    for pat in (
        r"(?:ten|tên)\s*(?:du\s*an|dự\s*án|chien\s*dich|chiến\s*dịch)\s*[:\-–]\s*(.+)",
        r"(?:du\s*an|dự\s*án|chien\s*dich|chiến\s*dịch)\s*[:\-–]\s*(.+)",
        r"^(.+?)\s*[\-–—]\s*(?:lead|marketing|quang cao|quảng cáo|bds|bất động sản)",
    ):
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:120]
    first = raw.split("\n")[0].strip()
    return first[:100] if first else ""


def _user_wants_force_generate(brief: str) -> bool:
    q = normalize_query(brief)
    return any(k in q for k in FORCE_GENERATE_KEYWORDS)


def _missing_fields(brief: str, *, has_ptt: bool, has_market: bool) -> list[str]:
    missing: list[str] = []
    name = _extract_project_name_simple(brief)
    if len(name) < 3 and not has_ptt and not has_market:
        missing.append("project_name")
    if not _brief_has_objective(brief):
        missing.append("objective")
    if not _brief_has_icp(brief) and not has_market:
        missing.append("icp")
    if not _brief_has_budget(brief):
        missing.append("budget")
    if not _brief_has_duration(brief):
        missing.append("duration")
    return missing


def _build_clarification_reply(
    *,
    brief: str,
    missing: list[str],
    ptt_project: dict[str, Any] | None,
    ptt_score: float,
    market_intel: dict[str, Any] | None,
) -> str:
    lines: list[str] = []
    proj = _extract_project_name_simple(brief)

    if ptt_project and ptt_score >= 0.45:
        lines.extend(
            [
                f"## ✅ Tìm thấy dự án trong **portfolio PTT**",
                "",
                f"**{ptt_project.get('title', '')}** · _{ptt_project.get('category', '')}_",
                "",
                str(ptt_project.get("description") or "").strip(),
                "",
            ]
        )
    elif market_intel:
        lines.extend(
            [
                f"## 🔍 Nghiên cứu thị trường — **{market_intel.get('project_name', proj)}**",
                "",
                f"**Chủ đầu tư:** {market_intel.get('developer', '—')}",
                f"**Vị trí:** {market_intel.get('location', '—')}",
                f"**Phân khúc:** {market_intel.get('segment', '—')}",
                f"**Sản phẩm:** {market_intel.get('products', '—')}",
                f"**USP:** {market_intel.get('usp', '—')}",
                f"**ICP gợi ý:** {market_intel.get('icp', '—')}",
                f"**Timeline thị trường:** {market_intel.get('timeline_market', '—')}",
                "",
                f"_{market_intel.get('sources_note', 'Nguồn: tổng hợp công khai + khung PTT')}_",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## 📋 Chưa xác định rõ dự án",
                "",
                "Mình **chưa tìm thấy** dự án này trong portfolio PTT và chưa đủ dữ liệu thị trường để tạo file chính xác.",
                "",
            ]
        )

    if missing:
        lines.append("### Cần bổ sung thêm")
        lines.append("")
        field_prompts = {
            "project_name": "- **Tên dự án / chiến dịch** (chính xác như thương mại)",
            "objective": "- **Mục tiêu** (lead gen / giữ chỗ pre-launch / nhận diện thương hiệu / chuyển đổi booking…)",
            "icp": "- **Đối tượng khách hàng** (ICP: tuổi, thu nhập, khu vực, nhu cầu)",
            "budget": "- **Ngân sách marketing** (VD: 500 triệu/quý, 2 tỷ/năm…)",
            "duration": "- **Thời gian** (VD: Q2/2026, 12 tuần pre-launch…)",
        }
        for f in missing:
            if f in field_prompts:
                lines.append(field_prompts[f])
        lines.extend(
            [
                "",
                "_Trả lời thêm các mục trên — hệ thống sẽ nghiên cứu và tạo **KHMKT.xlsx** + **KPI.xlsx**._",
                "",
                "Hoặc gõ **「tạo file」** nếu muốn tạo ngay với thông tin hiện có.",
            ]
        )
    return "\n".join(lines)


def build_enriched_brief(
    brief: str,
    *,
    ptt_project: dict[str, Any] | None,
    market_intel: dict[str, Any] | None,
) -> str:
    parts = [brief.strip()]
    if ptt_project:
        parts.append(
            "\n\n[Portfolio PTT — dự án đã có]\n"
            f"Tên: {ptt_project.get('title', '')}\n"
            f"Loại: {ptt_project.get('category', '')}\n"
            f"Mô tả: {ptt_project.get('description', '')}"
        )
    if market_intel:
        parts.append(
            "\n\n[Nghiên cứu thị trường — dùng cho KHMKT/KPI]\n"
            f"Dự án: {market_intel.get('project_name', '')}\n"
            f"Chủ đầu tư: {market_intel.get('developer', '')}\n"
            f"Vị trí: {market_intel.get('location', '')}\n"
            f"Phân khúc: {market_intel.get('segment', '')}\n"
            f"Sản phẩm: {market_intel.get('products', '')}\n"
            f"USP: {market_intel.get('usp', '')}\n"
            f"ICP: {market_intel.get('icp', '')}\n"
            f"Đối thủ: {market_intel.get('competitors', '')}\n"
            f"Mục tiêu SMART gợi ý: {market_intel.get('smart_goal', '')}\n"
            f"Timeline: {market_intel.get('timeline_market', '')}\n"
            f"Rủi ro thị trường: {market_intel.get('risks_market', '')}"
        )
    return "\n".join(parts)


def apply_intel_to_plan(plan: dict[str, Any], analysis: dict[str, Any]) -> None:
    ptt = analysis.get("ptt_project")
    market = analysis.get("market_intel")
    if ptt:
        plan["ptt_portfolio"] = {
            "id": ptt.get("id"),
            "title": ptt.get("title"),
            "category": ptt.get("category"),
            "description": ptt.get("description"),
        }
        if not plan.get("project_name") or len(str(plan.get("project_name"))) < 4:
            plan["project_name"] = ptt.get("title")
        plan["campaign_name"] = f"{ptt.get('title')} — {plan.get('objective_label', 'Marketing')}"
    if market:
        plan["market_research"] = market
        if market.get("project_name"):
            plan["project_name"] = str(market["project_name"])
        if market.get("icp"):
            plan["icp"] = str(market["icp"])
        if market.get("smart_goal"):
            plan["smart_goal"] = str(market["smart_goal"])
        if market.get("timeline_market") and plan.get("duration", "").startswith("12 tuần"):
            plan["duration"] = str(market["timeline_market"])[:120]
        channels = market.get("recommended_channels")
        if isinstance(channels, list) and channels:
            plan["channels"] = channels
        plan["source"] = plan.get("source", "rule") + "+market_intel"
    brief_raw = str(plan.get("brief_raw") or "")
    if market and market.get("sources_note"):
        plan["brief_raw"] = brief_raw + f"\n\n[Nguồn nghiên cứu] {market['sources_note']}"


def analyze_campaign_brief(
    brief: str,
    *,
    ptt_projects: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Phân tích brief: tra portfolio PTT, nghiên cứu thị trường, xác định còn thiếu gì."""
    projects = ptt_projects or []
    ptt_project, ptt_score = match_ptt_project(brief, projects)
    project_name = _extract_project_name_simple(brief) or (ptt_project or {}).get("title", "")
    market_intel = None
    if not ptt_project or ptt_score < 0.7:
        market_intel = research_market_project(brief, project_name)

    missing = _missing_fields(brief, has_ptt=bool(ptt_project), has_market=bool(market_intel))

    # Đủ thông tin từ nghiên cứu → bớt hỏi
    if market_intel:
        if "icp" in missing and market_intel.get("icp"):
            missing.remove("icp")
        if "objective" in missing and market_intel.get("smart_goal"):
            missing.remove("objective")
    if ptt_project and "project_name" in missing:
        missing.remove("project_name")

    needs_clarification = bool(missing) and len(missing) >= 2
    if len(brief.strip()) < 12:
        needs_clarification = True
    if _user_wants_force_generate(brief):
        needs_clarification = False
    if force:
        needs_clarification = False

    enriched_brief = build_enriched_brief(brief, ptt_project=ptt_project, market_intel=market_intel)
    clarification = _build_clarification_reply(
        brief=brief,
        missing=missing,
        ptt_project=ptt_project,
        ptt_score=ptt_score,
        market_intel=market_intel,
    )

    return {
        "status": "needs_info" if needs_clarification else "ready",
        "missing_fields": missing,
        "ptt_project": ptt_project,
        "ptt_match_score": ptt_score,
        "market_intel": market_intel,
        "enriched_brief": enriched_brief,
        "clarification_reply": clarification,
        "project_name": project_name,
    }
