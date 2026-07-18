#!/usr/bin/env python3
"""Generate HTML lead intake forms for PTT — gọi lead + gặp trực tiếp."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "forms" / "lead-intake"

sys.path.insert(0, str(ROOT))
from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS  # noqa: E402

NAVY = "#0F172A"
ACCENT = "#2563EB"

SERVICE_SLUGS = [
    "dich-vu-seo-tong-the",
    "dich-vu-aeo",
    "dich-vu-seo-local",
    "dich-vu-seo-audit",
    "dich-vu-quan-tri-website",
    "thiet-ke-website",
    "thiet-ke-website-tron-goi",
    "thiet-ke-landing-page",
    "quang-cao-facebook",
    "quang-cao-google",
    "thue-tai-khoan-quang-cao",
    "tiep-thi-noi-dung",
]

COMMON_OBJECTIONS = [
    ("Giá cao / vượt ngân sách", "Hỏi ngân sách thực tế; so sánh chi phí cơ hội; đề xuất gói nhỏ hơn hoặc milestone."),
    ("Đang làm với agency khác", "Hỏi điểm không hài lòng; đề xuất audit độc lập hoặc pilot 1–3 tháng."),
    ("Cần suy nghĩ / hỏi sếp", "Xác định decision maker; đặt lịch gặp có người quyết định; gửi 1-pager trước."),
    ("Chưa có website / chưa sẵn sàng", "Đề xuất lộ trình: web trước → SEO/Ads; nurture với checklist chuẩn bị."),
    ("Kỳ vọng kết quả quá nhanh", "Chia sẻ timeline thực tế + case study; cam kết milestone đo được."),
    ("Tự làm được / có team nội bộ", "Hỏi bottleneck; đề xuất hybrid (PTT audit + team nội bộ triển khai)."),
    ("Không tin agency / bị scam trước", "Chia sẻ case, hợp đồng minh bạch, KPI cam kết, báo cáo định kỳ."),
    ("Chỉ hỏi giá, không chia sẻ thông tin", "Giải thích cần context để báo giá chính xác; đề xuất call 15p miễn phí."),
]

BANT_ROWS = [
    ("Budget", "Ngân sách thực tế/tháng hoặc dự án? Ai duyệt chi?"),
    ("Authority", "Ai ký HĐ? Ai quyết định cuối cùng?"),
    ("Need", "Pain point #1? Hậu quả nếu không giải quyết?"),
    ("Timeline", "Khi nào cần bắt đầu? Deadline campaign/go-live?"),
    ("Fit", "Phù hợp ICP PTT? Scope trong năng lực?"),
    ("History", "Đã thử gì? Agency cũ? Kết quả?"),
]

STAKEHOLDER_ROWS = [
    ("Decision Maker", "Người ký HĐ / quyết định ngân sách"),
    ("Influencer", "Người đề xuất / ảnh hưởng quyết định"),
    ("Gatekeeper", "Người lọc thông tin / PA / kế toán"),
    ("User", "Người dùng hàng ngày / vận hành"),
]

CALL_SCRIPTS = [
    (
        "Biến thể A — Lead inbound (form/chat)",
        '"Chào anh/chị [Tên], em [AM] từ PTT — agency digital marketing. '
        'Em thấy anh/chị quan tâm [dịch vụ]. Em gọi 15 phút để hiểu nhu cầu và xem PTT có phù hợp không, '
        'không ép mua. Anh/chị có 15 phút không ạ?"',
    ),
    (
        "Biến thể B — Referral / giới thiệu",
        '"Chào anh/chị, em [AM] PTT — [Người giới thiệu] nhờ em liên hệ vì anh/chị đang cần [dịch vụ]. '
        'Em muốn hỏi vài câu để chuẩn bị buổi tư vấn phù hợp. 15 phút được không ạ?"',
    ),
    (
        "Biến thể C — Outbound / tái kích hoạt",
        '"Chào anh/chị, em [AM] PTT. Trước anh/chị từng quan tâm [dịch vụ]. '
        'Em gọi cập nhật case mới ngành [X] và xem nhu cầu hiện tại — 15 phút, không bán hàng ép buộc ạ."',
    ),
]

DEEP_DISCOVERY_COMMON = [
    "Mục tiêu kinh doanh 6–12 tháng tới? KPI đo thành công?",
    "Khách hàng lý tưởng (ICP) của anh/chị là ai?",
    "Điểm đau lớn nhất hiện tại? Đã thử giải pháp nào?",
    "Quy trình duyệt chi / ký HĐ nội bộ như thế nào?",
    "Đối thủ chính? Anh/chị muốn khác biệt ở đâu?",
    "Team marketing hiện tại: ai làm gì? Thiếu gì?",
    "Ngân sách đã duyệt hay đang xin duyệt?",
    "Timeline bắt buộc (campaign, mùa vụ, board meeting)?",
    "Rủi ro lớn nhất nếu chọn sai đối tác?",
    "Tiêu chí chọn agency (giá, case, SLA, báo cáo)?",
]

# Form chung — qualify trước khi xác định dịch vụ (CRM web + HTML)
COMMON_PHONE_QUESTIONS = [
    "Anh/chị đang quan tâm dịch vụ gì? (SEO / Ads / Web / Content / chưa rõ?)",
    "Website/domain hiện tại (nếu có)?",
    "Pain point #1 cần giải quyết gấp nhất?",
    "Ngân sách dự kiến (range/tháng hoặc dự án)? Ai duyệt chi?",
    "Timeline bắt đầu mong muốn?",
    "Ai là decision maker / người ký HĐ?",
    "Đã thử agency hoặc tự làm gì trước đây? Kết quả?",
    "KPI đo thành công là gì (traffic, lead, doanh thu…)?",
    "Ngành / quy mô DN / thị trường chính?",
    "Lead đến từ đâu — kỳ vọng cụ thể từ PTT?",
    "Có deadline campaign / mùa vụ / họp board không?",
    "Dịch vụ nào ưu tiên nhất nếu phải chọn một?",
]

COMMON_RED_FLAGS = [
    "Chưa rõ nhu cầu — chỉ hỏi giá",
    "Không có ngân sách / từ chối nêu range",
    "Không tiếp cận được decision maker",
    "Kỳ vọng không thực tế (kết quả trong 1–2 tuần)",
    "Từ chối chia sẻ thông tin cơ bản",
    "Ghost sau 2 lần follow-up",
    "So sánh giá với freelancer không cùng scope",
    "Đa dịch vụ nhưng không ưu tiên — khó scope",
]

COMMON_URGENCY = [
    "Campaign / mùa vụ sắp tới",
    "Traffic / lead tụt gấp",
    "Website lỗi / downtime",
    "Hết hạn agency cũ",
    "Board / sếp yêu cầu báo cáo gấp",
    "Đối thủ vượt mặt trên digital",
]

COMMON_DEMO_CHECKLIST = [
    "Crawl website sơ bộ",
    "Check PageSpeed / CWV",
    "Xem GBP / Ads account (nếu có)",
    "Phân tích 1 competitor",
    "Show dashboard mẫu PTT",
]

COMMON_DOCS = [
    ("Website URL / domain", "☐", "☐"),
    ("Screenshot analytics (GSC/GA4/Ads)", "☐", "☐"),
    ("Brand guideline / logo", "☐", "☐"),
    ("Brief nhu cầu / pain point", "☐", "☐"),
    ("Ngân sách & timeline xác nhận", "☐", "☐"),
]

COMMON_KPI_QUESTIONS = [
    "Mục tiêu KPI 3–6 tháng realistic?",
    "Metric chính: traffic, lead hay doanh thu?",
    "Baseline hiện tại đo được không?",
]

COMMON_SCOPE_QUESTIONS = [
    "IN: dịch vụ nào trong phạm vi PTT?",
    "OUT: gì KH tự làm hoặc đã có vendor?",
    "Pilot 1–3 tháng trước cam kết dài hạn?",
]

COMMON_FORM_SLUG = "_common"


def build_common_form_dict() -> dict:
    """Định nghĩa form chung — dùng CRM web + fallback slug lạ."""
    scripts = " ".join(
        f"[{title}] {text}" for title, text in CALL_SCRIPTS
    )
    return {
        "title": "Form chung — chưa xác định dịch vụ",
        "group": "Mọi dịch vụ PTT",
        "overview": "Qualify lead trước khi biết chính xác dịch vụ. Sau khi rõ → chuyển form dịch vụ cụ thể.",
        "icp": "Lead inbound/outbound chưa rõ scope; multi-service; cần discovery trước khi gán lifecycle slug.",
        "call_script": scripts[:2000],
        "phone_qs": list(COMMON_PHONE_QUESTIONS),
        "inperson_qs": list(DEEP_DISCOVERY_COMMON),
        "red_flags": list(COMMON_RED_FLAGS),
        "objections": list(COMMON_OBJECTIONS),
        "urgency": list(COMMON_URGENCY),
        "sla": "Phản hồi lead ≤2h · Qualify 15–25p · Gán dịch vụ + lifecycle sau khi Go",
        "demo_checklist": list(COMMON_DEMO_CHECKLIST),
        "docs": list(COMMON_DOCS),
        "kpi_questions": list(COMMON_KPI_QUESTIONS),
        "scope_questions": list(COMMON_SCOPE_QUESTIONS),
        "closing_script": (
            '"Dựa trên buổi trao đổi, em đề xuất [dịch vụ phù hợp] và buổi tư vấn sâu 45–60p '
            'với [decision maker]. Anh/chị book [ngày] được không ạ?"'
        ),
        "upsell": [
            "Bundle SEO + Ads",
            "Audit trước retainer",
            "Landing page nhanh cho campaign",
        ],
    }


def render_field(label: str, field_type: str = "text", wide: bool = False) -> str:
    cls = "field field-wide" if wide else "field"
    if field_type == "textarea":
        inner = f'<div class="lines lines-tall"></div>'
    elif field_type == "checkbox":
        inner = '<span class="cb">☐</span>'
    else:
        inner = '<div class="line"></div>'
    return f'<div class="{cls}"><label>{label}</label>{inner}</div>'


def render_checkbox_group(items: list[str], cols: int = 2) -> str:
    cells = "".join(f'<label class="cb-item"><span class="cb">☐</span> {item}</label>' for item in items)
    return f'<div class="cb-group cols-{cols}">{cells}</div>'


def render_question_block(questions: list[str], prefix: str = "Q") -> str:
    rows = []
    for i, q in enumerate(questions, 1):
        rows.append(
            f'<tr><td class="q-num">{prefix}{i}</td><td class="q-text">{q}</td>'
            f'<td class="q-note"><div class="lines"></div></td></tr>'
        )
    return (
        '<table class="q-table"><thead><tr>'
        '<th style="width:3rem">#</th><th>Câu hỏi</th><th style="width:35%">Ghi chú / trả lời</th>'
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_table(headers: list[str], rows: list[list[str]], col_widths: list[str] | None = None) -> str:
    thead = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
    style = ""
    if col_widths:
        style = "<colgroup>" + "".join(f'<col style="width:{w}">' for w in col_widths) + "</colgroup>"
    return f'<table class="data-table">{style}<thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>'


def render_objections(items: list[tuple[str, str]]) -> str:
    rows = [
        f'<tr><td><strong>{obj}</strong></td><td><div class="lines"></div><p class="hint">{prompt}</p></td></tr>'
        for obj, prompt in items
    ]
    return (
        '<table class="data-table"><thead><tr><th style="width:28%">Phản đối</th>'
        '<th>Cách xử lý / ghi chú AM</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def _bant_html(abbreviated: bool = False) -> str:
    rows_html = []
    for name, prompt in BANT_ROWS:
        scores = "".join('<td class="score"></td>' for _ in range(5))
        rows_html.append(
            f"<tr><td><strong>{name}</strong><br><span class=\"hint\">{prompt}</span></td>{scores}"
            f'<td><div class="lines lines-sm"></div></td></tr>'
        )
    suffix = " (rút gọn)" if abbreviated else ""
    return f"""<h3>BANT+ Scoring{suffix}</h3>
