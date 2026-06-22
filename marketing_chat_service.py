"""Trợ lý chiến lược marketing nội bộ — dùng trong CMS PTT."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from marketing_campaign_kit import KPI_BRIEF_PROMPT
from marketing_execution import EXECUTION_KNOWLEDGE, EXECUTION_MODULES, execution_rule_reply, normalize_query

DEFAULT_WELCOME = (
    "Xin chào! Trợ lý **playbook marketing thực chiến** PTT.\n\n"
    "**7 bước** (A→G lý thuyết + **H→L thực hành**: lộ trình ngày/tuần, template copy, công thức, RACI):\n"
    "1. **Ads** — brief, 14 ngày launch, QA pixel · 2. **TVC/KOL** — 21 ngày sản xuất\n"
    "3. **Excel** (XLS) — ritual T6, báo cáo email · 4. **Funnel** — CRM + email D0-D14\n"
    "5. **Telesales** — SOP SDR, log CRM · 6. **Đa kênh** (ĐK) — workshop 3h\n"
    "7. **Test kênh** — TEST-ID, scale protocol\n\n"
    "Toolbar: **XLS** (tuần) · **ĐK** (đa kênh) · **KPI** (scorecard chiến lược).\n"
    "Bấm nút module để nhận playbook đủ để triển khai ngay."
)

DEFAULT_QUICK_REPLIES: tuple[str, ...] = (
    "Playbook thực chiến Bước 1 — FB/Google Ads (14 ngày)",
    "Playbook Bước 4 — Triển khai funnel + CRM 6 ngày",
    "Playbook Bước 5 — SOP telesales + log CRM",
    "Playbook Bước 6 — KH đa kênh + workshop 3h",
    "Playbook Bước 7 — Đăng ký test + scale protocol",
    "Mẫu báo cáo marketing tuần (Excel T6)",
    "Tải Excel quản lý KPI chiến lược marketing",
    "Tải Excel kế hoạch 12 tuần (XLS)",
)

MARKETING_MODULES: tuple[dict[str, str], ...] = (
    {
        "id": "kpi",
        "label": "KPI & đo lường",
        "prompt": (
            "Playbook KPI chiến lược marketing theo dự án cụ thể. "
            "Hỏi tên chiến dịch/dự án, phân tích 7 bước, tạo KHMKT.xlsx + KPI.xlsx."
        ),
        "action": "prompt_kpi_campaign",
    },
    {
        "id": "metrics",
        "label": "Chỉ số quản lý",
        "prompt": (
            "Thiết kế dashboard chỉ số quản lý marketing (BSC/marketing scorecard): "
            "4–6 nhóm chỉ số (thu hút, chuyển đổi, giữ chân, hiệu quả chi phí, thương hiệu), "
            "định nghĩa công thức, nguồn dữ liệu CRM/ads, kèm bảng markdown."
        ),
    },
    {
        "id": "risk",
        "label": "Quản lý rủi ro",
        "prompt": (
            "Lập ma trận rủi ro chiến dịch marketing: rủi ro ngân sách, creative fatigue, "
            "tracking lỗi, phụ thuộc kênh, tuân thủ quảng cáo — xác suất × tác động, "
            "biện pháp giảm thiểu, owner, kèm flowchart mermaid."
        ),
    },
    {
        "id": "budget",
        "label": "Quản lý ngân sách",
        "prompt": (
            "Xây khung quản lý ngân sách marketing theo quý: phân bổ theo kênh/mục tiêu, "
            "quy tắc reallocate, dự phòng 10%, checkpoint hàng tuần, "
            "kèm pie chart phân bổ và line chart burn rate giả định."
        ),
    },
    {
        "id": "profit",
        "label": "Lợi nhuận & ROMI",
        "prompt": (
            "Phân tích lợi nhuận marketing: CAC, LTV, LTV/CAC, biên đóng góp gross margin sau ads, "
            "ROMI/ROAS, payback period — giả định số minh họa, khuyến nghị tối ưu, "
            "kèm bar chart so sánh kênh theo ROMI."
        ),
    },
)

MARKETING_KNOWLEDGE = """
Bối cảnh PTT Advertising Solutions:
- Creative Martech Platform — tích hợp sáng tạo, dữ liệu và công nghệ marketing.
- Dịch vụ chính: AEO, SEO tổng thể, thiết kế web/landing, quảng cáo đa kênh (Google, Meta, TikTok…), content & social.