<p class="hint">Đánh giá 1–5 mỗi tiêu chí. Tổng ≥24: Go | 18–23: Nurture | &lt;18: No-Go</p>
<table class="data-table bant-table">
<thead><tr><th>Tiêu chí</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>Ghi chú</th></tr></thead>
<tbody>{"".join(rows_html)}</tbody>
<tfoot><tr><td colspan="6"><strong>Tổng điểm</strong></td><td><div class="line"></div></td></tr></tfoot>
</table>"""


def _go_nogo_html() -> str:
    return f"""<h3>Nhiệt độ lead &amp; quyết định</h3>
<div class="cb-group cols-3">
  <label class="cb-item"><span class="cb">☐</span> <strong>Hot</strong> — budget + timeline + DM engaged</label>
  <label class="cb-item"><span class="cb">☐</span> <strong>Warm</strong> — nhu cầu rõ, thiếu budget/timeline</label>
  <label class="cb-item"><span class="cb">☐</span> <strong>Cold</strong> — chỉ hỏi giá, không pain point</label>
</div>
<div class="cb-group cols-3" style="margin-top:.75rem">
  <label class="cb-item cb-go"><span class="cb">☐</span> <strong>Go</strong> → Book Tư vấn</label>
  <label class="cb-item cb-nurture"><span class="cb">☐</span> <strong>Nurture</strong> → Drip + follow-up</label>
  <label class="cb-item cb-nogo"><span class="cb">☐</span> <strong>No-Go</strong> → Từ chối lịch sự</label>
</div>
{render_field("Lý do quyết định", "textarea", wide=True)}"""


def _section(title: str, body: str, part: str = "") -> str:
    part_badge = f'<span class="part-badge">{part}</span>' if part else ""
    return f'<section class="form-section"><div class="section-head"><h2>{title}</h2>{part_badge}</div>{body}</section>'


def build_html(title: str, slug: str, sections: list[str]) -> str:
    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — PTT Lead Intake</title>
<style>
:root {{ --navy:{NAVY}; --accent:{ACCENT}; --gray:#64748B; --light:#F1F5F9; --border:#CBD5E1; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:"Segoe UI",system-ui,-apple-system,sans-serif; color:var(--navy); background:#fff; line-height:1.5; font-size:13px; }}
.page {{ max-width:920px; margin:0 auto; padding:1.5rem 1.25rem 3rem; }}
header.doc-header {{ background:var(--navy); color:#fff; padding:1.25rem 1.5rem; border-radius:8px; margin-bottom:1.5rem; position:relative; }}
header.doc-header .header-top {{ display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }}
header.doc-header .header-brand img {{ height:52px; width:auto; display:block; }}
header.doc-header h1 {{ font-size:1.35rem; margin-bottom:.25rem; }}
header.doc-header .meta {{ font-size:.85rem; opacity:.85; }}
header.doc-header .slug {{ color:#93C5FD; font-size:.8rem; }}
.meta-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:.75rem 1.25rem; margin-top:1rem; background:rgba(255,255,255,.08); padding:1rem; border-radius:6px; }}
.form-section {{ margin-bottom:1.75rem; page-break-inside:avoid; }}
.section-head {{ display:flex; align-items:center; gap:.75rem; border-bottom:3px solid var(--accent); padding-bottom:.4rem; margin-bottom:1rem; }}
.section-head h2 {{ font-size:1.05rem; color:var(--navy); }}
.part-badge {{ background:var(--accent); color:#fff; font-size:.7rem; font-weight:600; padding:.2rem .55rem; border-radius:4px; white-space:nowrap; }}
h3 {{ font-size:.95rem; color:var(--accent); margin:1rem 0 .5rem; }}
p, li {{ margin-bottom:.35rem; }}
.hint {{ color:var(--gray); font-size:.8rem; font-style:italic; }}
.script-box {{ background:var(--light); border-left:4px solid var(--accent); padding:.75rem 1rem; margin:.5rem 0; border-radius:0 6px 6px 0; }}
.field {{ margin-bottom:.65rem; }}
.field-wide {{ grid-column:1/-1; }}
.field label {{ display:block; font-weight:600; font-size:.8rem; margin-bottom:.2rem; color:var(--gray); }}
.line {{ border-bottom:1px solid var(--border); height:1.4rem; }}
.lines {{ border-bottom:1px solid var(--border); height:1.2rem; margin-bottom:.35rem; }}
.lines-sm .lines, .lines-sm {{ height:1rem; }}
.lines-tall {{ min-height:3.5rem; border:1px solid var(--border); border-radius:4px; background:#FAFAFA; }}
.cb {{ display:inline-block; width:1rem; text-align:center; }}
.cb-group {{ display:grid; gap:.4rem .75rem; }}
.cb-group.cols-2 {{ grid-template-columns:1fr 1fr; }}
.cb-group.cols-3 {{ grid-template-columns:1fr 1fr 1fr; }}
.cb-item {{ display:flex; align-items:flex-start; gap:.35rem; font-size:.85rem; }}
.cb-go {{ color:#15803D; }} .cb-nurture {{ color:#B45309; }} .cb-nogo {{ color:#B91C1C; }}
.data-table, .q-table {{ width:100%; border-collapse:collapse; margin:.75rem 0; font-size:.82rem; }}
.data-table th, .q-table th {{ background:var(--accent); color:#fff; padding:.45rem .6rem; text-align:left; font-weight:600; }}
.data-table td, .q-table td {{ border:1px solid var(--border); padding:.45rem .6rem; vertical-align:top; }}
.data-table tr:nth-child(even) td {{ background:var(--light); }}
.q-num {{ text-align:center; font-weight:700; color:var(--accent); }}
.q-note .lines {{ min-height:2.4rem; }}
.score {{ width:2rem; text-align:center; background:#fff !important; }}
.bant-table td, .bant-table th {{ font-size:.78rem; }}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; }}
.footer-note {{ margin-top:2rem; padding:1rem; background:var(--light); border-radius:6px; font-size:.8rem; color:var(--gray); }}
@media print {{
  body {{ font-size:11px; }}
  .page {{ padding:0; max-width:100%; }}
  header.doc-header {{ border-radius:0; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  .form-section {{ page-break-inside:avoid; }}
  .part-badge, .data-table th, .q-table th {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
}}
</style>
</head>
<body>
<div class="page">
<header class="doc-header">
  <div class="header-top">
    <div>
      <div class="slug">PTT · Lead Intake · {slug}</div>
      <h1>{title}</h1>
      <div class="meta">Form tiếp nhận lead — Gọi điện (15–25 phút) + Gặp trực tiếp (45–60 phút)</div>
    </div>
    <div class="header-brand"><img src="/static/images/ptt-logo.png" alt="PTT Advertising Solutions"></div>
  </div>
  <div class="meta-grid">
    {render_field("Account Manager (AM)")}
    {render_field("Ngày gọi / gặp", "text")}
    {render_field("Lead ID / CRM")}
    {render_field("Nguồn lead (form/referral/ads/...)")}
    {render_field("Dịch vụ quan tâm", "text")}
    {render_field("Tên KH / Công ty")}
    {render_field("SĐT / Email", "text")}
    {render_field("Chức danh người liên hệ", "text")}
  </div>
</header>
{body}
<div class="footer-note">
  PTT Agency · Service Delivery · Sau buổi gọi/gặp: cập nhật CRM task <strong>Lead</strong> + Lead care <strong>first_contact</strong>.
  In form: Ctrl/Cmd+P · Tạo lại: <code>python3 scripts/generate_lead_intake_forms.py</code>
</div>
</div>
</body>
</html>"""


def get_lead_form_fields(slug: str) -> list[dict]:
    steps = SERVICE_WORKFLOW_STEPS.get(slug, {}).get("lead", [])
    if steps:
        return steps[0].get("form_fields", [])
    return []


def render_crm_footer(slug: str) -> str:
    fields = get_lead_form_fields(slug)
    if not fields:
        return ""
    rows = "".join(
        f'<tr><td><code>{f["key"]}</code></td><td>{f["label"]}</td>'
        f'<td><div class="line"></div></td></tr>'
        for f in fields
    )
    return _section(
        "Đồng bộ CRM — Task Lead (form_fields)",
        f"""<p class="hint">Điền các trường sau vào CRM Service Delivery → stage Lead.</p>
<table class="data-table"><thead><tr><th>Key</th><th>Label</th><th>Giá trị</th></tr></thead>
<tbody>{rows}</tbody></table>""",
    )


def build_common_sections() -> list[str]:
    scripts = "".join(
        f'<div class="script-box"><strong>{title}</strong><p>{text}</p></div>' for title, text in CALL_SCRIPTS
    )
    stakeholder = render_table(
        ["Vai trò", "Họ tên", "Chức danh", "Ảnh hưởng (1-5)", "Ghi chú"],
        [[role, "", "", "", ""] for role, _ in STAKEHOLDER_ROWS],
        ["18%", "22%", "22%", "12%", "26%"],
    )
    objections = render_objections(COMMON_OBJECTIONS)
    crm_checklist = render_checkbox_group([
        "Tạo/cập nhật Lead trên CRM",
        "Gán tag dịch vụ đúng slug",
        "Ghi BANT+ score + nhiệt độ lead",
        "Log cuộc gọi + next action",
        "Đặt lịch Tư vấn (nếu Go)",
        "Gửi email recap 24h",
        "Chuyển Lead care → first_contact",
        "Thông báo SP/team nếu Hot",
    ], cols=2)
    meeting_prep = render_checkbox_group([
        "Xem lại ghi chú cuộc gọi",
        "Research website/social KH",
        "Chuẩn bị 3 case study ngành",
        "In form + checklist tài liệu",
        "Book phòng / link Google Meet",
        "Mời decision maker (nếu thiếu)",
        "Chuẩn bị demo/audit slot 15p",
        "Xác nhận SMS/email trước 24h",
    ], cols=2)
    doc_rows = [
        ["Website URL / domain", "☐", "☐"],
        ["Screenshot analytics (GSC/GA4/Ads)", "☐", "☐"],
        ["Brand guideline / logo", "☐", "☐"],
        ["Brief nhu cầu / pain point", "☐", "☐"],
        ["Ngân sách & timeline xác nhận", "☐", "☐"],
    ]
    commitments = render_table(
        ["Cam kết", "Chi tiết KH cam kết", "Deadline"],
        [
            ["Cam kết 1 — Thông tin", "", ""],
            ["Cam kết 2 — Thời gian", "", ""],
            ["Cam kết 3 — Ngân sách / quyết định", "", ""],
        ],
        ["22%", "53%", "25%"],
    )
    return [
        _section("Script mở đầu cuộc gọi", scripts, "PHẦN A"),
        _section("BANT+ Qualification", _bant_html(), "PHẦN A"),
        _section("Stakeholder Map", stakeholder, "PHẦN A"),
        _section("Xử lý phản đối thường gặp", objections, "PHẦN A"),
        _section("Nhiệt độ & Quyết định", _go_nogo_html(), "PHẦN A"),
        _section('Chốt cam kết — "3 cam kết từ KH"', commitments, "PHẦN A"),
        _section("CRM Sync Checklist", crm_checklist, "PHẦN A"),
        _section(
            "Chuẩn bị buổi gặp trực tiếp",
            meeting_prep + render_field("Ghi chú chuẩn bị thêm", "textarea", wide=True),
            "PHẦN B",
        ),
        _section(
            "Recap cuộc gọi & xác nhận mục tiêu",
            render_field("Tóm tắt pain point đã xác nhận", "textarea", wide=True)
            + render_field("Mục tiêu buổi gặp hôm nay", "textarea", wide=True),
            "PHẦN B",
        ),
        _section("Deep Discovery (10 câu)", render_question_block(DEEP_DISCOVERY_COMMON), "PHẦN B"),
        _section(
            "Trust Building",
            """<p>Chia sẻ 1 case study ngành tương tự · Demo quy trình PTT · Giới thiệu team SP phụ trách</p>"""
            + render_checkbox_group(["Case study đã trình bày", "Quy trình 7 giai đoạn đã giải thích",
                                     "SP intro (nếu có)", "Reference KH (nếu được phép)"], cols=2)
            + render_field("Phản ứng KH / câu hỏi thêm", "textarea", wide=True),
            "PHẦN B",
        ),
        _section(
            "Demo / Audit slot (15 phút live)",
            render_checkbox_group([
                "Crawl website sơ bộ", "Check PageSpeed/CWV", "Xem GBP/Ads account",
                "Phân tích 1 competitor", "Show dashboard mẫu",
            ], cols=2) + render_field("Insight chính từ demo", "textarea", wide=True),
            "PHẦN B",
        ),
        _section(
            "Thu thập tài liệu",
            render_table(["Tài liệu", "Lead (có/sẽ gửi)", "Onboard (sau ký)"], doc_rows, ["40%", "30%", "30%"]),
            "PHẦN B",
        ),
        _section(
            "Budget Close & Next Steps",
            render_field("Ngân sách xác nhận (VND)", "text")
            + render_field("Timeline bắt đầu mong muốn", "text")
            + render_field("Ngày họp Proposal / gửi báo giá", "text")
            + render_field("Người tham dự buổi Proposal", "text"),
            "PHẦN B",
        ),
    ]