Vòng đời khách hàng marketing (CRM PTT):
- KHTN (Khách hàng tiềm năng): thu thập lead, phân khúc, scoring, mục tiêu CPL/MQL.
- KHQT (Khách hàng quan tâm): nurture email/remarketing, đồng bộ sales-marketing, case study.
- CSKH: onboarding, loyalty, NPS/CSAT, giảm churn, tăng LTV.

Quy trình 5 bước KHTN (pipeline thu lead):
1. Nghiên cứu thị trường — TAM/SAM/SOM, đối thủ, xu hướng.
2. Phân khúc thị trường — tiêu chí địa lý, quy mô, ngành, hành vi.
3. Xác định ICP/persona — pain, kênh tin cậy, jobs-to-be-done.
4. Lựa chọn chiến lược tiếp cận — inbound/outbound/partner, thông điệp, media plan.
5. Thử nghiệm quảng cáo — pilot có kiểm soát, đo CPL/CPA/ROAS, quyết định scale.

Khung nghiệp vụ marketing (9 trụ — tham chiếu CRM PTT):
TMMT, thông điệp & định vị, media mix, nội dung, nurture, sales enablement,
đo lường/KPI, ngân sách, rủi ro & tuân thủ.

=== CHỈ SỐ QUẢN LÝ (Marketing Scorecard / BSC) ===
Nhóm chỉ số đề xuất theo 5 trụ:
1) Thu hút & nhận diện: reach, impression share, brand search volume, share of voice.
2) Chuyển đổi & pipeline: CPL, MQL→SQL rate, win rate, pipeline value, velocity.
3) Hiệu quả chi phí: CAC, CPA, ROAS, ROMI, cost per MQL/SQL.
4) Giá trị khách hàng: LTV, retention rate, NPS, upsell/cross-sell rate, churn.
5) Vận hành & chất lượng: SLA lead response, data quality score, tracking accuracy %.

Công thức tham chiếu:
- ROMI = (Doanh thu gán cho marketing − Chi phí marketing) / Chi phí marketing
- LTV = ARPU × Gross margin % × (1 / churn rate)  (hoặc theo cohort thực tế)
- LTV/CAC ≥ 3 thường là ngưỡng lành mạnh B2B SaaS; B2C tùy biên lợi nhuận.
- Payback period = CAC / (ARPU × Gross margin) tháng.

=== KPI ĐO LƯỜNG HIỆU QUẢ (theo mục tiêu) ===
Awareness: reach, frequency, VTR, brand lift, branded search CTR.
Consideration: landing CVR, content engagement, webinar show rate.
Conversion: CPL, CPA, ROAS, form completion rate, SQL acceptance rate.
Retention: NPS, CSAT, repeat purchase, expansion revenue.
Review cadence: daily (ads spend/CPA), weekly (CPL/CVR by channel), monthly (ROMI/LTV cohort).

Ngưỡng cảnh báo (ví dụ): CPA > target 20% trong 7 ngày → pause & audit; CPL tăng 30% WoW → kiểm creative/landing.

=== QUẢN LÝ RỦI RO MARKETING ===
Ma trận rủi ro (Probability × Impact):
- Ngân sách: overspend, under-delivery kênh, seasonality — giải pháp: cap daily, pacing rules.
- Dữ liệu: pixel/GA4 lỗi, attribution sai — giải pháp: QA tracking checklist, holdout test.
- Creative: fatigue, vi phạm policy — giải pháp: refresh 2–4 tuần, library pre-approval.
- Phụ thuộc kênh: 1 kênh >70% lead — giải pháp: diversify media mix.
- Tuân thủ: quảng cáo ngành hạn chế, bản quyền — giải pháp: legal review, whitelist landing.
- Thị trường: đối thủ bid cao, CPM tăng — giải pháp: scenario planning, reserve budget.

=== QUẢN LÝ NGÂN SÁCH ===
Khung phân bổ: Base (kênh đã validate) / Test (pilot) / Reserve (10–15%) / Brand.
Quy trình: annual plan → quarterly reforecast → weekly pacing → monthly variance report.
Chỉ số theo dõi: burn rate, % spent vs plan, CPA vs target, forecast end-of-month spend.
Quy tắc reallocate: chỉ chuyển budget sang kênh đạt CPA/ROAS target ≥14 ngày liên tục.