# fmt: off
SERVICE_FORMS: dict[str, dict] = {
    "dich-vu-seo-tong-the": {
        "title": "SEO Tổng thể",
        "group": "Tìm kiếm tự nhiên",
        "overview": "Chiến lược SEO toàn diện — kỹ thuật, nội dung, liên kết. Retainer ≥3 tháng.",
        "icp": "DN có website live ≥3 tháng; muốn tăng organic, giảm phụ thuộc Ads; SME hoặc enterprise có người duyệt content.",
        "call_script": '"Em thấy anh/chị quan tâm SEO tổng thể — tăng traffic tự nhiên bền vững. '
        'Cho em hỏi website hiện tại và mục tiêu traffic/ranking 6 tháng tới ạ?"',
        "phone_qs": [
            "Website domain? Live bao lâu rồi?", "Organic traffic/tháng hiện tại (ước lượng)?",
            "Top 5 từ khóa mục tiêu?", "Đã làm SEO/agency nào trước? Kết quả?",
            "Có GSC/GA4 access không?", "Ngân sách retainer/tháng (range)?",
            "Timeline kỳ vọng (3/6/12 tháng)?", "Ai duyệt thay đổi trên website?",
            "Có penalty/traffic tụt gần đây?", "Đối thủ organic chính?",
            "CMS/platform (WP/custom)?", "Cam kết duyệt content bao lâu?",
            "Mục tiêu KPI: traffic % hay ranking?", "Có team content nội bộ?",
            "Lý do chuyển/tìm agency mới?",
        ],
        "red_flags": ["Không có website", "Budget <3 tháng retainer", "Kỳ vọng top 1 trong 1 tháng",
                      "Từ chối duyệt content", "Không cung cấp GSC sau ký", "Chỉ muốn mua backlink"],
        "objections": [
            ("SEO mất quá lâu", "Chia sẻ milestone 3T/6T; quick win tháng 1 (technical fix)."),
            ("Đã thuê agency, không hiệu quả", "Hỏi deliverable cũ; đề xuất audit độc lập trước."),
            ("Tự làm SEO được", "Hỏi bottleneck; PTT làm phần technical/link, team nội bộ content."),
            ("Giá cao hơn freelancer", "So sánh SLA, báo cáo, rủi ro penalty, cam kết KPI."),
            ("Không tin cam kết ranking", "Giải thích KPI traffic + từ khóa top 10, không guarantee #1."),
            ("Chỉ cần viết bài", "Giải thích SEO tổng thể cần technical + on-page + off-page."),
        ],
        "urgency": ["Traffic tụt đột ngột", "Mùa cao điểm sắp tới", "Đối thủ vượt ranking",
                    "Board yêu cầu giảm CPA", "Hết hạn agency cũ"],
        "sla": "Phản hồi lead ≤2h · Tư vấn trong 1–3 ngày · Proposal ≤2 ngày sau tư vấn",
        "inperson_qs": [
            "Baseline traffic 12 tháng — trend?", "Cluster từ khóa theo funnel (awareness/consideration/conversion)?",
            "Cấu trúc site: bao nhiêu URL index?", "Core Web Vitals hiện tại?", "Lịch sử migration/redirect?",
            "Content gap vs đối thủ?", "Internal link structure?", "Backlink profile — toxic links?",
            "Local vs national scope?", "E-commerce vs lead gen?", "Seasonality traffic?",
            "Brand vs non-brand traffic mix?", "Conversion rate từ organic?", "Tool đang dùng (Ahrefs/SEMrush)?",
            "Quy trình publish content?", "Legal/compliance hạn chế ngành?", "Multi-language cần không?",
            "Integration với CRM tracking lead?", "KPI success 6 tháng cụ thể?", "Budget phân bổ content vs link?",
        ],
        "demo_checklist": ["Crawl 50 URL sample", "PageSpeed mobile/desktop", "GSC Performance export",
                           "Top 10 ranking keywords", "3 đối thủ SERP", "Schema/FAQ check"],
        "docs": [("URL website", "☐", "☐"), ("Screenshot GSC Performance", "☐", "☐"),
                 ("GA4 overview 12 tháng", "☐", "☐"), ("Danh sách từ khóa mục tiêu", "☐", "☐"),
                 ("Brand guideline", "☐", "☐"), ("GSC User access", "—", "☐"), ("GA4 Editor access", "—", "☐")],
        "kpi_questions": ["Traffic +20% (3T) realistic?", "Top 10 keywords — bao nhiêu từ khóa?",
                          "CWV pass — ưu tiên URL nào?", "Lead/conversion từ organic?"],
        "scope_questions": ["IN: technical, on-page, content, link?", "OUT: paid ads, social, design?",
                            "Số bài content/tháng?", "Link building budget riêng?"],
        "closing_script": '"Dựa trên audit sơ bộ, PTT đề xuất buổi Proposal 60p — trình bày roadmap 6 tháng '
        'và KPI cam kết. Anh/chị book [ngày] với [decision maker] được không ạ?"',
        "upsell": ["AEO / AI search", "Content marketing retainer", "Quảng cáo Google (bổ sung SEO)",
                   "SEO Audit nếu chưa chắc baseline"],
    },
    "dich-vu-aeo": {
        "title": "AEO (Answer Engine Optimization)",
        "group": "Tìm kiếm tự nhiên",
        "overview": "Tối ưu xuất hiện trong ChatGPT, Gemini, Perplexity, Google SGE/AIO.",
        "icp": "Đã có SEO/content; ngành cạnh tranh (BĐS, TC, YTE, giáo dục); website nội dung ≥20 URL chất lượng.",
        "call_script": '"Anh/chị quan tâm AEO — xuất hiện khi khách hỏi AI về ngành. '
        'Anh/chị đã thử hỏi ChatGPT/Gemini về thương hiệu chưa ạ?"',
        "phone_qs": [
            "Domain và số URL nội dung chính?", "Đã thử query AI về brand — kết quả?",
            "FAQ/schema hiện có trên site?", "E-E-A-T: author, credentials?",
            "Ngành regulated (YTE/TC)? Expert review?", "URL ưu tiên cho AEO?",
            "Song song SEO tổng thể không?", "Ngân sách/tháng?", "Timeline mong muốn?",
            "Ai duyệt nội dung FAQ?", "CMS deploy schema được không?", "Đối thủ được AI cite?",
            "Mục tiêu: brand mention hay citation URL?", "Content tiếng Việt/Anh?", "Pain: không xuất hiện AI?",
        ],
        "red_flags": ["Site mỏng nội dung", "Không expert review ngành regulated",
                      "Kỳ vọng AI luôn recommend brand", "Không CMS access", "Không duyệt FAQ"],
        "objections": [
            ("AEO còn mới, chưa chắc hiệu quả", "Show case citation SGE; metric URL được trích dẫn."),
            ("Đã có SEO rồi", "AEO bổ sung layer AI search — khác schema/FAQ intent."),
            ("AI không kiểm soát được", "Tối ưu E-E-A-T, structured data — tăng xác suất cite."),
            ("Chi phí thêm", "Bundle với SEO tổng thể; pilot 3 tháng."),
            ("Không có content writer", "PTT viết FAQ + schema; KH duyệt expert."),
            ("Sợ thông tin sai trên AI", "Kiểm soát source content on-site; fact-check workflow."),
        ],
        "urgency": ["Đối thủ xuất hiện AI, mình không", "Launch sản phẩm mới",
                    "Google SGE rollout ngành", "PR cần AI visibility"],
        "sla": "Phản hồi ≤2h · Audit AI presence 1–3 ngày · Proposal ≤2 ngày",
        "inperson_qs": [
            "Query set 20 câu KH hay nhận?", "Brand mention rate trên 4 AI tools?",
            "Content pillar nào authoritative?", "Author schema đủ chưa?", "FAQ coverage theo topic?",
            "HowTo/Video schema cần không?", "Citation sources AI đang dùng?", "Competitor AI visibility?",
            "YMYL compliance requirements?", "Review cycle nội dung?", "Multimedia (video/podcast)?",
            "Internal linking tới pillar pages?", "Freshness — update frequency?", "Structured data errors?",
            "Brand SERP vs AI answer gap?", "Local AEO cần không?", "Integration chatbot site?",
            "KPI: citation count hay traffic?", "Budget content vs technical AEO?", "Pilot scope bao nhiêu URL?",
        ],
        "demo_checklist": ["Query ChatGPT/Gemini live 5 câu", "Rich Results Test 3 URL",
                           "Schema markup scan", "FAQ page review", "SGE preview (nếu có)", "Competitor AI check"],
        "docs": [("URL + 5 trang ưu tiên", "☐", "☐"), ("Export câu hỏi CS/sales", "☐", "☐"),
                 ("Screenshot Rich Results", "☐", "☐"), ("GSC access", "☐", "☐"),
                 ("Brand guideline", "☐", "☐"), ("CMS admin (schema)", "—", "☐")],
        "kpi_questions": ["URL được AI cite tăng bao nhiêu?", "≥80% trang ưu tiên có FAQ?",
                          "0 lỗi schema critical?", "Brand mention rate target?"],
        "scope_questions": ["IN: FAQ, schema, content optimize?", "OUT: full SEO link building?",
                            "Số URL pilot?", "Expert review ai chịu trách nhiệm?"],
        "closing_script": '"Em đề xuất buổi Proposal AEO — roadmap URL ưu tiên + KPI xuất hiện AI. '
        'Book [ngày] với team marketing được không ạ?"',
        "upsell": ["SEO tổng thể", "Content marketing", "SEO Audit baseline"],
    },
    "dich-vu-seo-local": {
        "title": "SEO Local",
        "group": "Tìm kiếm tự nhiên",
        "overview": "Google Maps, GBP, tìm kiếm địa phương — Local Pack top 3.",
        "icp": "Cửa hàng/chi nhánh; nhà hàng, spa, PK, BĐS, bán lẻ; cần hiển thị tìm kiếm gần tôi.",
        "call_script": '"Anh/chị cần khách tìm trên Maps/Google gần đó — em hỏi nhanh số chi nhánh '
        'và tình trạng Google Business Profile ạ?"',
        "phone_qs": [
            "Số chi nhánh & địa chỉ (NAP)?", "GBP đã verify? Ai là owner?",
            "Rating/review hiện tại?", "GBP suspended/duplicate?", "Website NAP khớp GBP?",
            "Từ khóa địa phương mục tiêu?", "KPI: gọi, chỉ đường, form?", "Ngân sách theo chi nhánh?",
            "Đối thủ Local Pack top 3?", "Quy trình xin review khách?", "Ảnh storefront có không?",
            "Multi-city hay 1 khu vực?", "Dịch vụ delivery/online?", "Ai post GBP updates?",
            "Pain: không lên Maps?",
        ],
        "red_flags": ["GBP suspended", "NAP lệch nhiều nơi", "N chi nhánh budget 1 điểm",
                      "Không có GPKD verify", "Review bombing đang xảy ra"],
        "objections": [
            ("Đã có GBP rồi", "Audit optimization score — thường còn 40% chưa tối ưu."),
            ("Review tự nhiên đủ rồi", "Local Pack cần NAP + citation + content, không chỉ review."),
            ("1 chi nhánh, tự làm được", "Show competitor Local Pack; time cost vs agency."),
            ("Giá theo chi nhánh cao", "Bundle multi-location discount; ưu tiên chi nhánh doanh thu cao."),
            ("Không muốn nhờ review", "Chia sẻ quy trình xin review hợp lệ, không fake."),
            ("Website chưa có", "GBP + landing page tối thiểu; upsell web."),
        ],
        "urgency": ["Mở chi nhánh mới", "Mùa cao điểm local", "Đối thủ vượt Local Pack",
                    "GBP bị report/suspended risk"],
        "sla": "Phản hồi ≤2h · GBP audit sơ bộ 1–3 ngày · Proposal 3–7 ngày",
        "inperson_qs": [
            "NAP từng chi nhánh — spreadsheet?", "GBP category chính/phụ đúng chưa?", "Service area vs storefront?",
            "Citation directories hiện có?", "Duplicate listing scan?", "Review velocity/tháng?",
            "Response rate Q&A GBP?", "GBP posts frequency?", "Local landing pages?", "Schema LocalBusiness?",
            "Geo-grid ranking test?", "Competitor citation gap?", "Ảnh: interior/exterior/product?",
            "Hours/special hours holidays?", "Tracking call/chỉ đường setup?", "Multi-language GBP?",
            "Franchise vs corporate structure?", "Budget per location?", "Priority locations wave 1?",
            "Integration CRM cho lead Maps?",
        ],
        "demo_checklist": ["GBP audit live", "Local Pack SERP 3 từ khóa", "NAP consistency check",
                           "Review sentiment scan", "Competitor GBP compare", "Map geo-grid (nếu có tool)"],
        "docs": [("Link GBP từng chi nhánh", "☐", "☐"), ("Excel NAP chi nhánh", "☐", "☐"),
                 ("Ảnh storefront", "☐", "☐"), ("Bản đồ khu vực target", "☐", "☐"),
                 ("GBP Owner access", "—", "☐"), ("GPKD verify", "☐", "☐")],
        "kpi_questions": ["Local Pack top 3 — bao nhiêu từ khóa?", "Review growth/tháng?",
                          "Call/chỉ đường tăng?", "NAP consistency score?"],
        "scope_questions": ["IN: GBP, citation, local content?", "OUT: SEO tổng thể national?",
                            "Số chi nhánh wave 1?", "Review management scope?"],
        "closing_script": '"Em gửi Proposal Local SEO — KPI Local Pack + timeline setup 2 tuần/chi nhánh. '
        'Họp [ngày] duyệt scope chi nhánh ưu tiên ạ?"',
        "upsell": ["SEO tổng thể", "Quảng cáo Google Local", "Quản trị website"],
    },
    "dich-vu-seo-audit": {
        "title": "SEO Audit",
        "group": "Tìm kiếm tự nhiên",
        "overview": "Audit technical, on-page, content, backlink — báo cáo ưu tiên hành động.",
        "icp": "Traffic tụt, penalty nghi ngờ, redesign, M&A site, cần review trước SEO dài hạn.",
        "call_script": '"Anh/chị cần audit SEO — em hỏi trigger (tụt traffic/penalty/redesign) '
        'và deadline cần báo cáo ạ?"',
        "phone_qs": [
            "Domain cần audit?", "Trigger: tụt traffic/penalty/redesign/mua site?",
            "Quy mô site (URL/index)?", "Phạm vi: tech/on-page/content/link?", "Deadline báo cáo?",
            "Ngân sách audit (range)?", "Có GSC access không?", "Lịch sử migration?",
            "Dev in-house fix sau audit?", "Đã audit lần nào chưa?", "Penalty manual action?",
            "E-commerce hay lead gen?", "Multi-domain/subdomain?", "Ngôn ngữ site?",
            "Mục tiêu sau audit: tự fix hay thuê triển khai?",
        ],
        "red_flags": ["Từ chối GSC", "Site >10k URL budget nhỏ", "Urgency cao không stakeholder",
                      "Scope creep mong đợi", "Chỉ muốn giá rẻ nhất"],
        "objections": [
            ("Audit tự làm bằng tool free", "PTT có phân tích impact×effort + khuyến nghị ưu tiên."),
            ("Giá audit cao", "So sánh scope trang, deliverable, presentation 60p."),
            ("Cần audit gấp 3 ngày", "Fast-track phụ phí; scope giới hạn URL."),
            ("Sau audit tự fix", "OK — offer implement package riêng."),
            ("Agency cũ audit rồi", "Second opinion độc lập; focus gap chưa cover."),
            ("Không share GSC", "Giải thích audit không GSC = 50% giá trị mất."),
        ],
        "urgency": ["Traffic drop >30%", "Google manual action email", "Pre-launch redesign",
                    "Due diligence M&A", "Board deadline"],
        "sla": "Phản hồi ≤2h · Scoping call 1–3 ngày · Báo cáo 2–3 tuần sau kickoff",
        "inperson_qs": [
            "Baseline traffic 12 tháng pre-drop?", "Ngày bắt đầu traffic tụt?", "Google update correlation?",
            "Migration redirect map?", "Robots.txt/sitemap issues?", "Canonical/hreflang?",
            "Thin/duplicate content %?", "Core Web Vitals distribution?", "Mobile usability errors?",
            "Backlink toxic ratio?", "Anchor text over-optimization?", "Internal link orphan pages?",
            "Structured data coverage?", "Log file access có không?", "Competitor benchmark?",
            "Priority URL list?", "Stakeholder nhận báo cáo?", "Format deliverable (PDF/Sheet)?",
            "Presentation 60p ai tham dự?", "Post-audit implement budget?", "Warranty/support Q&A?",
        ],
        "demo_checklist": ["Screaming Frog crawl sample", "GSC Coverage/CWV", "5 quick wins live",
                           "Backlink snapshot", "SERP visibility trend", "Penalty check"],
        "docs": [("URL website", "☐", "☐"), ("Screenshot GSC", "☐", "☐"), ("Báo cáo SEO cũ", "☐", "☐"),
                 ("Mô tả vấn đề chi tiết", "☐", "☐"), ("GSC + GA4 access", "—", "☐"), ("URL ưu tiên list", "☐", "☐")],
        "kpi_questions": ["Deliverable 2–3 tuần OK?", "Bảng ưu tiên impact×effort?",
                          "Presentation 60p included?", "Support Q&A post-audit bao lâu?"],
        "scope_questions": ["IN: tech, on-page, content, link?", "OUT: implement fix?",
                            "Giới hạn số trang crawl?", "Log file analysis included?"],
        "closing_script": '"Em gửi Proposal audit — phạm vi, timeline, deliverable cụ thể. '
        'Ký HĐ → kickoff 24h cần GSC. Họp [ngày] ạ?"',
        "upsell": ["SEO tổng thể triển khai", "Quản trị website fix", "Technical retainer"],
    },
    "dich-vu-quan-tri-website": {
        "title": "Quản trị Website",
        "group": "Tìm kiếm tự nhiên",
        "overview": "Bảo trì WordPress/custom — update, bảo mật, content, fix lỗi, backup.",
        "icp": "Site đang vận hành; cần duy trì; vừa bàn giao thiết kế; site đang lỗi (urgency cao).",
        "call_script": '"Website anh/chị đang cần hỗ trợ gì — bảo trì định kỳ hay đang gặp lỗi gấp? '
        'Em hỏi platform và tình trạng hiện tại ạ?"',
        "phone_qs": [
            "URL và platform (WP/custom)?", "Lỗi hiện tại — urgency?", "WP version & plugins chính?",
            "Hosting provider — ai sở hữu?", "Tần suất cập nhật content?", "Ai tự sửa wp-admin?",
            "Backup & staging có không?", "SLA uptime mong muốn?", "Ngân sách retainer/tháng?",
            "Số ticket/tháng ước tính?", "Bảo mật — hack trước đây?", "E-commerce/plugin phức tạp?",
            "Dev cũ còn hỗ trợ không?", "Compliance (PCI/GDPR)?", "Multi-site/network?",
        ],
        "red_flags": ["KH tự admin hay phá", "Không backup", "Hosting yếu/shared lỏng",
                      "Fix ngay chưa ký SLA", "Budget không đủ retainer tối thiểu"],
        "objections": [
            ("Tự update WP được", "Rủi ro break site; PTT staging + backup trước mọi update."),
            ("Freelancer rẻ hơn", "SLA uptime, response time, incident log."),
            ("Chỉ cần fix 1 lần", "Offer ticket-based; retainer rẻ hơn nếu >3 ticket/tháng."),
            ("Sợ mất quyền kiểm soát", "Access read-only cho KH; mọi change log ticket."),
            ("Dev cũ làm được", "Handover doc; PTT nhận bảo hành 30 ngày post-dev."),
            ("Không cần staging", "Giải thích risk production direct edit."),
        ],
        "urgency": ["Site down/error 500", "Hack/malware", "Plugin break sau update",
                    "Black Friday/campaign sắp tới", "Hết hạn dev cũ"],
        "sla": "Phản hồi ≤2h · Site down ≤30p first response · Onboard 48–72h",
        "inperson_qs": [
            "Plugin inventory — critical list?", "Theme custom hay off-shelf?", "Database size/performance?",
            "CDN/caching setup?", "SSL expiry monitoring?", "Uptime history 3 tháng?",
            "Security scan last date?", "User roles — ai admin?", "Content workflow approval?",
            "Form/CRM integrations?", "Payment gateway (Woo)?", "Multilingual plugin?",
            "Media library size?", "Cron jobs custom?", "Error log patterns?",
            "Hosting specs — RAM/CPU?", "Disaster recovery plan?", "Change request process?",
            "Monthly report format?", "Escalation contact?", "Warranty vs retainer scope?",
        ],
        "demo_checklist": ["PageSpeed check", "WP version/plugin outdated scan", "Uptime ping",
                           "Security headers check", "Backup verify", "Mobile responsive quick test"],
        "docs": [("URL + mô tả lỗi", "☐", "☐"), ("Screenshot lỗi", "☐", "☐"), ("Hosting info", "☐", "☐"),
                 ("Plugin list export", "☐", "☐"), ("wp-admin / FTP", "—", "☐"), ("Handover doc dev cũ", "☐", "☐")],
        "kpi_questions": ["Uptime SLA %?", "Response time ticket?", "Số task hoàn thành/tháng?",
                          "Incident resolution time?"],
        "scope_questions": ["IN: update, backup, content, fix?", "OUT: redesign, SEO, new feature?",
                            "Số giờ support/tháng?", "Emergency fee ngoài giờ?"],
        "closing_script": '"Em gửi Proposal quản trị — scope/tháng, SLA, checklist bàn giao. '
        'Access sau ký HĐ — kickoff 48h. Họp [ngày] ạ?"',
        "upsell": ["SEO tổng thể", "Thiết kế redesign", "Landing page campaign"],
    },
    "thiet-ke-website": {
        "title": "Thiết kế Website",
        "group": "Thiết kế",
        "overview": "UI/UX design — Figma/PSD, wireframe → UI, handoff developer. 5–7 tuần.",
        "icp": "Làm mới/redesign; cần design chuyên nghiệp; dev có thể bên thứ 3 hoặc nội bộ.",
        "call_script": '"Anh/chị cần thiết kế website — redesign hay site mới? Em hỏi số trang, '
        'deadline và ngân sách design ạ?"',
        "phone_qs": [
            "Redesign hay website mới?", "Loại web (corporate/ecomm/portfolio)?", "Số trang/template ước tính?",
            "Deadline mong muốn?", "Ngân sách design (range)?", "Có brand guideline/logo vector?",
            "Website tham khảo (refs)?", "Mục tiêu CVR/conversion?", "Dev partner có sẵn?",
            "Số vòng revision mong muốn?", "Responsive — mobile first?", "Ngôn ngữ (VI/EN)?",
            "Ai duyệt design cuối?", "Content sẵn hay cần placeholder?", "Tích hợp design system?",
        ],
        "red_flags": ["Không logo vector", "Deadline <4 tuần cho >10 trang", "Nhiều stakeholder không ai duyệt",
                      "Budget không khớp scope", "Feature creep trong design phase"],
        "objections": [
            ("Template ThemeForest rẻ hơn", "Custom design = brand differentiation + CVR."),
            ("Freelancer design 5 triệu", "So sánh revision policy, handoff dev, responsive QA."),
            ("Chưa có content", "Wireframe trước; content song song milestone 2."),
            ("Dev nội bộ không đọc Figma", "PTT handoff: spec + assets + dev support call."),
            ("Cần gấp 2 tuần", "Scope landing 5 trang max; phụ phí rush."),
            ("Nhiều người duyệt", "Quy trình 1 POC duyệt; max 2 vòng free."),
        ],
        "urgency": ["Rebrand launch date", "Hết hạn domain/hosting cũ", "Investor demo",
                    "Campaign cần site mới", "Competitor site mới ra mắt"],
        "sla": "Phản hồi ≤2h · Tư vấn 1–3 ngày · Proposal 3–7 ngày · Design 5–7 tuần",
        "inperson_qs": [
            "Brand personality keywords?", "Target user persona chi tiết?", "User journey chính?",
            "Sitemap draft — bao nhiêu trang?", "Must-have sections trang chủ?", "E-commerce hay lead gen CTA?",
            "Accessibility requirements?", "Animation/micro-interaction level?", "Photo style — stock vs custom?",
            "Typography preferences?", "Competitor design benchmark?", "Existing analytics heatmap?",
            "Form fields cần thiết?", "Trust signals (testimonial/cert)?", "Footer legal pages?",
            "Dark mode cần không?", "Design system cho app sau?", "Handoff format (Figma/Dev Mode)?",
            "Revision approval workflow?", "Milestone payment OK?", "Post-design dev support scope?",
        ],
        "demo_checklist": ["Show Figma portfolio ngành", "Wireframe sample live", "Design system demo",
                           "Responsive breakpoint explain", "Handoff spec sample", "Revision process walkthrough"],
        "docs": [("Refs URL 3–5 site", "☐", "☐"), ("Logo (nếu có)", "☐", "☐"), ("Brand cơ bản", "☐", "☐"),
                 ("Sitemap sơ bộ", "☐", "☐"), ("Logo SVG/EPS", "—", "☐"), ("Font license + HEX colors", "—", "☐")],
        "kpi_questions": ["Deliverable đúng milestone?", "≤2 vòng revision miễn phí?",
                          "CSAT design ≥4.2?", "Handoff dev đầy đủ?"],
        "scope_questions": ["IN: wireframe, UI, responsive, handoff?", "OUT: dev, content, SEO?",
                            "Số trang included?", "Extra page fee?"],
        "closing_script": '"Em gửi Proposal design — phạm vi trang, timeline 5–7 tuần, milestone thanh toán. '
        'Họp kickoff design brief [ngày] ạ?"',
        "upsell": ["Website trọn gói (design+dev)", "Landing page campaign", "Quản trị website"],
    },
    "thiet-ke-website-tron-goi": {
        "title": "Website Trọn gói",
        "group": "Thiết kế",
        "overview": "Design + dev + go-live — WordPress/custom. 8–12 tuần.",
        "icp": "Một đơn vị làm hết; landing/brochure/e-commerce; tích hợp payment/CRM.",
        "call_script": '"Anh/chị cần website trọn gói — design, code, go-live. Em hỏi loại web, '
        'tính năng chính và timeline launch ạ?"',
        "phone_qs": [
            "Loại web (brochure/ecomm/portal)?", "Tính năng: cart, payment, đa ngôn ngữ?",
            "Tích hợp CRM/ERP/email?", "WordPress hay custom stack?", "Domain/hosting sẵn?",
            "Ai cung cấp content — deadline?", "SEO cơ bản trong scope?", "Quy mô SKU (e-comm)?",
            "Ngân sách tổng (range)?", "Timeline go-live?", "Payment gateway nào?",
            "User roles/admin phức tạp?", "Migration data từ site cũ?", "Compliance (PCI)?",
            "Bảo hành post-live?",
        ],
        "red_flags": ["Feature creep không scope doc", "Content KH trễ không deadline",
                      "Không ký scope trước dev", "Thiếu payment spec", "Budget <8 tuần effort"],
        "objections": [
            ("Tách design/dev rẻ hơn", "Trọn gói = 1 POC, timeline chắc, warranty 30 ngày."),
            ("Freelancer full-stack", "Team PTT: design + dev + QA riêng; SLA rõ."),
            ("WordPress template đủ", "Custom feature (CRM, payment) cần dev thật."),
            ("SEO đưa sau", "On-page cơ bản trong scope launch; full SEO upsell."),
            ("Thêm feature giữa chừng", "Change request process + phụ phí minh bạch."),
            ("Timeline 4 tuần e-comm", "Realistic 8–12 tuần; giảm scope MVP."),
        ],
        "urgency": ["Launch sản phẩm cố định", "Hết hạn hợp đồng thuê site", "Franchise expansion",
                    "Rebrand toàn công ty", "Campaign date hard"],
        "sla": "Phản hồi ≤2h · BRD meeting 1–3 ngày · Proposal 3–7 ngày · Go-live 8–12 tuần",
        "inperson_qs": [
            "User flow chi tiết từng persona?", "Sitemap final sign-off ai?", "Feature list IN/OUT?",
            "Payment flow — one-time/subscription?", "Shipping/tax rules (e-comm)?", "Product import format?",
            "CRM webhook spec?", "Email transactional (order/reset)?", "Admin dashboard cần gì?",
            "Multi-vendor marketplace?", "Search/filter complexity?", "Blog/news section?",
            "Cookie consent/GDPR?", "Analytics GTM events?", "Performance budget (PageSpeed)?",
            "Staging UAT process?", "Content matrix deadline?", "Training CMS — bao nhiêu người?",
            "Hosting recommendation?", "SSL, backup, monitoring?", "Warranty bug 30 ngày scope?",
        ],
        "demo_checklist": ["Show live site ngành tương tự", "Admin CMS demo", "Checkout flow sample",
                           "Mobile QA checklist", "PageSpeed launched site", "Scope doc template walkthrough"],
        "docs": [("Refs site + feature list", "☐", "☐"), ("Brand cơ bản", "☐", "☐"),
                 ("BRD/sitemap nháp", "☐", "☐"), ("Integration spec", "☐", "☐"),
                 ("Scope doc ký", "—", "☐"), ("Content matrix + domain access", "—", "☐")],
        "kpi_questions": ["Go-live đúng milestone?", "QA checklist pass?", "PageSpeed mobile score?",
                          "Warranty 30 ngày bug?"],
        "scope_questions": ["IN: design, dev, QA, go-live, SEO basic?", "OUT: content writing, full SEO, Ads?",
                            "Số trang/SKU included?", "Change request rate?"],
        "closing_script": '"Em gửi Proposal trọn gói — scope doc IN/OUT, milestone 8–12 tuần. '
        'Ký scope trước dev. Họp BRD [ngày] ạ?"',
        "upsell": ["Quản trị website", "SEO tổng thể", "Google/Facebook Ads launch"],
    },
    "thiet-ke-landing-page": {
        "title": "Landing Page",
        "group": "Thiết kế",
        "overview": "LP chuyển đổi cao cho campaign Ads/email. 1–2 tuần.",
        "icp": "Campaign Ads sắp chạy; deadline gấp; cần CVR-focused 1 trang.",
        "call_script": '"Anh/chị cần landing page cho campaign — em hỏi deadline launch Ads '
        'và CTA chính (form/gọi/mua) ạ?"',
        "phone_qs": [
            "Deadline campaign cụ thể?", "CTA: form/gọi/chat/mua?", "Offer/USP/pricing rõ chưa?",
            "Ads creative message match?", "Pixel/GTM/events setup?", "Domain/subdomain?",
            "Form fields & CRM nhận lead?", "Copy ai viết — sẵn chưa?", "Ảnh sản phẩm sẵn?",
            "A/B test plan?", "Mobile traffic %?", "Compliance ngành (YTE/TC)?",
            "Ngân sách LP (range)?", "Design only hay code luôn?", "Post-live ai sửa?",
        ],
        "red_flags": ["Copy chưa chốt", "Deadline <5 ngày thiếu asset", "Offer yếu kỳ vọng CVR cao",
                      "Không có Ads campaign date", "Không pixel tracking plan"],
        "objections": [
            ("Template Unbounce đủ", "Custom = message match Ads + PageSpeed + brand."),
            ("1 tuần không kịp", "MVP 5 section; copy+ảnh phải sẵn day 1."),
            ("CVR guarantee?", "Best practice + benchmark ngành; không guarantee %."),
            ("Tự clone page cũ", "Audit CVR page cũ trước; redesign section yếu."),
            ("Chỉ cần design", "Offer code+tracking package; design-only rẻ hơn."),
            ("Giá cao cho 1 trang", "So sánh conversion value 1 lead vs cost LP."),
        ],
        "urgency": ["Ads start date cố định", "Flash sale/event", "Product launch",
                    "Agency cũ delay", "Policy reject cần LP mới"],
        "sla": "Phản hồi ≤2h (deadline ≤5 ngày ≤1h) · Live 1–2 tuần",
        "inperson_qs": [
            "Above-fold USP 1 câu?", "Social proof — testimonial/logo?", "Objection handling section?",
            "FAQ cần không?", "Video embed?", "Countdown/urgency element?", "Form fields tối thiểu?",
            "Thank-you page + conversion event?", "Heatmap tool post-live?", "Privacy policy link?",
            "Sticky CTA mobile?", "Load time budget?", "CDN/hosting?", "SSL subdomain?",
            "CRM/Zapier integration spec?", "A/B variant scope?", "Accessibility form labels?",
            "Retargeting pixel events?", "Post-live CVR review date?", "Iteration budget?",
        ],
        "demo_checklist": ["LP portfolio ngành", "PageSpeed live demo", "Form submit test",
                           "GTM preview events", "Mobile thumb-zone CTA", "Message match Ads mock"],
        "docs": [("Ads creative + copy", "☐", "☐"), ("USP/offer doc", "☐", "☐"), ("Ảnh SP 1000×1000", "☐", "☐"),
                 ("Refs LP", "☐", "☐"), ("Copy final + Logo SVG", "—", "☐"), ("GTM/pixel ID", "—", "☐")],
        "kpi_questions": ["PageSpeed pass?", "Form+tracking OK?", "Live đúng deadline campaign?",
                          "CVR review 30 ngày?"],
        "scope_questions": ["IN: design, code, form, pixel?", "OUT: Ads management, copywriting?",
                            "Số section/revision?", "A/B variant included?"],
        "closing_script": '"Campaign [ngày] — em lock timeline LP 1–2 tuần. Ký HĐ hôm nay → brief ngày mai. '
        'OK ạ?"',
        "upsell": ["A/B test retainer", "Facebook/Google Ads", "Quản trị LP + CRO"],
    },
    "quang-cao-facebook": {
        "title": "Quảng cáo Facebook (Meta Ads)",
        "group": "Quảng cáo",
        "overview": "Quản lý Meta Ads — lead gen, sales, traffic. Retainer tháng.",
        "icp": "Chạy Ads mới hoặc tối ưu account; cần CPL/ROAS ổn định; có LP/fanpage.",
        "call_script": '"Anh/chị chạy Facebook Ads — mục tiêu lead, sale hay traffic? '
        'Em hỏi ngân sách/ngày và có BM/Ads account chưa ạ?"',
        "phone_qs": [
            "Mục tiêu: lead/sale/traffic/awareness?", "KPI CPL/ROAS baseline?", "Ngân sách/ngày (VND)?",
            "LP URL — live & tốc độ?", "Fanpage link & BM owner?", "Pixel/CAPI setup status?",
            "Creative ai làm — có sẵn?", "Lịch sử policy/vi phạm?", "Account cũ hay mới?",
            "Retargeting audience có chưa?", "Ngành sản phẩm — restricted?", "Geo target?",
            "Catalog/DPA cần không?", "Agency cũ kết quả?", "Timeline scale budget?",
        ],
        "red_flags": ["Không LP", "Pixel lỗi/không cài", "Ngành hạn chế không disclose",
                      "Ngân sách/ngày quá thấp learning", "BM không add partner được"],
        "objections": [
            ("Tự boost post đủ", "Ads Manager = targeting + pixel + optimize algorithm."),
            ("CPL agency cao hơn tự chạy", "So sánh quality lead + time + creative test volume."),
            ("Burn budget tháng trước", "Audit account — thường structure/audience issue."),
            ("Creative nội bộ không cần agency", "OK — PTT optimize + media plan; creative KH supply."),
            ("Không tin % phí quản lý", "Minh bạch fee + spend report hàng tuần."),
            ("CAPI phức tạp", "PTT setup CAPI standard; server-side improve match rate."),
        ],
        "urgency": ["Campaign launch date", "Account disabled recovery", "Seasonal sale",
                    "Competitor aggressive Ads", "New product launch"],
        "sla": "Phản hồi ≤2h · Strategy call 1–3 ngày · Setup campaign 3–5 ngày sau onboard",
        "inperson_qs": [
            "Funnel stage mapping?", "Audience persona 3 layer?", "Creative angle tested?",
            "Offer/lead magnet?", "LP message match score?", "Form friction audit?",
            "Pixel events priority list?", "CAPI vs browser dedup?", "BM structure clean?",
            "Ad account spending limit?", "Catalog feed quality?", "UTM convention?",
            "Weekly report format?", "Creative refresh cadence?", "Policy risk products?",
            "Competitor Ad Library insights?", "Budget scaling rules?", "Learning phase plan?",
            "Whatsapp/Messenger ads?", "Influencer whitelisting?", "Break-even CPL/ROAS math?",
        ],
        "demo_checklist": ["Ads Manager audit live", "LP PageSpeed", "Pixel Helper check",
                           "Audience overlap estimate", "Creative swipe file ngành", "CPL benchmark share"],
        "docs": [("Fanpage link", "☐", "☐"), ("Screenshot Ads Manager", "☐", "☐"), ("LP URL", "☐", "☐"),
                 ("Media kit/creative", "☐", "☐"), ("BM partner access", "—", "☐"), ("Pixel verify", "—", "☐")],
        "kpi_questions": ["CTR/CPL/ROAS target?", "Báo cáo tuần+tháng?", "Creative refresh 2 tuần?",
                          "Scale budget threshold?"],
        "scope_questions": ["IN: setup, optimize, report?", "OUT: creative production, LP build?",
                            "Min spend/ngày?", "% fee vs flat retainer?"],
        "closing_script": '"Em gửi Proposal Meta Ads — KPI, cấu trúc campaign, phí quản lý. '
        'BM partner sau ký — setup 3–5 ngày. Họp [ngày] ạ?"',
        "upsell": ["Google Ads", "Landing page mới", "Thuê TK nếu BM issue"],
    },
    "quang-cao-google": {
        "title": "Quảng cáo Google Ads",
        "group": "Quảng cáo",
        "overview": "Search, Shopping, Display, PMax — tối ưu CPA/ROAS.",
        "icp": "Search intent cao; e-commerce Shopping; ROAS/CPA target rõ; LP quality.",
        "call_script": '"Anh/chị chạy Google Ads — Search, Shopping hay PMax? '
        'Em hỏi ngân sách/tháng và conversion tracking hiện tại ạ?"',
        "phone_qs": [
            "Search/Shopping/Display/PMax?", "Merchant Center/feed status?", "Conversion tracking verified?",
            "ROAS/CPA target?", "Ngân sách/tháng?", "Geo & ngôn ngữ?", "AOV/margin sản phẩm?",
            "Lịch sử account spend?", "LP load time?", "Brand vs non-brand split?",
            "Agency cũ structure?", "SKU count e-comm?", "Lead gen hay e-comm?",
            "GA4 linked?", "Remarketing lists?",
        ],
        "red_flags": ["Conversion tracking sai", "LP chậm >5s", "Budget cạn giữa tháng không plan",
                      "Feed disapproved Shopping", "No conversion value setup"],
        "objections": [
            ("Google Smart Campaign đủ", "Full account = keyword control + QS + Shopping structure."),
            ("CPA cao hơn kỳ vọng", "Learning 2 tuần; benchmark ngành trước khi judge."),
            ("PMax black box", "Asset group strategy + search term insights + brand exclusion."),
            ("Tự chạy tiết kiệm fee", "Search term waste + negative keyword expertise."),
            ("Shopping feed phức tạp", "Feed optimization included onboarding."),
            ("Không cần GA4", "GA4 + Ads linked = better bidding signals."),
        ],
        "urgency": ["Feed disapproved blocking sales", "Competitor impression share drop",
                    "Q4 peak season prep", "New SKU launch", "Account suspended appeal"],
        "sla": "Phản hồi ≤2h · Keyword research call 1–3 ngày · Setup 3–5 ngày",
        "inperson_qs": [
            "Keyword intent mapping?", "Negative keyword list seed?", "Quality Score issues?",
            "Impression share target?", "Shopping feed attribute gaps?", "PMax asset group plan?",
            "Conversion action hierarchy?", "Enhanced conversions setup?", "Remarketing RLSA?",
            "Geo bid modifiers?", "Ad schedule performance?", "Landing page per ad group?",
            "Competitor auction insights?", "Budget pacing rules?", "Merchant Center policy?",
            "Product title optimization?", "Seasonality bid strategy?", "Brand protection campaign?",
            "Call tracking integration?", "LTV vs CPA model?", "Cross-sell Shopping PMax?",
        ],
        "demo_checklist": ["Account audit live", "Search term waste estimate", "Conversion tracking test",
                           "PageSpeed LP", "Merchant Center check", "Keyword opportunity preview"],
        "docs": [("LP URL", "☐", "☐"), ("SKU top sellers", "☐", "☐"), ("Screenshot Google Ads", "☐", "☐"),
                 ("Product feed sample", "☐", "☐"), ("Ads partner + GA4", "—", "☐"), ("GTM access", "—", "☐")],
        "kpi_questions": ["Impression share ≥60%?", "CPA/ROAS cam kết?", "Conversion data accurate?",
                          "Budget alert 50/75/90%?"],
        "scope_questions": ["IN: Search/Shopping/PMax manage?", "OUT: LP, feed creation, creative?",
                            "Min budget/tháng?", "Shopping feed optimization scope?"],
        "closing_script": '"Em gửi Proposal Google Ads — account structure, KPI, budget phân bổ. '
        'Tracking verify 48h sau ký. Họp [ngày] ạ?"',
        "upsell": ["Facebook Ads retargeting", "Landing page CRO", "SEO brand protection"],
    },
    "thue-tai-khoan-quang-cao": {
        "title": "Thuê Tài khoản Quảng cáo",
        "group": "Quảng cáo",
        "overview": "Thuê TK Meta/Google/TikTok — setup 1–2 ngày. Spend lớn, urgency cao.",
        "icp": "TK bị khóa; cần chạy gấp; không tự mở TK; spend lớn; ngành khó mở TK.",
        "call_script": '"Anh/chị cần thuê tài khoản quảng cáo — Meta, Google hay TikTok? '
        'Em hỏi lý do (bị khóa/mới/spend lớn) và ngân sách/tháng ạ?"',
        "phone_qs": [
            "Nền tảng: Meta/Google/TikTok?", "Suspended/limit/mới/chưa có TK?", "Sản phẩm quảng cáo cụ thể?",
            "Spend/tháng (VND)?", "Ai tạo creative?", "Payment ai chịu — KH hay PTT?",
            "Lịch sử vi phạm policy?", "Ngành regulated (YTE/TC/crypto)?", "BM hiện có link được không?",
            "Campaign đang chạy dở?", "Cần invoice/VAT?", "Số TK cần (1 hay nhiều)?",
            "Whitelist domain?", "CAPI/server-side?", "Thời hạn thuê dự kiến?",
        ],
        "red_flags": ["SP vi phạm policy", "KH không cho review creative pre-approval",
                      "Nhiều TK chết lịch sử", "Grey/black hat product", "Không ký HĐ điều khoản"],
        "objections": [
            ("Sợ TK bị khóa lại", "Pre-approval creative; policy compliance daily monitor."),
            ("Phí thuê cao", "So sánh downtime cost vs fee; min spend tier."),
            ("Không minh bạch spend", "Dashboard + invoice chi tiết hàng tháng."),
            ("Mất quyền kiểm soát campaign", "KH giữ creative + targeting; PTT giữ billing TK."),
            ("Rủi ro pháp lý", "HĐ rõ trách nhiệm; KH cam kết tuân policy."),
            ("Tự mở TK mới được", "Timeline 2–4 tuần verify; thuê = 1–2 ngày active."),
        ],
        "urgency": ["TK suspended campaign đang chạy", "Daily spend limit hit", "Launch product tuần này",
                    "Appeal rejected", "Scale spend vượt cap TK cũ"],
        "sla": "Phản hồi ≤2h · TK khóa ≤1h first response · Active TK 1–2 ngày sau HĐ",
        "inperson_qs": [
            "Product policy checklist pass?", "Landing page policy compliance?", "Creative pre-approval workflow?",
            "Spend cap & alert rules?", "Multi-account backup plan?", "Billing cycle & invoice format?",
            "VAT/export invoice need?", "BM admin roles?", "Pixel/domain ownership?", "Refund/chargeback policy?",
            "Termination notice period?", "Spend report frequency?", "Violation escalation contact?",
            "Industry certification docs?", "Geo restriction products?", "Age-gated products?",
            "Whitelisted domains list?", "CAPI ownership?", "Agency vs in-house operator?",
            "Renewal terms 30-day notice?", "Upsell full Ads management interest?",
        ],
        "demo_checklist": ["Policy review sample creative", "HĐ điều khoản walkthrough",
                           "Spend dashboard demo", "Setup timeline 1–2 ngày", "Backup account plan",
                           "Violation case study (anonymous)"],
        "docs": [("Screenshot email platform", "☐", "☐"), ("Mẫu creative", "☐", "☐"), ("GPKD", "☐", "☐"),
                 ("Mô tả lịch sử TK", "☐", "☐"), ("BM access + payment", "—", "☐"), ("HĐ ký + creative approved", "—", "☐")],
        "kpi_questions": ["TK active đúng hạn?", "Minh bạch spend 100%?", "0 vi phạm do KH creative?",
                          "Renewal rate?"],
        "scope_questions": ["IN: TK rental, billing, monitor?", "OUT: Ads management, creative?",
                            "% spend fee vs flat?", "Platforms included?"],
        "closing_script": '"Sản phẩm pass policy review — em gửi HĐ thuê TK, active 1–2 ngày. '
        'Ký + BM link hôm nay được không ạ?"',
        "upsell": ["Facebook/Google Ads management", "Landing page compliant", "Creative production"],
    },
    "tiep-thi-noi-dung": {
        "title": "Tiếp thị Nội dung",
        "group": "Nội dung",
        "overview": "Content marketing — blog, social; retainer bài/tháng.",
        "icp": "Không team viết nội bộ; cần traffic organic + brand; cần lịch publish đều.",
        "call_script": '"Anh/chị cần tiếp thị nội dung — blog, social hay cả hai? '
        'Em hỏi số bài/tháng và ngân sách retainer ạ?"',
        "phone_qs": [
            "Kênh: blog/social/cả hai?", "Số bài/tháng mong muốn?", "Ngân sách/tháng?",
            "Persona & tone brand?", "Nội dung cũ — URL?", "Ai duyệt — SLA bao lâu?",
            "Chủ đề cấm/claim pháp lý?", "Ai publish lên CMS?", "Từ khóa SEO ưu tiên?",
            "Ảnh/minh họa ai cung cấp?", "Ngành regulated?", "Social platform nào?",
            "Thought leadership vs SEO blog?", "AI content policy nội bộ?", "Mục tiêu: traffic vs brand?",
        ],
        "red_flags": ["Duyệt chậm >48h", "Không brand voice", "100% AI không human review",
                      "Không người duyệt xác định", "Chủ đề YMYL không expert review"],
        "objections": [
            ("Tự viết bằng ChatGPT", "PTT = strategy + SEO brief + edit + publish schedule."),
            ("Freelancer bài rẻ", "Retainer = calendar, QA, SEO on-page, reporting."),
            ("Không thấy traffic ngay", "Content compound 3–6 tháng; KPI tháng 1 = publish rate."),
            ("Brand voice khó", "Onboard workshop tone + 3 bài mẫu calibration."),
            ("Duyệt nhiều vòng", "SLA 48h trong HĐ; delay KH = shift calendar."),
            ("Social vs blog — chọn 1", "Bundle discount; repurposing 1 bài → 5 social."),
        ],
        "urgency": ["Launch brand cần content bank", "SEO gap vs competitor content",
                    "Rebrand cần voice mới", "Campaign cần blog support", "Investor due diligence"],
        "sla": "Phản hồi ≤2h · Strategy call 1–3 ngày · Calendar T1 trong proposal",
        "inperson_qs": [
            "Content pillar/cluster map?", "Persona doc chi tiết?", "Competitor content gap?",
            "Brand voice examples 5 bài?", "SEO keyword cluster priority?", "Content format mix?",
            "Expert interview access?", "Legal/compliance review process?", "CMS workflow publish?",
            "Image/infographic style?", "Social repurposing workflow?", "UGC integration?",
            "Thought leader byline?", "Multilingual content?", "Refresh old content plan?",
            "Distribution channels?", "Email newsletter integration?", "KPI: traffic vs engagement?",
            "Approval escalation path?", "Fact-check source requirements?", "Calendar flexibility 70/30?",
        ],
        "demo_checklist": ["Content calendar sample", "Bài mẫu ngành", "SEO brief template",
                           "Social repurposing example", "Traffic case study", "Brand voice workshop agenda"],
        "docs": [("Brand guideline", "☐", "☐"), ("Bài mẫu", "☐", "☐"), ("Link blog/social", "☐", "☐"),
                 ("Persona draft", "☐", "☐"), ("Tone/style guide", "—", "☐"), ("CMS access + keyword list", "—", "☐")],
        "kpi_questions": ["100% bài đúng lịch?", "SEO on-page pass?", "Traffic từ content tăng?",
                          "Engagement rate social?"],
        "scope_questions": ["IN: strategy, viết, SEO brief, publish?", "OUT: Ads, design, photography?",
                            "Số bài/word count?", "Revision rounds?"],
        "closing_script": '"Em gửi Proposal content — số bài/tháng, calendar T1, quy trình duyệt 48h. '
        'Workshop brand voice kickoff [ngày] ạ?"',
        "upsell": ["SEO tổng thể", "AEO FAQ content", "Facebook/Google Ads amplify"],
    },
}
# fmt: on


def build_service_sections(slug: str) -> list[str]:
    svc = SERVICE_FORMS[slug]
    overview = f"""<p><strong>Tổng quan:</strong> {svc["overview"]}</p>
<p><strong>ICP lý tưởng:</strong> {svc["icp"]}</p>
<p><strong>SLA:</strong> {svc["sla"]}</p>"""

    phone = (
        f'<div class="script-box"><strong>Script mở đầu (tailored)</strong><p>{svc["call_script"]}</p></div>'
        + render_question_block(svc["phone_qs"], "P")
        + f"<h3>Red flags</h3>{render_checkbox_group(svc['red_flags'], cols=2)}"
        + f"<h3>Urgency triggers</h3>{render_checkbox_group(svc['urgency'], cols=2)}"
        + render_objections(svc["objections"])
        + _bant_html(abbreviated=True)
        + _go_nogo_html()
    )

    inperson = (
        render_field("Recap cuộc gọi — pain point xác nhận", "textarea", wide=True)
        + f"<h3>Discovery sâu (15–20 câu)</h3>{render_question_block(svc['inperson_qs'], 'D')}"
        + f"<h3>Live audit / Demo checklist</h3>{render_checkbox_group(svc['demo_checklist'], cols=2)}"
        + render_field("Insight chính từ demo", "textarea", wide=True)
        + f"<h3>Tài liệu thu thập</h3>{render_table(['Tài liệu', 'Lead', 'Onboard'], svc['docs'], ['40%', '30%', '30%'])}"
        + f"<h3>KPI framing</h3>{render_question_block(svc['kpi_questions'], 'K')}"
        + f"<h3>Scope boundary</h3>{render_question_block(svc['scope_questions'], 'S')}"
        + f'<div class="script-box"><strong>Script chốt — book Proposal/Tư vấn</strong><p>{svc["closing_script"]}</p></div>'
        + f"<h3>Upsell paths</h3>{render_checkbox_group(svc['upsell'], cols=2)}"
        + render_field("Ngày họp Proposal / gửi báo giá", "text")
        + render_field("Người tham dự + budget xác nhận", "textarea", wide=True)
    )

    return [
        _section(f"{svc['title']} — Tổng quan & ICP", overview, "PHẦN A"),
        _section(f"Qualify qua điện thoại — {svc['title']}", phone, "PHẦN A"),
        _section(f"Gặp trực tiếp — {svc['title']}", inperson, "PHẦN B"),
        render_crm_footer(slug),
    ]


def generate_all() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    common_path = OUTPUT_DIR / "00-form-chung.html"
    common_path.write_text(
        build_html("Form tiếp nhận Lead — Chung (mọi dịch vụ)", "00-form-chung", build_common_sections()),
        encoding="utf-8",
    )
    written.append(common_path)

    for slug in SERVICE_SLUGS:
        svc = SERVICE_FORMS[slug]
        path = OUTPUT_DIR / f"{slug}.html"
        path.write_text(
            build_html(f"Form tiếp nhận Lead — {svc['title']}", slug, build_service_sections(slug)),
            encoding="utf-8",
        )
        written.append(path)

    return written


def main() -> None:
    files = generate_all()
    print(f"Generated {len(files)} HTML forms in {OUTPUT_DIR}:")
    for p in sorted(files):
        print(f"  - {p.name}")


if __name__ == "__main__":
    main()