=== LỢI NHUẬN & HIỆU QUẢ TÀI CHÍNH ===
Contribution margin sau marketing = Revenue − COGS − Variable marketing cost.
ROMI/ROAS theo kênh để ưu tiên scale; dừng kênh LTV/CAC < 1 hoặc payback > 18 tháng (B2B).
Unit economics slide: CAC breakdown, LTV by cohort, margin bridge chart.
""".strip() + "\n\n" + EXECUTION_KNOWLEDGE


def _norm(text: str) -> str:
    return normalize_query(text)


def _settings_flag(settings: dict[str, Any], key: str, *, default: bool = True) -> bool:
    raw = str(settings.get(key, "1" if default else "0")).strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return default


def build_marketing_chat_config(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    s = settings or {}
    welcome = str(s.get("cms_mk_chat_welcome") or "").strip() or DEFAULT_WELCOME
    quick_raw = str(s.get("cms_mk_chat_quick_json") or "").strip()
    quick: list[str] = list(DEFAULT_QUICK_REPLIES)
    if quick_raw:
        try:
            parsed = json.loads(quick_raw)
            if isinstance(parsed, list) and parsed:
                quick = [str(x).strip() for x in parsed if str(x).strip()][:8]
        except ValueError:
            pass
    has_ai = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    return {
        "enabled": _settings_flag(s, "cms_mk_chat_enabled", default=True),
        "title": str(s.get("cms_mk_chat_title") or "Quản trị Marketing").strip(),
        "subtitle": str(s.get("cms_mk_chat_subtitle") or "KPI · Rủi ro · Ngân sách · Lợi nhuận").strip(),
        "welcome": welcome,
        "placeholder": str(
            s.get("cms_mk_chat_placeholder")
            or "Hỏi về KPI, chỉ số quản lý, rủi ro, ngân sách, ROMI/LTV…"
        ).strip(),
        "quick_replies": quick,
        "modules": [dict(m) for m in EXECUTION_MODULES] + [dict(m) for m in MARKETING_MODULES],
        "weekly_plan_xlsx_url": "/api/cms/marketing-chat/weekly-plan.xlsx",
        "multichannel_plan_xlsx_url": "/api/cms/marketing-chat/multichannel-plan.xlsx",
        "kpi_strategy_xlsx_url": "/api/cms/marketing-chat/kpi-strategy.xlsx",
        "kpi_brief_prompt": KPI_BRIEF_PROMPT,
        "campaign_kit_url": "/api/cms/marketing-chat/campaign-kit",
        "ai_enabled": has_ai,
        "ai_note": (
            "Đang dùng OpenAI (OPENAI_API_KEY)."
            if has_ai
            else "Chưa có OPENAI_API_KEY — trả lời theo khung kiến thức PTT."
        ),
    }


def _rule_based_reply(question: str) -> str | None:
    exec_match = execution_rule_reply(question)
    if exec_match:
        return exec_match

    q = _norm(question)
    if not q:
        return None

    rules: list[tuple[tuple[str, ...], str]] = [
        (
            ("stp", "segment", "phan khuc", "targeting", "icp", "persona"),
            (
                "Khung STP gợi ý cho team PTT:\n"
                "1) Segmentation — chia theo ngành, quy mô, hành vi mua, địa lý.\n"
                "2) Targeting — chọn 1–3 phân khúc ưu tiên (size × win-rate × fit sản phẩm).\n"
                "3) Positioning — USP + proof (case, số liệu) + thông điệp nhất quán trên landing/ads.\n"
                "Deliverable: 1 trang persona/ICP dùng chung sales & marketing."
            ),
        ),
        (
            ("media mix", "kenh", "channel", "google ads", "facebook", "meta", "tiktok"),
            (
                "Gợi ý media mix theo mục tiêu:\n"
                "• Lead gen B2B: Search brand + competitor, LinkedIn/Meta lead form, remarketing, landing tối ưu form.\n"
                "• Awareness: Video/YouTube, social organic + paid reach, PR/content.\n"
                "• Performance: 70% budget vào kênh đã chứng minh CPA, 20% test creative/audience, 10% dự phòng.\n"
                "Luôn gắn UTM + CRM để đo CPL theo nguồn.\n\n"
                "```chart-json\n"
                '{"type":"pie","title":"Phân bổ ngân sách media (gợi ý)","labels":["Performance đã validate","Thử nghiệm","Dự phòng/Brand"],"values":[65,25,10]}\n'
                "```"
            ),
        ),
        (
            ("kpi", "chi so", "metric", "cpl", "cpa", "roas", "ctr", "cvr", "do luong", "hieu qua"),
            (
                "**KPI đo lường hiệu quả marketing (PTT)**\n\n"
                "| Giai đoạn | KPI dẫn dắt | KPI kết quả | Ngưỡng review |\n"
                "|---|---|---|---|\n"
                "| Awareness | Reach, Frequency | Brand search lift | Tuần |\n"
                "| KHTN | CTR, CPC | CPL, MQL rate | Ngày/tuần |\n"
                "| KHQT | Open/click nurture | SQL rate, meeting booked | Tuần |\n"
                "| CSKH | NPS response | Retention, LTV, upsell | Tháng |\n\n"
                "**Cadence:** Daily — spend/CPA; Weekly — CPL/CVR theo kênh; Monthly — ROMI/LTV cohort.\n\n"
                "📥 **Tạo Excel theo dự án:** bấm nút **KPI** → mô tả chiến dịch → nhận **KHMKT.xlsx** (7 bước) + **KPI.xlsx** (dashboard RAG).\n\n"
                "```chart-json\n"
                '{"type":"bar","title":"KPI mục tiêu vs thực tế (minh họa)","labels":["CPL","CPA","ROAS","MQL rate"],"values":[85,92,78,88]}\n'
                "```"
            ),
        ),
        (
            ("chi so quan ly", "scorecard", "dashboard", "bsc", "balanced scorecard", "quan tri"),
            (
                "**Marketing Scorecard — 5 trụ chỉ số quản lý**\n\n"
                "1. **Thu hút:** reach, SOV, branded search volume\n"
                "2. **Chuyển đổi:** CPL, MQL→SQL, win rate, pipeline velocity\n"
                "3. **Hiệu quả chi phí:** CAC, ROMI, cost/MQL\n"
                "4. **Giá trị KH:** LTV, churn, NPS, expansion revenue\n"
                "5. **Vận hành:** SLA phản hồi lead, tracking accuracy %\n\n"
                "Deliverable: 1 trang dashboard (Looker/Sheet) + owner từng chỉ số + tần suất họp review.\n\n"
                "```mermaid\nflowchart LR\n  A[Thu hút] --> B[Chuyển đổi]\n  B --> C[Hiệu quả CP]\n  C --> D[Giá trị KH]\n  D --> E[Vận hành]\n```"
            ),
        ),
        (
            ("rui ro", "risk", "risk management", "quan ly rui ro", "giam thieu"),
            (
                "**Ma trận quản lý rủi ro marketing**\n\n"
                "| Rủi ro | Xác suất | Tác động | Giảm thiểu |\n"
                "|---|---|---|---|\n"
                "| Overspend ngân sách | TB | Cao | Daily cap, pacing rules |\n"
                "| Tracking/GA4 lỗi | TB | Cao | QA checklist, holdout test |\n"
                "| Creative fatigue | Cao | TB | Refresh 2–4 tuần |\n"
                "| Phụ thuộc 1 kênh >70% | TB | Cao | Diversify media mix |\n"
                "| Vi phạm policy ads | Thấp | Cao | Pre-approval, whitelist |\n\n"
                "**Quy trình:** Identify → Assess → Mitigate → Monitor (review hàng tháng).\n\n"
                "```mermaid\nflowchart TD\n  R[Phát hiện rủi ro] --> A{Impact cao?}\n  A -->|Có| M[Kích hoạt kế hoạch giảm thiểu]\n  A -->|Không| W[Theo dõi]\n  M --> Review[Review tuần]\n```"
            ),
        ),
        (
            ("ngan sach", "budget", "chi phi", "allocation", "burn rate", "pacing"),
            (
                "**Khung quản lý ngân sách marketing**\n\n"
                "**Phân bổ đề xuất:**\n"
                "• Base 60–65% — kênh đã validate CPA/ROAS\n"
                "• Test 20–25% — pilot creative/audience mới\n"
                "• Reserve 10–15% — dự phòng / brand\n\n"
                "**Chỉ số theo dõi:** burn rate, % spent vs plan, forecast EOM, variance MoM.\n"
                "**Quy tắc reallocate:** Chỉ scale kênh đạt target ≥14 ngày liên tục.\n\n"
                "```chart-json\n"
                '{"type":"pie","title":"Phân bổ ngân sách quý","labels":["Base/Performance","Test/Pilot","Reserve","Brand"],"values":[62,23,10,5]}\n'
                "```\n\n"
                "```chart-json\n"
                '{"type":"line","title":"Burn rate vs kế hoạch (minh họa %/tháng)","labels":["T1","T2","T3","T4","T5","T6"],"values":[12,28,45,58,72,85]}\n'
                "```"
            ),
        ),
        (
            ("loi nhuan", "profit", "romi", "ltv", "cac", "margin", "bien dong gop", "payback", "unit economics"),
            (
                "**Phân tích lợi nhuận & unit economics marketing**\n\n"
                "**Công thức cốt lõi:**\n"
                "• ROMI = (Revenue attributed − Marketing cost) / Marketing cost\n"
                "• LTV = ARPU × Gross margin × (1/churn) — ưu tiên cohort thực tế\n"
                "• LTV/CAC ≥ 3 (B2B SaaS tham chiếu); Payback = CAC / (ARPU × margin)\n"
                "• Contribution margin = Revenue − COGS − Variable marketing\n\n"
                "**Quyết định scale:** Scale kênh ROMI > 0 và LTV/CAC > ngưỡng; dừng nếu payback > 18 tháng.\n\n"
                "```chart-json\n"
                '{"type":"bar","title":"ROMI theo kênh (minh họa %)","labels":["Google Ads","Meta","SEO","Email","Partner"],"values":[120,85,210,160,95]}\n'
                "```"
            ),
        ),
        (
            ("khtn", "5 buoc", "pipeline", "thu lead", "lead gen"),
            (
                "Quy trình 5 bước KHTN (PTT CRM):\n"
                "1. Nghiên cứu thị trường — insight + giả định cần kiểm chứng.\n"
                "2. Phân khúc — ma trận ưu tiên phân khúc.\n"
                "3. ICP/Persona — pain, kênh, phản đối thường gặp.\n"
                "4. Chiến lược tiếp cận — mix kênh + thông điệp + media plan 1 trang.\n"
                "5. Pilot có kiểm soát — đo CPL/CPA, quyết định dừng/tối ưu/scale.\n\n"
                "```mermaid\nflowchart TD\n  A[1. Nghiên cứu TT] --> B[2. Phân khúc]\n  B --> C[3. ICP/Persona]\n  C --> D[4. Chiến lược tiếp cận]\n  D --> E[5. Pilot & scale]\n```"
            ),
        ),
        (
            ("inbound", "outbound", "content", "seo", "aeo"),
            (
                "Inbound vs Outbound:\n"
                "• Inbound (SEO/AEO, content, webinar): chi phí biên giảm dần, cần thời gian, phù hợp trust dài hạn.\n"
                "• Outbound (ads, cold outreach, event): tốc độ nhanh, cần đo CPL/CPA chặt.\n"
                "PTT thường phối hợp: ads thúc tốc + SEO/AEO giữ nền + nurture chuyển KHTN→KHQT."
            ),
        ),
        (
            ("funnel", "nurture", "khqt", "remarketing"),
            (
                "Funnel KHTN → KHQT:\n"
                "• Top: content/ads thu lead → form/landing có scoring.\n"
                "• Mid: email sequence, remarketing, case study theo ngành.\n"
                "• Bottom: demo/tư vấn, SLA sales ≤24–48h, CRM ghi đủ context.\n"
                "Tránh đổ traffic vào landing yếu CVR — tối ưu trang đích trước khi scale budget."
            ),
        ),
    ]

    best_score = 0
    best_answer: str | None = None
    for keywords, answer in rules:
        for kw in keywords:
            if kw in q:
                score = len(kw)
                if score > best_score:
                    best_score = score
                    best_answer = answer
    return best_answer


def _build_system_prompt(settings: dict[str, Any]) -> str:
    custom = str(settings.get("cms_mk_chat_system_prompt") or "").strip()
    if custom:
        return custom[:8000]
    brand = str(settings.get("brand_name") or "PTT Advertising Solutions").strip()
    return (
        f"Bạn là chuyên gia **quản trị marketing cấp cao** (CMO advisor) nội bộ cho {brand}.\n"
        "Trả lời bằng tiếng Việt, chuyên sâu, có số liệu minh họa và khuyến nghị hành động.\n\n"
        "5 MODULE CHUYÊN SÂU (luôn ưu tiên khi câu hỏi liên quan):\n"
        "1) **Chỉ số quản lý** — Marketing Scorecard/BSC, dashboard, owner, nguồn dữ liệu.\n"
        "2) **KPI đo lường hiệu quả** — leading/lagging, ngưỡng cảnh báo, cadence review.\n"
        "3) **Quản lý rủi ro** — ma trận P×I, mitigations, monitoring.\n"
        "4) **Quản lý ngân sách** — phân bổ, pacing, burn rate, reallocate rules.\n"
        "5) **Lợi nhuận** — CAC, LTV, LTV/CAC, ROMI, contribution margin, payback.\n\n"
        "7 BƯỚC THỰC THI (tag [BUOC:id] — playbook áp dụng thực tiễn):\n"
        "Khung **A→G** (mục tiêu, input, quy trình, deliverable, KPI, rủi ro, checklist) +\n"
        "**H→L** (lộ trình ngày/tuần, template copy-paste, công thức, RACI, lỗi thường gặp).\n"
        "1) Ads — brief, campaign structure, QA, 14 ngày.\n"
        "2) TVC/KOL — 21 ngày sản xuất, shot list, legal.\n"
        "3) Excel — ritual T6, báo cáo, RACI; nút XLS.\n"
        "4) Funnel — CRM setup, email D0-D14, SLA 4h.\n"
        "5) Telesales — SOP SDR, CRM log, follow-up cadence.\n"
        "6) Đa kênh — workshop, budget rules; nút ĐK.\n"
        "7) Test — TEST-ID, min sample, scale +20%.\n\n"
        "Cấu trúc mỗi câu trả lời (khi phù hợp):\n"
        "1) **Tóm tắt điều hành** — 2–3 câu kết luận + quyết định đề xuất.\n"
        "2) **Phân tích chi tiết** — bảng markdown, công thức, benchmark.\n"
        "3) **Chỉ số/KPI cụ thể** — tên, công thức, mục tiêu, tần suất đo.\n"
        "4) **Rủi ro & kiểm soát** — ít nhất 2–3 rủi ro + biện pháp.\n"
        "5) **Deliverable** — tài liệu/dashboard/bước triển khai tuần này.\n"
        "6) **Biểu đồ** — chart-json cho số liệu; mermaid cho quy trình/ma trận.\n\n"
        "Biểu đồ Mermaid — ```mermaid ... ``` | Chart.js — ```chart-json {\"type\":\"bar|pie|line\",...} ```\n\n"
        "Nếu thiếu ngữ cảnh (ngành, quy mô, doanh thu, ngân sách), hỏi lại 1–2 câu trước khi chốt.\n\n"
        f"{MARKETING_KNOWLEDGE}"
    )


def _openai_reply(
    question: str,
    history: list[dict[str, Any]],
    settings: dict[str, Any],
    api_key: str,
) -> str:
    system = _build_system_prompt(settings)
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in history[-10:]:
        role = str(m.get("role") or "")
        text = str(m.get("text") or "").strip()[:2000]
        if not text:
            continue
        if role == "user":
            messages.append({"role": "user", "content": text})
        elif role in ("assistant", "bot"):
            messages.append({"role": "assistant", "content": text})
    messages.append({"role": "user", "content": question[:2000]})

    payload = json.dumps(
        {
            "model": (
                os.environ.get("OPENAI_MODEL")
                or os.environ.get("AI_CHAT_MODEL")
                or "gpt-4o-mini"
            ),
            "messages": messages,
            "max_tokens": 2200,
            "temperature": 0.5,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data["choices"][0]["message"]["content"]).strip()


def _openai_error_hint(exc: Exception) -> str:
    import urllib.error

    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 429:
            return "429 — vượt quota hoặc rate limit OpenAI"
        if exc.code == 401:
            return "401 — API key không hợp lệ"
        return f"HTTP {exc.code}"
    return type(exc).__name__


def build_marketing_strategy_reply(
    question: str,
    history: list[dict[str, Any]] | None,
    settings: dict[str, Any] | None = None,
) -> str:
    text = str(question or "").strip()
    if not text:
        return "Vui lòng nhập câu hỏi về chiến lược marketing."
    if len(text) > 4000:
        text = text[:4000]

    s = settings or {}
    matched = _rule_based_reply(text)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if matched:
        return matched

    if api_key:
        try:
            return _openai_reply(text, history or [], s, api_key)
        except Exception as exc:
            api_hint = _openai_error_hint(exc)
            brand = str(s.get("brand_name") or "PTT Advertising Solutions").strip()
            return (
                f"Cảm ơn bạn đã hỏi về «{text[:80]}{'…' if len(text) > 80 else ''}».\n\n"
                "Gợi ý khung trả lời:\n"
                "• Làm rõ mục tiêu (awareness / lead / retention) và phân khúc mục tiêu.\n"
                "• Chọn 2–3 kênh trọng tâm + KPI đo lường (CPL, ROAS, brand search…).\n"
                "• Lập pilot 2–4 tuần trước khi scale ngân sách.\n\n"
                f"OpenAI đã cấu hình trong PTT/.env nhưng chưa trả lời được ({api_hint}). "
                f"Bạn có thể thử lại sau, hoặc dùng CRM → Kế hoạch marketing tại {brand}."
            )

    brand = str(s.get("brand_name") or "PTT Advertising Solutions").strip()
    return (
        f"Cảm ơn bạn đã hỏi về «{text[:80]}{'…' if len(text) > 80 else ''}».\n\n"
        "Gợi ý khung trả lời:\n"
        "• Làm rõ mục tiêu (awareness / lead / retention) và phân khúc mục tiêu.\n"
        "• Chọn 2–3 kênh trọng tâm + KPI đo lường (CPL, ROAS, brand search…).\n"
        "• Lập pilot 2–4 tuần trước khi scale ngân sách.\n\n"
        f"Thêm OPENAI_API_KEY vào PTT/.env để nhận tư vấn chi tiết hơn, "
        f"hoặc dùng CRM → Kế hoạch marketing tại {brand}."
    )


def _role_label(role: str) -> str:
    return "Bạn" if role == "user" else "Trợ lý MK"


def build_export_markdown(messages: list[dict[str, Any]], *, brand: str = "PTT Advertising Solutions") -> str:
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Bản ghi chiến lược marketing — {brand}",
        f"_Xuất lúc {ts}_",
        "",
    ]
    for m in messages:
        role = str(m.get("role") or "")
        text = str(m.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"## {_role_label(role)}")
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_export_html(messages: list[dict[str, Any]], *, brand: str = "PTT Advertising Solutions") -> str:
    from datetime import datetime, timezone
    from html import escape

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        "<!DOCTYPE html><html lang='vi'><head><meta charset='utf-8'>",
        f"<title>Chiến lược marketing — {escape(brand)}</title>",
        "<script src='https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js'></script>",
        "<script>mermaid.initialize({startOnLoad:true,theme:'neutral'});</script>",
        "<style>body{font-family:Inter,system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#13233f}"
        "h1{color:#2f7238}.msg{margin:1.25rem 0;padding:1rem;border:1px solid #d8deeb;border-radius:12px;background:#f6faf7}"
        ".meta{font-size:.75rem;color:#59657d;text-transform:uppercase;margin-bottom:.5rem}"
        "pre{background:#fff;padding:.75rem;border-radius:8px;overflow:auto;font-size:.85rem}"
        ".mermaid{margin:1rem 0}</style></head><body>",
        f"<h1>Chiến lược marketing — {escape(brand)}</h1>",
        f"<p><em>Xuất lúc {escape(ts)}</em></p>",
    ]
    for m in messages:
        role = str(m.get("role") or "")
        text = str(m.get("text") or "").strip()
        if not text:
            continue
        body = escape(text).replace("\n", "<br>")
        # Preserve mermaid blocks for rendering
        body = re.sub(
            r"```mermaid\s*([\s\S]*?)```",
            lambda mo: f"<pre class='mermaid'>{escape(mo.group(1).strip())}</pre>",
            text,
        )
        if "```mermaid" not in text:
            body = escape(text).replace("\n", "<br>")
        else:
            chunks = re.split(r"(```mermaid[\s\S]*?```)", text)
            body = ""
            for chunk in chunks:
                mm = re.match(r"```mermaid\s*([\s\S]*?)```", chunk.strip())
                if mm:
                    body += f"<pre class='mermaid'>{escape(mm.group(1).strip())}</pre>"
                elif chunk.strip():
                    body += f"<div>{escape(chunk.strip()).replace(chr(10), '<br>')}</div>"
        parts.append(f"<div class='msg'><div class='meta'>{escape(_role_label(role))}</div>{body}</div>")
    parts.append("</body></html>")
    return "\n".join(parts)
