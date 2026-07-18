# Service Workflow Engine — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi card kanban `/crm/service-delivery` click vào mở trang workflow riêng, hiển thị 7 stages dạng tabs, mỗi stage có tasks với form + AI assist + tick hoàn thành.

**Architecture:** 2 module Python mới (`crm_svc_workflow_steps.py` — data-only, `crm_svc_tasks.py` — schema + logic), 5 routes thêm vào `app.py`, 1 template mới, cập nhật kanban card onclick.

**Tech Stack:** Flask 3 monolith, SQLite (`get_connection()`), Anthropic SDK trực tiếp (`claude-haiku-4-5-20251001`), Jinja2 + Vanilla JS.

## Global Constraints

- Auth pattern mọi page route: `redir = _ensure_admin_session_html(); if redir: return redir`
- Template extend: `{% extends "admin_layout.html" %}`, content block: `{% block admin_main %}`
- Mọi page route truyền `**_admin_page_template_kwargs()` vào `render_template`
- DB: `with get_connection() as conn:` — không dùng `conn.close()` thủ công
- Timestamps: `datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")`
- AI model: `claude-haiku-4-5-20251001`, synchronous, fail silent (return `""`)
- Tests: `unittest.TestCase` + SQLite in-memory + `conn.row_factory = sqlite3.Row`
- Không thêm feature ngoài yêu cầu (YAGNI)
- `delete_task` chỉ xoá `is_custom=1`
- `seed_tasks` idempotent: check `COUNT(*) WHERE is_custom=0` trước khi seed

---

### Task 1: crm_svc_workflow_steps.py — Steps data + AI prompts

**Files:**
- Create: `crm_svc_workflow_steps.py`

**Interfaces:**
- Produces: `SERVICE_WORKFLOW_STEPS: dict[str, dict[str, list[dict]]]` — key là service_slug → stage → list of `{title, description, ai_prompt_key, form_fields}`
- Produces: `AI_PROMPT_TEMPLATES: dict[str, str]` — key là prompt_key → template string với `{placeholder}`

- [ ] **Step 1: Tạo file**

```python
# crm_svc_workflow_steps.py
"""Steps định nghĩa cho 12 dịch vụ PTTP — data-only, không có logic."""
from __future__ import annotations

AI_PROMPT_TEMPLATES: dict[str, str] = {
    "qualify_lead": (
        "Bạn là chuyên gia {service_name} của agency PTT.\n"
        "Phân tích lead: ngành={niche}, ngân sách={budget}, nhu cầu={need}.\n\n"
        "Viết brief 200 từ: đánh giá tiềm năng (cao/trung/thấp), điểm đau chính, "
        "gợi ý package phù hợp, 3 câu hỏi cần hỏi thêm khi tư vấn."
    ),
    "consult_analysis": (
        "Bạn là chuyên gia {service_name} của agency PTT.\n"
        "KH: {customer_name}, ngành: {niche}. Tình trạng: {current_status}.\n\n"
        "Viết phân tích 250 từ: tình trạng hiện tại, cơ hội tăng trưởng, "
        "thách thức, hướng tiếp cận đề xuất."
    ),
    "draft_proposal": (
        "Bạn là chuyên gia {service_name} của agency PTT.\n"
        "KH: {customer_name}, ngành: {niche}, ngân sách: {budget}, mục tiêu: {goal}.\n\n"
        "Viết proposal 350 từ: tóm tắt giải pháp, phạm vi công việc, "
        "lộ trình {timeline} tháng, cam kết KPI, giá dịch vụ."
    ),
    "kickoff_brief": (
        "Bạn là chuyên gia {service_name} của agency PTT.\n"
        "KH: {customer_name}, bắt đầu: {start_date}.\n\n"
        "Tạo brief kickoff: thông tin dự án, phân công nhân sự, "
        "checklist access cần nhận, mốc tháng đầu, quy trình báo cáo."
    ),
    "progress_report": (
        "Bạn là chuyên gia {service_name} của agency PTT.\n"
        "KH: {customer_name}, kỳ: {report_period}.\n"
        "Đã làm: {completed_tasks}. Số liệu: {metrics}.\n\n"
        "Tạo báo cáo: kết quả kỳ này, KPI so với mục tiêu, "
        "vấn đề phát sinh, kế hoạch kỳ tiếp."
    ),
    "handover_report": (
        "Bạn là chuyên gia {service_name} của agency PTT.\n"
        "KH: {customer_name}. KPI cam kết: {kpi_target}. Đạt được: {kpi_actual}.\n\n"
        "Tạo báo cáo nghiệm thu: kết quả so với cam kết, "
        "highlight thành tựu, bài học, đề xuất bước tiếp theo."
    ),
    "upsell_suggest": (
        "Bạn là chuyên gia {service_name} của agency PTT.\n"
        "KH: {customer_name} dùng {months_active} tháng. KPI: {kpi_summary}.\n\n"
        "Đề xuất gia hạn + upsell: giá trị đã mang lại, lý do gia hạn, "
        "gợi ý nâng cấp package, dịch vụ bổ sung phù hợp."
    ),
}

SERVICE_WORKFLOW_STEPS: dict[str, dict[str, list[dict]]] = {

    "dich-vu-seo-tong-the": {
        "lead": [{
            "title": "Tiếp nhận & qualify lead SEO",
            "description": "AI qualify lead, gán tag SEO tổng thể. Phản hồi ≤2h. Xác nhận ngân sách tối thiểu và kỳ vọng traffic.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành KH", "type": "text"},
                {"key": "budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
                {"key": "domain", "label": "Website domain", "type": "text"},
                {"key": "need", "label": "Nhu cầu cụ thể", "type": "textarea"},
            ],
        }],
        "consult": [
            {
                "title": "Audit website & phân tích từ khóa",
                "description": "Phân tích technical SEO, tốc độ tải, Core Web Vitals. Nghiên cứu từ khóa mục tiêu, volume, difficulty. Ghi nhận đối thủ.",
                "ai_prompt_key": "consult_analysis",
                "form_fields": [
                    {"key": "current_status", "label": "Tình trạng website hiện tại", "type": "textarea"},
                    {"key": "top_competitors", "label": "Đối thủ chính", "type": "text"},
                    {"key": "target_keywords", "label": "Từ khóa mục tiêu", "type": "textarea"},
                ],
            },
        ],
        "proposal": [{
            "title": "Draft proposal SEO tổng thể",
            "description": "Soạn proposal: phạm vi công việc, timeline 3–6 tháng, cam kết KPI traffic và ranking.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "KPI cam kết", "type": "text"},
                {"key": "timeline", "label": "Timeline (tháng)", "type": "number"},
                {"key": "budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
            ],
        }],
        "onboard": [
            {
                "title": "Kickoff & nhận access",
                "description": "Nhận access GSC, GA4, hosting. Setup tool theo dõi. Đo baseline traffic và số từ khóa đang ranking.",
                "ai_prompt_key": "kickoff_brief",
                "form_fields": [
                    {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                    {"key": "gsc_access", "label": "GSC access", "type": "text"},
                    {"key": "ga4_access", "label": "GA4 access", "type": "text"},
                    {"key": "assigned_sp", "label": "SEO Specialist phụ trách", "type": "text"},
                ],
            },
        ],
        "deliver": [
            {
                "title": "Triển khai SEO tháng",
                "description": "On-page: meta tags, heading, nội dung theo từ khóa. Technical: fix lỗi crawl, sitemap. Off-page: link building. Báo cáo tháng.",
                "ai_prompt_key": "progress_report",
                "form_fields": [
                    {"key": "report_period", "label": "Tháng báo cáo", "type": "text"},
                    {"key": "completed_tasks", "label": "Công việc đã làm", "type": "textarea"},
                    {"key": "metrics", "label": "Traffic / Ranking tháng này", "type": "textarea"},
                ],
            },
        ],
        "handover": [{
            "title": "Báo cáo nghiệm thu SEO",
            "description": "Tổng hợp: traffic tăng trưởng, số từ khóa top 10, DA so với baseline.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "KPI cam kết ban đầu", "type": "textarea"},
                {"key": "kpi_actual", "label": "KPI đạt được thực tế", "type": "textarea"},
                {"key": "traffic_growth_pct", "label": "Tăng trưởng traffic (%)", "type": "number"},
            ],
        }],
        "retain": [{
            "title": "Gia hạn & upsell",
            "description": "Nhắc gia hạn trước 30 ngày. Gợi ý upsell: content marketing, AEO, Google Ads.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Số tháng sử dụng", "type": "number"},
                {"key": "kpi_summary", "label": "Tóm tắt KPI đạt được", "type": "textarea"},
            ],
        }],
    },

    "dich-vu-aeo": {
        "lead": [{
            "title": "Tiếp nhận lead AEO",
            "description": "Qualify lead, giải thích AEO (xuất hiện trong ChatGPT/Gemini/Perplexity). Kiểm tra KH có website và nội dung không.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành KH", "type": "text"},
                {"key": "domain", "label": "Website domain", "type": "text"},
                {"key": "budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
                {"key": "need", "label": "Nhu cầu", "type": "textarea"},
            ],
        }],
        "consult": [{
            "title": "Audit AI search presence",
            "description": "Kiểm tra KH xuất hiện trong ChatGPT/Gemini/Perplexity như thế nào. Xác định content gaps cần lấp.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "current_status", "label": "Kết quả audit AI search hiện tại", "type": "textarea"},
                {"key": "content_gaps", "label": "Content gaps phát hiện", "type": "textarea"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal AEO",
            "description": "Soạn proposal: chiến lược AEO, loại content cần tạo, timeline, cam kết tần suất xuất hiện trong AI search.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "Mục tiêu cam kết", "type": "text"},
                {"key": "timeline", "label": "Timeline (tháng)", "type": "number"},
                {"key": "budget", "label": "Ngân sách (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Kickoff AEO & đo baseline",
            "description": "Đo baseline tần suất xuất hiện trong AI search. Setup tracking tool. Brief content specialist.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "baseline_aeo", "label": "Baseline AI search presence", "type": "text"},
                {"key": "assigned_sp", "label": "Content Specialist phụ trách", "type": "text"},
            ],
        }],
        "deliver": [{
            "title": "Sản xuất AEO content tháng",
            "description": "Tạo FAQ content, schema markup, E-E-A-T signals theo kế hoạch. Monitor AI search weekly. Báo cáo tháng.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tháng báo cáo", "type": "text"},
                {"key": "completed_tasks", "label": "Content đã tạo", "type": "textarea"},
                {"key": "metrics", "label": "Tần suất AI search tháng này", "type": "textarea"},
            ],
        }],
        "handover": [{
            "title": "Báo cáo nghiệm thu AEO",
            "description": "Tổng hợp: tần suất xuất hiện, loại query được cover, so với baseline.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "KPI cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "KPI đạt được", "type": "textarea"},
            ],
        }],
        "retain": [{
            "title": "Gia hạn AEO & upsell",
            "description": "Nhắc gia hạn. Gợi ý upsell: SEO tổng thể, content marketing.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Số tháng sử dụng", "type": "number"},
                {"key": "kpi_summary", "label": "Tóm tắt KPI", "type": "textarea"},
            ],
        }],
    },

    "dich-vu-seo-local": {
        "lead": [{
            "title": "Tiếp nhận lead SEO Local",
            "description": "Qualify lead, kiểm tra Google Business Profile (GBP) hiện tại. Xác nhận địa chỉ và khu vực kinh doanh.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành", "type": "text"},
                {"key": "city", "label": "Thành phố / khu vực", "type": "text"},
                {"key": "gbp_status", "label": "Tình trạng GBP hiện tại", "type": "text"},
                {"key": "budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
            ],
        }],
        "consult": [{
            "title": "GBP audit & local keyword research",
            "description": "Audit GBP: thông tin đầy đủ chưa, review count, ảnh, Q&A. Nghiên cứu từ khóa local.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "current_status", "label": "Kết quả GBP audit", "type": "textarea"},
                {"key": "local_keywords", "label": "Từ khóa local mục tiêu", "type": "textarea"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal SEO Local",
            "description": "Proposal: tối ưu GBP, citation building, local content, cam kết top Local Pack.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "KPI cam kết (Local Pack %)", "type": "text"},
                {"key": "timeline", "label": "Timeline (tháng)", "type": "number"},
                {"key": "budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "GBP setup & citation plan",
            "description": "Tối ưu GBP đầy đủ. Lên danh sách citation sites. Setup tracking Local Pack.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "gbp_url", "label": "GBP profile URL", "type": "text"},
            ],
        }],
        "deliver": [{
            "title": "Triển khai SEO Local tháng",
            "description": "GBP posts weekly, citation building, review management, local content. Báo cáo tháng.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tháng báo cáo", "type": "text"},
                {"key": "gbp_views", "label": "GBP views tháng này", "type": "number"},
                {"key": "local_pack_pct", "label": "Xuất hiện Local Pack (%)", "type": "number"},
            ],
        }],
        "handover": [{
            "title": "Báo cáo nghiệm thu SEO Local",
            "description": "Kết quả: GBP views tăng, Local Pack ranking, review count so với baseline.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "KPI cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "KPI đạt được", "type": "textarea"},
            ],
        }],
        "retain": [{
            "title": "Gia hạn SEO Local & upsell",
            "description": "Nhắc gia hạn. Gợi ý upsell: SEO tổng thể, Google Ads Maps.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Số tháng sử dụng", "type": "number"},
                {"key": "kpi_summary", "label": "Tóm tắt KPI", "type": "textarea"},
            ],
        }],
    },

    "dich-vu-seo-audit": {
        "lead": [{
            "title": "Tiếp nhận lead SEO Audit",
            "description": "Qualify lead, xác nhận website cần audit, timeline nhận báo cáo mong muốn.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "domain", "label": "Website cần audit", "type": "text"},
                {"key": "niche", "label": "Ngành", "type": "text"},
                {"key": "budget", "label": "Ngân sách audit (VND)", "type": "number"},
                {"key": "need", "label": "Mục tiêu audit", "type": "textarea"},
            ],
        }],
        "consult": [{
            "title": "Scoping & phân tích sơ bộ",
            "description": "Xác định phạm vi audit: technical, on-page, off-page, content, competitor. Báo giá chính xác.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "audit_scope", "label": "Phạm vi audit", "type": "textarea"},
                {"key": "current_status", "label": "Tình trạng website sơ bộ", "type": "textarea"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal SEO Audit",
            "description": "Proposal: danh mục kiểm tra, tool sử dụng, định dạng báo cáo, timeline giao hàng.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "Deliverables cam kết", "type": "text"},
                {"key": "timeline", "label": "Timeline giao báo cáo (ngày)", "type": "number"},
                {"key": "budget", "label": "Phí audit (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Nhận access & bắt đầu audit",
            "description": "Nhận access GSC, GA4, hosting. Bắt đầu crawl và phân tích.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "gsc_access", "label": "GSC access", "type": "text"},
                {"key": "ga4_access", "label": "GA4 access", "type": "text"},
            ],
        }],
        "deliver": [{
            "title": "Thực hiện audit & viết báo cáo",
            "description": "Chạy audit đầy đủ: technical, on-page, backlink, content, competitor. Viết báo cáo với action items ưu tiên.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tiến độ", "type": "text"},
                {"key": "completed_tasks", "label": "Hạng mục đã audit xong", "type": "textarea"},
                {"key": "issues_found", "label": "Số issues phát hiện", "type": "number"},
            ],
        }],
        "handover": [{
            "title": "Giao báo cáo & thuyết trình",
            "description": "Giao báo cáo hoàn chỉnh. Thuyết trình kết quả và hướng dẫn action items ưu tiên. KH ký nhận.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "Deliverables đã cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "Deliverables đã giao", "type": "textarea"},
                {"key": "issues_critical", "label": "Số issues critical", "type": "number"},
            ],
        }],
        "retain": [{
            "title": "Upsell SEO triển khai sau audit",
            "description": "Đề xuất KH thuê SEO tổng thể để implement action items trong báo cáo.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Ngày từ khi nhận báo cáo", "type": "number"},
                {"key": "kpi_summary", "label": "Issues quan trọng cần fix", "type": "textarea"},
            ],
        }],
    },

    "dich-vu-quan-tri-website": {
        "lead": [{
            "title": "Tiếp nhận lead quản trị website",
            "description": "Qualify lead, xác nhận loại website (WordPress/custom), nhu cầu: cập nhật nội dung, fix lỗi, bảo mật.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "domain", "label": "Website domain", "type": "text"},
                {"key": "platform", "label": "Nền tảng (WordPress/custom)", "type": "text"},
                {"key": "niche", "label": "Ngành", "type": "text"},
                {"key": "budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
            ],
        }],
        "consult": [{
            "title": "Đánh giá website & xác định scope",
            "description": "Kiểm tra: tốc độ, bảo mật, backup, phiên bản plugin. Xác định scope quản trị hàng tháng.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "current_status", "label": "Tình trạng website hiện tại", "type": "textarea"},
                {"key": "pain_points", "label": "Vấn đề cần giải quyết", "type": "textarea"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal quản trị website",
            "description": "Proposal: scope dịch vụ, SLA response time, backup policy, tần suất cập nhật.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "Scope dịch vụ", "type": "textarea"},
                {"key": "timeline", "label": "Hợp đồng (tháng)", "type": "number"},
                {"key": "budget", "label": "Phí/tháng (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Nhận access & setup backup",
            "description": "Nhận admin website, hosting, domain. Setup backup tự động. Security scan lần đầu.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "admin_access", "label": "Admin access", "type": "text"},
                {"key": "hosting_access", "label": "Hosting access", "type": "text"},
            ],
        }],
        "deliver": [{
            "title": "Quản trị tháng",
            "description": "Cập nhật content, fix lỗi, update plugin/theme, backup check, báo cáo uptime tháng.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tháng báo cáo", "type": "text"},
                {"key": "completed_tasks", "label": "Công việc tháng này", "type": "textarea"},
                {"key": "uptime_pct", "label": "Uptime (%)", "type": "number"},
            ],
        }],
        "handover": [{
            "title": "Báo cáo & nghiệm thu",
            "description": "Tổng kết: số lần cập nhật, uptime, lỗi đã fix, security incidents.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "SLA cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "Kết quả thực tế", "type": "textarea"},
            ],
        }],
        "retain": [{
            "title": "Gia hạn & upsell",
            "description": "Nhắc gia hạn. Đề xuất upsell: SEO, redesign nếu website cũ.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Số tháng sử dụng", "type": "number"},
                {"key": "kpi_summary", "label": "Tóm tắt hiệu suất", "type": "textarea"},
            ],
        }],
    },

    "thiet-ke-website": {
        "lead": [{
            "title": "Tiếp nhận lead thiết kế website",
            "description": "Qualify lead: loại website, số trang, tham khảo design, budget, deadline.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành", "type": "text"},
                {"key": "website_type", "label": "Loại website (corporate/ecomm/portfolio)", "type": "text"},
                {"key": "budget", "label": "Ngân sách (VND)", "type": "number"},
                {"key": "deadline", "label": "Deadline mong muốn", "type": "date"},
            ],
        }],
        "consult": [{
            "title": "Thu thập yêu cầu chi tiết",
            "description": "Họp tư vấn: mục tiêu website, đối tượng người dùng, website tham khảo, tính năng cần có.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "current_status", "label": "Yêu cầu chi tiết", "type": "textarea"},
                {"key": "design_refs", "label": "Website tham khảo (URLs)", "type": "textarea"},
                {"key": "pages_count", "label": "Số trang cần thiết kế", "type": "number"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal thiết kế",
            "description": "Proposal: scope, số revision, timeline, format bàn giao (Figma/PSD).",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "Deliverables cam kết", "type": "textarea"},
                {"key": "timeline", "label": "Timeline (tuần)", "type": "number"},
                {"key": "budget", "label": "Phí thiết kế (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Nhận brand assets & confirm sitemap",
            "description": "Nhận: logo, màu sắc, font, nội dung trang, ảnh. Confirm sitemap và wireframe sơ bộ.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "brand_assets", "label": "Brand assets đã nhận", "type": "textarea"},
                {"key": "sitemap", "label": "Sitemap đã confirm", "type": "textarea"},
            ],
        }],
        "deliver": [{
            "title": "Thiết kế & revision",
            "description": "Thiết kế mockup → KH review → chỉnh sửa (tối đa 2 vòng) → final design.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tuần", "type": "text"},
                {"key": "completed_tasks", "label": "Trang đã thiết kế xong", "type": "textarea"},
                {"key": "revision_round", "label": "Vòng revision hiện tại", "type": "number"},
            ],
        }],
        "handover": [{
            "title": "Bàn giao file thiết kế",
            "description": "Giao file Figma/PSD, export assets, hướng dẫn sử dụng. KH ký nghiệm thu.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "Deliverables cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "Files đã bàn giao", "type": "textarea"},
            ],
        }],
        "retain": [{
            "title": "Upsell sau thiết kế",
            "description": "Đề xuất: code website từ design, SEO, quản trị website, landing page thêm.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Ngày từ khi bàn giao", "type": "number"},
                {"key": "kpi_summary", "label": "Sản phẩm đã bàn giao", "type": "textarea"},
            ],
        }],
    },

    "thiet-ke-website-tron-goi": {
        "lead": [{
            "title": "Tiếp nhận lead website trọn gói",
            "description": "Qualify lead: cần design + code + go-live, loại website, tính năng, budget.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành", "type": "text"},
                {"key": "website_type", "label": "Loại website", "type": "text"},
                {"key": "features", "label": "Tính năng cần có", "type": "textarea"},
                {"key": "budget", "label": "Ngân sách (VND)", "type": "number"},
            ],
        }],
        "consult": [{
            "title": "Tư vấn kỹ thuật & thu thập yêu cầu",
            "description": "Họp chi tiết: tính năng, tích hợp (payment/CRM), hosting, domain, SEO cơ bản.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "current_status", "label": "Yêu cầu kỹ thuật chi tiết", "type": "textarea"},
                {"key": "integrations", "label": "Tích hợp cần thiết", "type": "text"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal website trọn gói",
            "description": "Proposal: scope design + dev, milestones, warranty, hosting recommendation.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "Scope dự án", "type": "textarea"},
                {"key": "timeline", "label": "Timeline (tuần)", "type": "number"},
                {"key": "budget", "label": "Phí trọn gói (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Kickoff & setup hosting/domain",
            "description": "Nhận brand assets, nội dung. Setup hosting/domain. Lên kế hoạch sprint.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "hosting_info", "label": "Hosting/domain info", "type": "text"},
                {"key": "sprint_plan", "label": "Kế hoạch sprint", "type": "textarea"},
            ],
        }],
        "deliver": [{
            "title": "Design → Dev → Testing → Staging",
            "description": "Thiết kế mockup → code → test → staging → KH review → điều chỉnh → go-live.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tuần/Sprint", "type": "text"},
                {"key": "completed_tasks", "label": "Milestone đã hoàn thành", "type": "textarea"},
                {"key": "current_phase", "label": "Phase hiện tại", "type": "text"},
            ],
        }],
        "handover": [{
            "title": "Go-live & bàn giao website",
            "description": "Deploy production. Bàn giao: source code, admin access, hướng dẫn. Training AM.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "Deliverables cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "Đã bàn giao", "type": "textarea"},
                {"key": "live_url", "label": "URL live", "type": "text"},
            ],
        }],
        "retain": [{
            "title": "Hậu mãi 1 tháng & upsell",
            "description": "Hỗ trợ 1 tháng sau go-live. Đề xuất: quản trị website, SEO, quảng cáo.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Ngày từ go-live", "type": "number"},
                {"key": "kpi_summary", "label": "Tình trạng website sau go-live", "type": "textarea"},
            ],
        }],
    },

    "thiet-ke-landing-page": {
        "lead": [{
            "title": "Tiếp nhận lead landing page",
            "description": "Qualify lead: mục đích (lead gen/sales/event), campaign đi kèm, deadline.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành", "type": "text"},
                {"key": "lp_purpose", "label": "Mục đích landing page", "type": "text"},
                {"key": "campaign", "label": "Campaign đi kèm (Ads/Email...)", "type": "text"},
                {"key": "budget", "label": "Ngân sách (VND)", "type": "number"},
            ],
        }],
        "consult": [{
            "title": "Brief landing page",
            "description": "Xác định: đối tượng mục tiêu, USP, CTA chính, offer, tone of voice.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "target_audience", "label": "Đối tượng mục tiêu", "type": "textarea"},
                {"key": "usp", "label": "USP / điểm khác biệt", "type": "text"},
                {"key": "cta", "label": "CTA chính", "type": "text"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal landing page",
            "description": "Proposal: số section, số revision, có code không, timeline giao hàng.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "Deliverables", "type": "text"},
                {"key": "timeline", "label": "Timeline (ngày)", "type": "number"},
                {"key": "budget", "label": "Phí (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Nhận brief & assets",
            "description": "Nhận: logo, ảnh sản phẩm, copy draft, màu sắc thương hiệu.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "assets_received", "label": "Assets đã nhận", "type": "textarea"},
            ],
        }],
        "deliver": [{
            "title": "Thiết kế & revision LP",
            "description": "Design mockup → KH review → chỉnh sửa → export/code.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Ngày", "type": "text"},
                {"key": "completed_tasks", "label": "Đã hoàn thành", "type": "textarea"},
                {"key": "revision_round", "label": "Vòng revision", "type": "number"},
            ],
        }],
        "handover": [{
            "title": "Bàn giao landing page",
            "description": "Giao file design + code. Test mobile/desktop. Hướng dẫn nhúng vào website.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "Deliverables cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "Đã bàn giao", "type": "textarea"},
            ],
        }],
        "retain": [{
            "title": "Upsell sau landing page",
            "description": "Đề xuất: A/B test version mới, chạy Ads vào LP, website đầy đủ.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Ngày từ bàn giao", "type": "number"},
                {"key": "kpi_summary", "label": "Hiệu suất LP (CVR, leads...)", "type": "textarea"},
            ],
        }],
    },

    "quang-cao-facebook": {
        "lead": [{
            "title": "Tiếp nhận lead Facebook Ads",
            "description": "Qualify lead: tài khoản Ads có không, ngân sách/ngày, mục tiêu (lead/sale/traffic).",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành sản phẩm", "type": "text"},
                {"key": "daily_budget", "label": "Ngân sách/ngày (VND)", "type": "number"},
                {"key": "campaign_goal", "label": "Mục tiêu campaign", "type": "text"},
                {"key": "has_ads_account", "label": "Có tài khoản Ads không", "type": "text"},
            ],
        }],
        "consult": [{
            "title": "Phân tích & lên strategy",
            "description": "Phân tích đối tượng, sản phẩm, đối thủ. Strategy: objective, targeting, format creative.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "target_audience", "label": "Đối tượng mục tiêu", "type": "textarea"},
                {"key": "current_status", "label": "Kết quả Ads trước đây", "type": "textarea"},
                {"key": "product_usp", "label": "USP sản phẩm", "type": "textarea"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal Facebook Ads",
            "description": "Proposal: cấu trúc campaign, KPI cam kết (CTR/CPL/ROAS), phí quản lý.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "KPI cam kết (CTR min, CPL target)", "type": "text"},
                {"key": "timeline", "label": "Timeline (tháng)", "type": "number"},
                {"key": "budget", "label": "Phí quản lý/tháng (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Setup BM, Pixel & campaign",
            "description": "Setup Business Manager, pixel, custom audience. Tạo campaign structure đầu tiên. Brief creative.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày launch", "type": "date"},
                {"key": "bm_id", "label": "Business Manager ID", "type": "text"},
                {"key": "pixel_status", "label": "Pixel status", "type": "text"},
            ],
        }],
        "deliver": [{
            "title": "Vận hành & tối ưu tháng",
            "description": "Monitor daily, A/B test creative, tối ưu targeting và bidding, scale winning ads. Báo cáo tháng.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tháng báo cáo", "type": "text"},
                {"key": "spend", "label": "Tổng spend (VND)", "type": "number"},
                {"key": "metrics", "label": "CTR / CPL / ROAS tháng này", "type": "textarea"},
            ],
        }],
        "handover": [{
            "title": "Báo cáo nghiệm thu Facebook Ads",
            "description": "Tổng kết: tổng spend, leads/sales, ROI, bài học tối ưu.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "KPI cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "KPI đạt được", "type": "textarea"},
                {"key": "total_spend", "label": "Tổng spend (VND)", "type": "number"},
            ],
        }],
        "retain": [{
            "title": "Gia hạn & upsell Ads",
            "description": "Nhắc gia hạn. Đề xuất: tăng ngân sách, thêm kênh Google Ads, retargeting.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Số tháng chạy Ads", "type": "number"},
                {"key": "kpi_summary", "label": "Performance tổng hợp", "type": "textarea"},
            ],
        }],
    },

    "quang-cao-google": {
        "lead": [{
            "title": "Tiếp nhận lead Google Ads",
            "description": "Qualify lead: Google Ads account có không, ngân sách, mục tiêu (Search/Display/Shopping).",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành / sản phẩm", "type": "text"},
                {"key": "monthly_budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
                {"key": "campaign_type", "label": "Loại campaign mục tiêu", "type": "text"},
                {"key": "has_google_ads", "label": "Có Google Ads account không", "type": "text"},
            ],
        }],
        "consult": [{
            "title": "Keyword research & account strategy",
            "description": "Nghiên cứu từ khóa, đối thủ, ước tính CPC. Lên account structure.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "target_keywords", "label": "Từ khóa mục tiêu", "type": "textarea"},
                {"key": "current_status", "label": "Kết quả Google Ads hiện tại", "type": "textarea"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal Google Ads",
            "description": "Proposal: account structure, KPI cam kết (Impression Share/CPA), phí quản lý.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "KPI cam kết", "type": "text"},
                {"key": "timeline", "label": "Timeline (tháng)", "type": "number"},
                {"key": "budget", "label": "Phí quản lý/tháng (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Setup account & conversion tracking",
            "description": "Setup Google Ads account, conversion tracking, campaign structure, ad copy đầu tiên.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày launch", "type": "date"},
                {"key": "account_id", "label": "Google Ads Account ID", "type": "text"},
                {"key": "conversion_tracking", "label": "Conversion tracking status", "type": "text"},
            ],
        }],
        "deliver": [{
            "title": "Vận hành & tối ưu Google Ads",
            "description": "Monitor daily, tối ưu bid, negative keywords, Quality Score, A/B test ad copy.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tháng báo cáo", "type": "text"},
                {"key": "spend", "label": "Tổng spend (VND)", "type": "number"},
                {"key": "metrics", "label": "Impression Share / CPA / Conversions", "type": "textarea"},
            ],
        }],
        "handover": [{
            "title": "Báo cáo nghiệm thu Google Ads",
            "description": "Tổng kết: spend, conversions, CPA, ROAS so với mục tiêu.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "KPI cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "KPI đạt được", "type": "textarea"},
            ],
        }],
        "retain": [{
            "title": "Gia hạn & upsell Google Ads",
            "description": "Nhắc gia hạn. Đề xuất: mở rộng Shopping/Display/PMax, thêm Facebook Ads.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Số tháng chạy Ads", "type": "number"},
                {"key": "kpi_summary", "label": "Performance tổng hợp", "type": "textarea"},
            ],
        }],
    },

    "thue-tai-khoan-quang-cao": {
        "lead": [{
            "title": "Tiếp nhận lead thuê tài khoản Ads",
            "description": "Qualify lead: nền tảng (Meta/Google/TikTok), ngân sách/tháng, urgency (bị khóa / mới / khác).",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "platform", "label": "Nền tảng (Meta/Google/TikTok)", "type": "text"},
                {"key": "monthly_spend", "label": "Ngân sách/tháng (VND)", "type": "number"},
                {"key": "urgency", "label": "Lý do cần thuê", "type": "text"},
                {"key": "niche", "label": "Ngành", "type": "text"},
            ],
        }],
        "consult": [{
            "title": "Đánh giá rủi ro & điều khoản",
            "description": "Đánh giá lịch sử tài khoản KH, rủi ro vi phạm policy. Giải thích điều khoản sử dụng.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "current_status", "label": "Lịch sử tài khoản KH", "type": "textarea"},
                {"key": "risk_assessment", "label": "Đánh giá rủi ro", "type": "text"},
            ],
        }],
        "proposal": [{
            "title": "Draft hợp đồng thuê tài khoản",
            "description": "Hợp đồng: phí thuê, % spend, điều khoản sử dụng, trách nhiệm 2 bên, điều kiện chấm dứt.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "goal", "label": "Điều khoản chính", "type": "textarea"},
                {"key": "budget", "label": "Phí thuê/tháng (VND)", "type": "number"},
                {"key": "timeline", "label": "Thời hạn hợp đồng (tháng)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Setup tài khoản & hướng dẫn KH",
            "description": "Cấu hình tài khoản, payment method, Business Manager. Hướng dẫn quy tắc sử dụng.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "account_setup", "label": "Thông tin tài khoản đã setup", "type": "textarea"},
            ],
        }],
        "deliver": [{
            "title": "Monitor tài khoản tháng",
            "description": "Monitor daily, xử lý cảnh báo trong 2h, báo cáo spend tháng trước ngày 5.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tháng báo cáo", "type": "text"},
                {"key": "total_spend", "label": "Tổng spend tháng (VND)", "type": "number"},
                {"key": "account_status", "label": "Tình trạng tài khoản", "type": "text"},
            ],
        }],
        "handover": [{
            "title": "Báo cáo & hóa đơn",
            "description": "Gửi báo cáo spend chi tiết, hóa đơn minh bạch. Tổng kết SLA đã thực hiện.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "SLA cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "Kết quả thực tế", "type": "textarea"},
            ],
        }],
        "retain": [{
            "title": "Gia hạn & upsell quản lý Ads",
            "description": "Nhắc gia hạn. Đề xuất upgrade: thuê tài khoản + quản lý Ads toàn diện.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Số tháng thuê", "type": "number"},
                {"key": "kpi_summary", "label": "Uptime và tình trạng tài khoản", "type": "textarea"},
            ],
        }],
    },

    "tiep-thi-noi-dung": {
        "lead": [{
            "title": "Tiếp nhận lead content marketing",
            "description": "Qualify lead: kênh (blog/social/cả hai), số bài/tháng, ngân sách, mục tiêu traffic/brand.",
            "ai_prompt_key": "qualify_lead",
            "form_fields": [
                {"key": "niche", "label": "Ngành", "type": "text"},
                {"key": "channels", "label": "Kênh cần content (blog/social/...)", "type": "text"},
                {"key": "articles_per_month", "label": "Số bài/tháng mong muốn", "type": "number"},
                {"key": "budget", "label": "Ngân sách/tháng (VND)", "type": "number"},
            ],
        }],
        "consult": [{
            "title": "Phân tích content & lên strategy",
            "description": "Phân tích content KH đang có, đối thủ, cơ hội. Gợi ý cluster chủ đề và content calendar sơ bộ.",
            "ai_prompt_key": "consult_analysis",
            "form_fields": [
                {"key": "current_status", "label": "Content KH đang có", "type": "textarea"},
                {"key": "top_competitors", "label": "Đối thủ về content", "type": "text"},
                {"key": "target_audience", "label": "Đối tượng độc giả", "type": "textarea"},
            ],
        }],
        "proposal": [{
            "title": "Draft proposal content marketing",
            "description": "Proposal: số bài, định dạng, content calendar tháng 1 mẫu, quy trình duyệt, cam kết KPI.",
            "ai_prompt_key": "draft_proposal",
            "form_fields": [
                {"key": "articles_count", "label": "Số bài/tháng cam kết", "type": "number"},
                {"key": "goal", "label": "KPI traffic cam kết", "type": "text"},
                {"key": "budget", "label": "Phí/tháng (VND)", "type": "number"},
            ],
        }],
        "onboard": [{
            "title": "Strategy brief & content calendar tháng 1",
            "description": "Nhận brand guideline, tone of voice, từ khóa ưu tiên. Confirm content calendar tháng 1.",
            "ai_prompt_key": "kickoff_brief",
            "form_fields": [
                {"key": "start_date", "label": "Ngày bắt đầu", "type": "date"},
                {"key": "tone_of_voice", "label": "Tone of voice", "type": "text"},
                {"key": "content_calendar", "label": "Content calendar tháng 1", "type": "textarea"},
            ],
        }],
        "deliver": [{
            "title": "Sản xuất content tháng",
            "description": "Viết bài theo brief, review SEO on-page, KH duyệt, publish đúng lịch. Báo cáo tháng.",
            "ai_prompt_key": "progress_report",
            "form_fields": [
                {"key": "report_period", "label": "Tháng báo cáo", "type": "text"},
                {"key": "articles_published", "label": "Số bài đã publish", "type": "number"},
                {"key": "organic_traffic", "label": "Traffic từ content tháng này", "type": "number"},
            ],
        }],
        "handover": [{
            "title": "Báo cáo nghiệm thu content",
            "description": "Tổng hợp: số bài publish, traffic tăng trưởng, từ khóa vào top 20.",
            "ai_prompt_key": "handover_report",
            "form_fields": [
                {"key": "kpi_target", "label": "KPI cam kết", "type": "textarea"},
                {"key": "kpi_actual", "label": "KPI đạt được", "type": "textarea"},
                {"key": "traffic_growth_pct", "label": "Tăng trưởng traffic (%)", "type": "number"},
            ],
        }],
        "retain": [{
            "title": "Gia hạn & upsell content",
            "description": "Nhắc gia hạn. Đề xuất: tăng số bài, thêm kênh (video/infographic), SEO tổng thể.",
            "ai_prompt_key": "upsell_suggest",
            "form_fields": [
                {"key": "months_active", "label": "Số tháng sử dụng", "type": "number"},
                {"key": "kpi_summary", "label": "Traffic và ranking tổng hợp", "type": "textarea"},
            ],
        }],
    },
}
```

- [ ] **Step 2: Verify import OK**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python -c "from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS, AI_PROMPT_TEMPLATES; print(len(SERVICE_WORKFLOW_STEPS), 'services,', len(AI_PROMPT_TEMPLATES), 'prompts')"
```

Expected: `12 services, 7 prompts`

- [ ] **Step 3: Commit**

```bash
git add crm_svc_workflow_steps.py
git commit -m "feat: add SERVICE_WORKFLOW_STEPS + AI_PROMPT_TEMPLATES for 12 services"
```

---

### Task 2: crm_svc_tasks.py — Schema + logic + tests (TDD)

**Files:**
- Create: `crm_svc_tasks.py`
- Create: `tests/test_crm_svc_tasks.py`

**Interfaces:**
- Consumes: `crm_svc_workflow_steps.SERVICE_WORKFLOW_STEPS`, `crm_svc_workflow_steps.AI_PROMPT_TEMPLATES`
- Consumes: `crm_service_lifecycle.VALID_STAGES`
- Produces:
  - `ensure_schema(conn) -> None`
  - `seed_tasks(conn, lifecycle_id: int, service_slug: str) -> int`
  - `list_tasks(conn, lifecycle_id: int) -> dict[str, list[dict]]`
  - `update_task(conn, task_id: int, *, is_done=None, notes=None, form_data=None, done_by=None) -> None`
  - `create_custom_task(conn, lifecycle_id: int, stage: str, title: str, description: str = "") -> int`
  - `delete_task(conn, task_id: int) -> bool`
  - `run_ai_assist(conn, task_id: int, customer_context: dict) -> str`
  - `get_progress(conn, lifecycle_id: int) -> dict[str, dict]`
  - `SERVICE_LABELS: dict[str, str]`

- [ ] **Step 1: Viết tests (failing)**

```python
# tests/test_crm_svc_tasks.py
"""Tests cho crm_svc_tasks module."""
from __future__ import annotations

import sqlite3
import unittest

from crm_svc_tasks import (
    SERVICE_LABELS,
    create_custom_task,
    delete_task,
    ensure_schema,
    get_progress,
    list_tasks,
    seed_tasks,
    update_task,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS crm_staff (id INTEGER PRIMARY KEY)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'active',
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        INSERT INTO crm_service_lifecycle
            (id, service_slug, stage, status, stage_entered_at, created_at, updated_at)
        VALUES (1, 'dich-vu-seo-tong-the', 'lead', 'active',
                '2026-06-23 00:00:00', '2026-06-23 00:00:00', '2026-06-23 00:00:00')
    """)
    conn.commit()
    ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_table_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_svc_tasks", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        ensure_schema(conn)  # gọi lần 2 không lỗi
        ensure_schema(conn)


class TestSeedTasks(unittest.TestCase):
    def test_seeds_correct_count(self):
        conn = _setup_conn()
        count = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertGreater(count, 0)
        db_count = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = 1"
        ).fetchone()[0]
        self.assertEqual(db_count, count)

    def test_idempotent_second_call_returns_zero(self):
        conn = _setup_conn()
        count1 = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        count2 = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertGreater(count1, 0)
        self.assertEqual(count2, 0)

    def test_unknown_slug_returns_zero(self):
        conn = _setup_conn()
        count = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-khong-ton-tai")
        self.assertEqual(count, 0)

    def test_form_fields_stored_as_json(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        row = conn.execute(
            "SELECT form_fields FROM crm_svc_tasks WHERE lifecycle_id = 1 LIMIT 1"
        ).fetchone()
        import json
        fields = json.loads(row["form_fields"])
        self.assertIsInstance(fields, list)


class TestListTasks(unittest.TestCase):
    def test_returns_dict_by_stage(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        result = list_tasks(conn, lifecycle_id=1)
        self.assertIsInstance(result, dict)
        self.assertIn("lead", result)
        self.assertIsInstance(result["lead"], list)
        self.assertGreater(len(result["lead"]), 0)

    def test_form_data_is_dict(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        result = list_tasks(conn, lifecycle_id=1)
        task = result["lead"][0]
        self.assertIsInstance(task["form_data"], dict)

    def test_form_fields_is_list(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        result = list_tasks(conn, lifecycle_id=1)
        task = result["lead"][0]
        self.assertIsInstance(task["form_fields"], list)

    def test_empty_lifecycle_returns_empty(self):
        conn = _setup_conn()
        result = list_tasks(conn, lifecycle_id=999)
        self.assertEqual(result, {})


class TestUpdateTask(unittest.TestCase):
    def _get_task_id(self, conn):
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        return conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 LIMIT 1"
        ).fetchone()["id"]

    def test_mark_done(self):
        conn = _setup_conn()
        tid = self._get_task_id(conn)
        update_task(conn, tid, is_done=True)
        row = conn.execute(
            "SELECT is_done, done_at FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
        self.assertEqual(row["is_done"], 1)
        self.assertTrue(len(row["done_at"]) > 0)

    def test_mark_undone_clears_done_at(self):
        conn = _setup_conn()
        tid = self._get_task_id(conn)
        update_task(conn, tid, is_done=True)
        update_task(conn, tid, is_done=False)
        row = conn.execute(
            "SELECT is_done, done_at FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
        self.assertEqual(row["is_done"], 0)
        self.assertEqual(row["done_at"], "")

    def test_save_notes(self):
        conn = _setup_conn()
        tid = self._get_task_id(conn)
        update_task(conn, tid, notes="Ghi chú test")
        row = conn.execute(
            "SELECT notes FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
        self.assertEqual(row["notes"], "Ghi chú test")

    def test_save_form_data(self):
        conn = _setup_conn()
        tid = self._get_task_id(conn)
        update_task(conn, tid, form_data={"niche": "bất động sản", "budget": 5000000})
        result = list_tasks(conn, lifecycle_id=1)
        task = next(t for s in result.values() for t in s if t["id"] == tid)
        self.assertEqual(task["form_data"]["niche"], "bất động sản")
        self.assertEqual(task["form_data"]["budget"], 5000000)


class TestCustomTask(unittest.TestCase):
    def test_create_custom_task(self):
        conn = _setup_conn()
        tid = create_custom_task(
            conn, lifecycle_id=1, stage="deliver", title="Task tuỳ chỉnh"
        )
        self.assertIsInstance(tid, int)
        row = conn.execute(
            "SELECT * FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
        self.assertEqual(row["is_custom"], 1)
        self.assertEqual(row["title"], "Task tuỳ chỉnh")
        self.assertEqual(row["stage"], "deliver")

    def test_delete_custom_task(self):
        conn = _setup_conn()
        tid = create_custom_task(
            conn, lifecycle_id=1, stage="deliver", title="Task xoá"
        )
        ok = delete_task(conn, tid)
        self.assertTrue(ok)
        self.assertIsNone(
            conn.execute(
                "SELECT id FROM crm_svc_tasks WHERE id = ?", (tid,)
            ).fetchone()
        )

    def test_cannot_delete_template_task(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        tid = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE is_custom = 0 LIMIT 1"
        ).fetchone()["id"]
        ok = delete_task(conn, tid)
        self.assertFalse(ok)

    def test_delete_nonexistent_returns_false(self):
        conn = _setup_conn()
        ok = delete_task(conn, 99999)
        self.assertFalse(ok)


class TestGetProgress(unittest.TestCase):
    def test_returns_all_stages(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        progress = get_progress(conn, lifecycle_id=1)
        from crm_service_lifecycle import VALID_STAGES
        for stage in VALID_STAGES:
            self.assertIn(stage, progress)

    def test_lead_stage_has_tasks(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        progress = get_progress(conn, lifecycle_id=1)
        self.assertGreater(progress["lead"]["total"], 0)
        self.assertEqual(progress["lead"]["done"], 0)
        self.assertEqual(progress["lead"]["pct"], 0)

    def test_pct_100_when_all_done(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        tasks = list_tasks(conn, lifecycle_id=1)
        for t in tasks.get("lead", []):
            update_task(conn, t["id"], is_done=True)
        progress = get_progress(conn, lifecycle_id=1)
        self.assertEqual(progress["lead"]["pct"], 100)


class TestServiceLabels(unittest.TestCase):
    def test_all_12_slugs_in_labels(self):
        from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS
        for slug in SERVICE_WORKFLOW_STEPS:
            self.assertIn(slug, SERVICE_LABELS, f"Missing label for {slug}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy tests — expect FAIL**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python -m pytest tests/test_crm_svc_tasks.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'crm_svc_tasks'`

- [ ] **Step 3: Implement crm_svc_tasks.py**

```python
# crm_svc_tasks.py
"""Workflow tasks per-customer cho 12 dịch vụ PTTP."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"

SERVICE_LABELS: dict[str, str] = {
    "dich-vu-aeo": "Dịch vụ AEO",
    "dich-vu-seo-tong-the": "SEO Tổng thể",
    "dich-vu-seo-local": "SEO Local",
    "dich-vu-seo-audit": "SEO Audit",
    "dich-vu-quan-tri-website": "Quản trị Website",
    "thiet-ke-website": "Thiết kế Website",
    "thiet-ke-website-tron-goi": "Website Trọn gói",
    "thiet-ke-landing-page": "Landing Page",
    "quang-cao-facebook": "Quảng cáo Facebook",
    "quang-cao-google": "Quảng cáo Google",
    "thue-tai-khoan-quang-cao": "Thuê Tài khoản Ads",
    "tiep-thi-noi-dung": "Tiếp thị Nội dung",
}


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_tasks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id  INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            stage         TEXT NOT NULL DEFAULT '',
            step_index    INTEGER NOT NULL DEFAULT 0,
            title         TEXT NOT NULL DEFAULT '',
            description   TEXT NOT NULL DEFAULT '',
            form_fields   TEXT NOT NULL DEFAULT '[]',
            form_data     TEXT NOT NULL DEFAULT '{}',
            ai_output     TEXT NOT NULL DEFAULT '',
            ai_prompt_key TEXT NOT NULL DEFAULT '',
            is_done       INTEGER NOT NULL DEFAULT 0,
            done_at       TEXT NOT NULL DEFAULT '',
            done_by       INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            notes         TEXT NOT NULL DEFAULT '',
            is_custom     INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT '',
            updated_at    TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_tasks_lifecycle "
        "ON crm_svc_tasks(lifecycle_id, stage)"
    )
    conn.commit()


def seed_tasks(
    conn: sqlite3.Connection, lifecycle_id: int, service_slug: str
) -> int:
    from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS
    existing = conn.execute(
        "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = ? AND is_custom = 0",
        (lifecycle_id,),
    ).fetchone()[0]
    if existing > 0:
        return 0
    steps = SERVICE_WORKFLOW_STEPS.get(service_slug, {})
    ts = _ts()
    count = 0
    for stage, stage_steps in steps.items():
        for idx, step in enumerate(stage_steps):
            conn.execute(
                """
                INSERT INTO crm_svc_tasks
                    (lifecycle_id, stage, step_index, title, description,
                     ai_prompt_key, form_fields, form_data, is_done, is_custom,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 0, 0, ?, ?)
                """,
                (
                    lifecycle_id, stage, idx,
                    step["title"], step.get("description", ""),
                    step.get("ai_prompt_key", ""),
                    json.dumps(step.get("form_fields", []), ensure_ascii=False),
                    ts, ts,
                ),
            )
            count += 1
    conn.commit()
    return count


def list_tasks(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT * FROM crm_svc_tasks
        WHERE lifecycle_id = ?
        ORDER BY stage, step_index, id
        """,
        (lifecycle_id,),
    ).fetchall()
    result: dict[str, list[dict]] = {}
    for row in rows:
        d = dict(row)
        d["form_data"] = json.loads(d.get("form_data") or "{}")
        d["form_fields"] = json.loads(d.get("form_fields") or "[]")
        stage = d["stage"]
        result.setdefault(stage, []).append(d)
    return result


def update_task(
    conn: sqlite3.Connection,
    task_id: int,
    *,
    is_done: bool | None = None,
    notes: str | None = None,
    form_data: dict | None = None,
    done_by: int | None = None,
) -> None:
    ts = _ts()
    sets = ["updated_at = ?"]
    params: list[Any] = [ts]
    if is_done is not None:
        sets.append("is_done = ?")
        params.append(1 if is_done else 0)
        if is_done:
            sets.append("done_at = ?")
            params.append(ts)
        else:
            sets.append("done_at = ''")
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes[:4000])
    if form_data is not None:
        sets.append("form_data = ?")
        params.append(json.dumps(form_data, ensure_ascii=False))
    if done_by is not None:
        sets.append("done_by = ?")
        params.append(done_by)
    params.append(task_id)
    conn.execute(
        f"UPDATE crm_svc_tasks SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()


def create_custom_task(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    stage: str,
    title: str,
    description: str = "",
) -> int:
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_svc_tasks
            (lifecycle_id, stage, step_index, title, description, form_fields,
             form_data, is_done, is_custom, created_at, updated_at)
        VALUES (?, ?, 999, ?, ?, '[]', '{}', 0, 1, ?, ?)
        """,
        (lifecycle_id, stage, title[:500], description[:2000], ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def delete_task(conn: sqlite3.Connection, task_id: int) -> bool:
    row = conn.execute(
        "SELECT is_custom FROM crm_svc_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if row is None or not row["is_custom"]:
        return False
    conn.execute("DELETE FROM crm_svc_tasks WHERE id = ?", (task_id,))
    conn.commit()
    return True


def run_ai_assist(
    conn: sqlite3.Connection,
    task_id: int,
    customer_context: dict,
) -> str:
    from crm_svc_workflow_steps import AI_PROMPT_TEMPLATES
    task = conn.execute(
        "SELECT * FROM crm_svc_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if task is None:
        return ""
    template = AI_PROMPT_TEMPLATES.get(task["ai_prompt_key"], "")
    if not template:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    try:
        import anthropic
        ctx = {k: customer_context.get(k, "") for k in [
            "service_name", "customer_name", "niche", "budget", "need", "goal",
            "current_status", "timeline", "start_date", "report_period",
            "completed_tasks", "metrics", "kpi_target", "kpi_actual",
            "months_active", "kpi_summary",
        ]}
        prompt = template.format(**ctx)
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        output = response.content[0].text.strip()
        conn.execute(
            "UPDATE crm_svc_tasks SET ai_output = ?, updated_at = ? WHERE id = ?",
            (output, _ts(), task_id),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_assist lỗi task_id=%s: %s", task_id, exc)
        return ""


def get_progress(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, dict[str, Any]]:
    from crm_service_lifecycle import VALID_STAGES
    rows = conn.execute(
        """
        SELECT stage, COUNT(*) as total, SUM(is_done) as done
        FROM crm_svc_tasks
        WHERE lifecycle_id = ?
        GROUP BY stage
        """,
        (lifecycle_id,),
    ).fetchall()
    result: dict[str, dict] = {
        s: {"total": 0, "done": 0, "pct": 0} for s in VALID_STAGES
    }
    for row in rows:
        total = row["total"]
        done = row["done"] or 0
        pct = int(done / total * 100) if total > 0 else 0
        result[row["stage"]] = {"total": total, "done": done, "pct": pct}
    return result
```

- [ ] **Step 4: Chạy tests — expect PASS**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python -m pytest tests/test_crm_svc_tasks.py -v
```

Expected: All tests PASS. Nếu fail → fix trước khi tiếp tục.

- [ ] **Step 5: Commit**

```bash
git add crm_svc_tasks.py tests/test_crm_svc_tasks.py
git commit -m "feat: add crm_svc_tasks module + 17 tests (TDD)"
```

---

### Task 3: Wire app.py — init schema + 5 routes

**Files:**
- Modify: `app.py` — thêm import, init schema, 5 routes sau `crm_service_delivery_page`

**Interfaces:**
- Consumes: `crm_svc_tasks.ensure_schema`, `seed_tasks`, `list_tasks`, `update_task`, `create_custom_task`, `delete_task`, `run_ai_assist`, `get_progress`, `SERVICE_LABELS`
- Consumes: `crm_svc_workflow_steps.SERVICE_WORKFLOW_STEPS`
- Consumes: existing `_ensure_admin_session_html`, `_admin_page_template_kwargs`, `get_connection`, `_opt_pos_int`, `SVC_LIFECYCLE_STAGES`, `render_template`, `jsonify`, `request`

- [ ] **Step 1: Thêm import và init schema vào app.py**

Tìm block import crm_service_lifecycle ở đầu app.py (khoảng dòng 325):

```python
# Tìm dòng này:
from crm_service_lifecycle import (
```

Thêm sau block import crm_service_lifecycle (sau dòng `VALID_SLUGS as SVC_LIFECYCLE_SLUGS,`):

```python
from crm_svc_tasks import ensure_schema as _ensure_svc_tasks_schema
```

Tìm hàm `_ensure_service_lifecycle_schema` trong init (khoảng dòng init_db) và thêm call đến schema mới. Tìm pattern `_ensure_service_lifecycle_schema(conn)` trong init và thêm ngay sau:

```python
        _ensure_svc_tasks_schema(conn)
```

- [ ] **Step 2: Verify app import OK**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Thêm 5 routes vào app.py — sau hàm `crm_service_delivery_page` (sau dòng 16800)**

```python
# ── Service Workflow Detail ─────────────────────────────────────────────────

@app.get("/crm/service-delivery/<int:lifecycle_id>")
def crm_service_workflow_page(lifecycle_id: int) -> Any:
    redir = _ensure_admin_session_html()
    if redir is not None:
        return redir
    from crm_svc_tasks import (
        SERVICE_LABELS as _svc_labels,
        get_progress as _svc_progress,
        list_tasks as _svc_list_tasks,
        seed_tasks as _svc_seed,
    )
    from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS as _svc_steps
    with get_connection() as conn:
        lc = conn.execute(
            "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
        ).fetchone()
        if lc is None:
            return "Không tìm thấy lifecycle", 404
        lc = dict(lc)
        _svc_seed(conn, lifecycle_id=lifecycle_id, service_slug=lc["service_slug"])
        tasks_by_stage = _svc_list_tasks(conn, lifecycle_id=lifecycle_id)
        progress = _svc_progress(conn, lifecycle_id=lifecycle_id)
        customer = None
        if lc.get("customer_id"):
            row = conn.execute(
                "SELECT * FROM crm_customers WHERE id = ?", (lc["customer_id"],)
            ).fetchone()
            customer = dict(row) if row else None
    return render_template(
        "crm_service_workflow.html",
        lifecycle=lc,
        tasks_by_stage=tasks_by_stage,
        progress=progress,
        stages=SVC_LIFECYCLE_STAGES,
        customer=customer,
        service_label=_svc_labels.get(lc["service_slug"], lc["service_slug"]),
        service_steps=_svc_steps.get(lc["service_slug"], {}),
        stage_labels={
            "lead": "Lead", "consult": "Tư vấn", "proposal": "Báo giá",
            "onboard": "Onboarding", "deliver": "Triển khai",
            "handover": "Nghiệm thu", "retain": "Chăm sóc",
        },
        **_admin_page_template_kwargs(),
    )


@app.patch("/api/crm/svc-tasks/<int:task_id>")
def api_svc_task_patch(task_id: int) -> Any:
    from crm_svc_tasks import update_task as _svc_update
    payload = request.get_json(force=True) or {}
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Không tìm thấy task"}), 404
        is_done = payload.get("is_done")
        notes = payload.get("notes")
        form_data = payload.get("form_data")
        done_by = _opt_pos_int(payload.get("done_by"))
        _svc_update(
            conn, task_id,
            is_done=bool(is_done) if is_done is not None else None,
            notes=str(notes)[:4000] if notes is not None else None,
            form_data=form_data if isinstance(form_data, dict) else None,
            done_by=done_by,
        )
        updated = conn.execute(
            "SELECT * FROM crm_svc_tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(dict(updated))


@app.post("/api/crm/svc-tasks")
def api_svc_task_create() -> Any:
    from crm_svc_tasks import create_custom_task as _svc_create
    payload = request.get_json(force=True) or {}
    lifecycle_id = _opt_pos_int(payload.get("lifecycle_id"))
    stage = str(payload.get("stage", "")).strip()
    title = str(payload.get("title", "")).strip()[:500]
    description = str(payload.get("description", "")).strip()[:2000]
    if not lifecycle_id or not stage or not title:
        return jsonify({"error": "Cần lifecycle_id, stage và title"}), 400
    with get_connection() as conn:
        tid = _svc_create(
            conn, lifecycle_id=lifecycle_id,
            stage=stage, title=title, description=description,
        )
        row = conn.execute(
            "SELECT * FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
    return jsonify(dict(row)), 201


@app.delete("/api/crm/svc-tasks/<int:task_id>")
def api_svc_task_delete(task_id: int) -> Any:
    from crm_svc_tasks import delete_task as _svc_delete
    with get_connection() as conn:
        ok = _svc_delete(conn, task_id)
    if not ok:
        return jsonify({"error": "Không thể xoá — không phải custom task"}), 404
    return jsonify({"ok": True})


@app.post("/api/crm/svc-tasks/<int:task_id>/ai-assist")
def api_svc_task_ai_assist(task_id: int) -> Any:
    from crm_svc_tasks import SERVICE_LABELS as _svc_lbl, run_ai_assist as _svc_ai
    payload = request.get_json(force=True) or {}
    ctx: dict = payload.get("context") or {}
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT t.*, lc.service_slug, lc.customer_id
            FROM crm_svc_tasks t
            JOIN crm_service_lifecycle lc ON lc.id = t.lifecycle_id
            WHERE t.id = ?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": "Không tìm thấy task"}), 404
        if row["customer_id"]:
            cust = conn.execute(
                "SELECT name FROM crm_customers WHERE id = ?",
                (row["customer_id"],),
            ).fetchone()
            if cust:
                ctx.setdefault("customer_name", cust["name"] or "KH")
        ctx.setdefault(
            "service_name", _svc_lbl.get(row["service_slug"], row["service_slug"])
        )
        output = _svc_ai(conn, task_id=task_id, customer_context=ctx)
    return jsonify({"ai_output": output, "task_id": task_id})
```

- [ ] **Step 4: Verify app import OK + test run**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python -c "import app; print('OK')"
python -m pytest tests/test_crm_svc_tasks.py -v --tb=short
```

Expected: import OK, tất cả tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: wire crm_svc_tasks into app.py — init schema + 5 routes"
```

---

### Task 4: Template crm_service_workflow.html

**Files:**
- Create: `templates/crm_service_workflow.html`

**Interfaces:**
- Consumes từ route: `lifecycle`, `tasks_by_stage`, `progress`, `stages`, `customer`, `service_label`, `service_steps`, `stage_labels`
- JS: fetch `PATCH /api/crm/svc-tasks/<id>` để tick done / save form / notes
- JS: fetch `POST /api/crm/svc-tasks` để tạo custom task
- JS: fetch `DELETE /api/crm/svc-tasks/<id>` để xoá custom task
- JS: fetch `POST /api/crm/svc-tasks/<id>/ai-assist` để AI generate

- [ ] **Step 1: Tạo template**

```html
{% extends "admin_layout.html" %}

{% block title %}{{ service_label }} — Workflow — CRM{% endblock %}
{% block meta_robots %}noindex, nofollow{% endblock %}
{% block body_class_extra %}crm-body crm-svc-workflow-page{% endblock %}

{% block admin_page_title %}{{ service_label }}{% endblock %}
{% block admin_page_desc %}
  <p class="admin-page-desc">
    KH: <strong>{{ customer.name if customer else '#' ~ lifecycle.customer_id }}</strong>
    &nbsp;·&nbsp; Stage hiện tại:
    <span style="background:#6366f1;color:#fff;padding:2px 8px;border-radius:4px;font-size:.75rem;">
      {{ stage_labels.get(lifecycle.stage, lifecycle.stage) }}
    </span>
    &nbsp;·&nbsp;
    <a href="{{ url_for('crm_service_delivery_page') }}"
       style="font-size:.8rem;color:#6366f1;">← Về kanban</a>
  </p>
{% endblock %}

{% block admin_main %}
{% set total_tasks = progress.values() | sum(attribute='total') %}
{% set done_tasks  = progress.values() | sum(attribute='done') %}
{% set total_pct   = ((done_tasks / total_tasks * 100) | int) if total_tasks > 0 else 0 %}

{# Overall progress bar #}
<div style="margin-bottom:1.5rem;">
  <div style="display:flex;justify-content:space-between;font-size:.8rem;color:#555;margin-bottom:4px;">
    <span>Tiến độ tổng: {{ done_tasks }}/{{ total_tasks }} tasks</span>
    <span>{{ total_pct }}%</span>
  </div>
  <div style="height:8px;background:#e5e7eb;border-radius:4px;overflow:hidden;">
    <div style="height:100%;background:#6366f1;width:{{ total_pct }}%;transition:width .3s;"></div>
  </div>
</div>

{# Stage tabs #}
<div style="display:flex;gap:4px;margin-bottom:1rem;flex-wrap:wrap;">
  {% for stage in stages %}
  {% set prog = progress.get(stage, {}) %}
  <button class="svc-tab-btn"
          data-stage="{{ stage }}"
          onclick="svcShowTab('{{ stage }}')"
          style="padding:.375rem .75rem;border-radius:6px;border:1px solid #e2e8f0;
                 background:{% if stage == lifecycle.stage %}#6366f1{% else %}#fff{% endif %};
                 color:{% if stage == lifecycle.stage %}#fff{% else %}#444{% endif %};
                 font-size:.8rem;cursor:pointer;">
    {{ stage_labels.get(stage, stage) }}
    {% if prog.total > 0 %}
    <span style="font-size:.7rem;opacity:.8;">{{ prog.done }}/{{ prog.total }}</span>
    {% endif %}
  </button>
  {% endfor %}
</div>

{# Tab panes #}
{% for stage in stages %}
<div id="svc-tab-{{ stage }}"
     style="display:{% if stage == lifecycle.stage %}block{% else %}none{% endif %};">

  {% set stage_tasks = tasks_by_stage.get(stage, []) %}
  {% if not stage_tasks %}
  <p style="color:#aaa;font-size:.85rem;padding:1rem 0;">Chưa có tasks — seed tự động khi mở trang.</p>
  {% endif %}

  {% for task in stage_tasks %}
  <div id="task-card-{{ task.id }}"
       style="background:#fff;border:1px solid {% if task.is_done %}#bbf7d0{% else %}#e2e8f0{% endif %};
              border-radius:8px;padding:1rem;margin-bottom:.75rem;
              {% if task.is_done %}opacity:.7;{% endif %}">

    {# Header #}
    <div style="display:flex;align-items:flex-start;gap:.75rem;margin-bottom:.5rem;">
      <input type="checkbox" {% if task.is_done %}checked{% endif %}
             onchange="svcToggleDone({{ task.id }}, this.checked)"
             style="margin-top:3px;cursor:pointer;width:16px;height:16px;">
      <div style="flex:1;">
        <div style="font-weight:600;font-size:.9rem;
                    {% if task.is_done %}text-decoration:line-through;color:#888;{% endif %}">
          {{ task.title }}
          {% if task.is_custom %}
          <span style="font-size:.65rem;background:#fef3c7;color:#92400e;
                       padding:1px 6px;border-radius:4px;margin-left:.25rem;">tuỳ chỉnh</span>
          {% endif %}
        </div>
        {% if task.description %}
        <div style="font-size:.78rem;color:#666;margin-top:2px;">{{ task.description }}</div>
        {% endif %}
      </div>
      {% if task.is_custom %}
      <button onclick="svcDeleteTask({{ task.id }})"
              title="Xoá task"
              style="background:none;border:none;cursor:pointer;color:#f87171;font-size:.8rem;padding:2px 6px;">✕</button>
      {% endif %}
    </div>

    {# Form fields #}
    {% if task.form_fields %}
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.5rem;
                margin:.75rem 0;padding:.75rem;background:#f8fafc;border-radius:6px;">
      {% for field in task.form_fields %}
      <label style="font-size:.75rem;color:#555;">
        {{ field.label }}
        {% if field.type == 'textarea' %}
        <textarea rows="2"
                  data-task-id="{{ task.id }}" data-field-key="{{ field.key }}"
                  onchange="svcSaveFormField({{ task.id }}, '{{ field.key }}', this.value)"
                  style="width:100%;margin-top:2px;padding:4px;border:1px solid #ddd;
                         border-radius:4px;font-size:.78rem;box-sizing:border-box;resize:vertical;"
        >{{ task.form_data.get(field.key, '') }}</textarea>
        {% else %}
        <input type="{{ field.type }}"
               data-task-id="{{ task.id }}" data-field-key="{{ field.key }}"
               value="{{ task.form_data.get(field.key, '') }}"
               onchange="svcSaveFormField({{ task.id }}, '{{ field.key }}', this.value)"
               style="width:100%;margin-top:2px;padding:4px;border:1px solid #ddd;
                      border-radius:4px;font-size:.78rem;box-sizing:border-box;">
        {% endif %}
      </label>
      {% endfor %}
    </div>
    {% endif %}

    {# Notes #}
    <div style="margin:.5rem 0;">
      <label style="font-size:.75rem;color:#555;display:block;">Ghi chú AM</label>
      <textarea rows="2"
                onchange="svcSaveNotes({{ task.id }}, this.value)"
                style="width:100%;margin-top:2px;padding:4px;border:1px solid #ddd;
                       border-radius:4px;font-size:.78rem;box-sizing:border-box;resize:vertical;"
      >{{ task.notes }}</textarea>
    </div>

    {# AI Output #}
    {% if task.ai_output %}
    <div id="ai-output-{{ task.id }}"
         style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;
                padding:.75rem;margin:.5rem 0;font-size:.8rem;white-space:pre-wrap;">{{ task.ai_output }}</div>
    {% else %}
    <div id="ai-output-{{ task.id }}" style="display:none;background:#f0fdf4;border:1px solid #bbf7d0;
         border-radius:6px;padding:.75rem;margin:.5rem 0;font-size:.8rem;white-space:pre-wrap;"></div>
    {% endif %}

    {# Actions #}
    <div style="display:flex;gap:.5rem;margin-top:.5rem;">
      {% if task.ai_prompt_key %}
      <button onclick="svcAiAssist({{ task.id }}, '{{ stage }}')"
              id="ai-btn-{{ task.id }}"
              style="padding:.3rem .7rem;background:#6366f1;color:#fff;border:none;
                     border-radius:6px;font-size:.78rem;cursor:pointer;">
        AI Hỗ trợ
      </button>
      {% endif %}
      <span id="ai-status-{{ task.id }}" style="font-size:.75rem;color:#888;align-self:center;"></span>
    </div>
  </div>
  {% endfor %}

  {# Add custom task #}
  <div style="margin-top:.75rem;">
    <details>
      <summary style="font-size:.8rem;color:#6366f1;cursor:pointer;user-select:none;">
        + Thêm task tuỳ chỉnh cho stage này
      </summary>
      <div style="display:flex;gap:.5rem;margin-top:.5rem;">
        <input type="text" id="custom-title-{{ stage }}"
               placeholder="Tên task..."
               style="flex:1;padding:.375rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
        <button onclick="svcAddCustomTask('{{ stage }}')"
                style="padding:.375rem .75rem;background:#22c55e;color:#fff;border:none;
                       border-radius:6px;font-size:.8rem;cursor:pointer;">Thêm</button>
      </div>
    </details>
  </div>
</div>
{% endfor %}

<script>
const _lifecycleId = {{ lifecycle.id }};

function svcShowTab(stage) {
  document.querySelectorAll('[id^="svc-tab-"]').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.svc-tab-btn').forEach(btn => {
    btn.style.background = '#fff';
    btn.style.color = '#444';
  });
  document.getElementById('svc-tab-' + stage).style.display = 'block';
  const btn = document.querySelector('[data-stage="' + stage + '"]');
  if (btn) { btn.style.background = '#6366f1'; btn.style.color = '#fff'; }
}

function svcToggleDone(taskId, isDone) {
  fetch('/api/crm/svc-tasks/' + taskId, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({is_done: isDone}),
  }).then(r => r.json()).then(() => {
    const card = document.getElementById('task-card-' + taskId);
    if (!card) return;
    card.style.borderColor = isDone ? '#bbf7d0' : '#e2e8f0';
    card.style.opacity = isDone ? '0.7' : '1';
  }).catch(console.error);
}

const _formDataCache = {};
function svcSaveFormField(taskId, key, value) {
  if (!_formDataCache[taskId]) _formDataCache[taskId] = {};
  _formDataCache[taskId][key] = value;
  clearTimeout(_formDataCache['_t_' + taskId]);
  _formDataCache['_t_' + taskId] = setTimeout(() => {
    fetch('/api/crm/svc-tasks/' + taskId, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({form_data: _formDataCache[taskId]}),
    }).catch(console.error);
  }, 800);
}

function svcSaveNotes(taskId, notes) {
  clearTimeout(window['_nt_' + taskId]);
  window['_nt_' + taskId] = setTimeout(() => {
    fetch('/api/crm/svc-tasks/' + taskId, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({notes}),
    }).catch(console.error);
  }, 800);
}

function svcAiAssist(taskId, stage) {
  const btn = document.getElementById('ai-btn-' + taskId);
  const status = document.getElementById('ai-status-' + taskId);
  if (btn) btn.disabled = true;
  if (status) status.textContent = 'Đang tạo...';
  const ctx = {};
  document.querySelectorAll('[data-task-id="' + taskId + '"]').forEach(el => {
    ctx[el.dataset.fieldKey] = el.value;
  });
  fetch('/api/crm/svc-tasks/' + taskId + '/ai-assist', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({context: ctx}),
  }).then(r => r.json()).then(data => {
    const out = document.getElementById('ai-output-' + taskId);
    if (out) { out.textContent = data.ai_output || '(AI không có phản hồi)'; out.style.display = 'block'; }
    if (status) status.textContent = '';
    if (btn) btn.disabled = false;
  }).catch(err => {
    if (status) status.textContent = 'Lỗi: ' + err;
    if (btn) btn.disabled = false;
  });
}

function svcAddCustomTask(stage) {
  const input = document.getElementById('custom-title-' + stage);
  const title = (input ? input.value : '').trim();
  if (!title) return;
  fetch('/api/crm/svc-tasks', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({lifecycle_id: _lifecycleId, stage, title}),
  }).then(r => r.json()).then(() => location.reload())
    .catch(console.error);
}

function svcDeleteTask(taskId) {
  if (!confirm('Xoá task này?')) return;
  fetch('/api/crm/svc-tasks/' + taskId, {method: 'DELETE'})
    .then(() => location.reload())
    .catch(console.error);
}
</script>
{% endblock %}
```

- [ ] **Step 2: Verify template render**

Với Flask server đang chạy trên port 5050, mở browser hoặc dùng curl:

```bash
curl -s -o /dev/null -w "%{http_code}" "http://localhost:5050/crm/service-delivery/1"
```

Expected: `200` (hoặc `302` nếu chưa login — đăng nhập trước)

- [ ] **Step 3: Commit**

```bash
git add templates/crm_service_workflow.html
git commit -m "feat: add crm_service_workflow.html — 7-stage workflow detail page"
```

---

### Task 5: Update kanban card — link đến workflow page

**Files:**
- Modify: `templates/crm_service_delivery.html` — dòng 48, đổi `onclick="svcOpenCard({{ lc.id }})"` thành link navigate

**Interfaces:**
- Consumes: `url_for('crm_service_workflow_page', lifecycle_id=lc.id)`
- Modal advance stage vẫn giữ nguyên — chỉ đổi card click behavior

- [ ] **Step 1: Sửa card onclick trong crm_service_delivery.html**

Tìm dòng (khoảng dòng 44–48):

```html
      <div class="svc-card" data-id="{{ lc.id }}"
           style="background:#fff; border-radius:6px; padding:.625rem; margin-bottom:.5rem;
                  border:1px solid #e2e8f0; cursor:pointer;"
           onclick="svcOpenCard({{ lc.id }})">
```

Thay bằng:

```html
      <div class="svc-card" data-id="{{ lc.id }}"
           style="background:#fff; border-radius:6px; padding:.625rem; margin-bottom:.5rem;
                  border:1px solid #e2e8f0; cursor:pointer;"
           onclick="location.href='{{ url_for('crm_service_workflow_page', lifecycle_id=lc.id) }}'">
```

- [ ] **Step 2: Verify kanban renders OK**

```bash
curl -s "http://localhost:5050/crm/service-delivery" | grep "crm_service_workflow_page" | head -3
```

Expected: thấy URL `/crm/service-delivery/1` (hoặc tương tự) trong HTML.

- [ ] **Step 3: Test navigation thủ công**

Đăng nhập → vào `/crm/service-delivery` → click card → mở trang workflow đúng lifecycle.

- [ ] **Step 4: Commit**

```bash
git add templates/crm_service_delivery.html
git commit -m "feat: kanban card click navigates to workflow detail page"
```

---

## Self-Review

**Spec coverage:**
- [x] 12 services × 7 stages × steps → Task 1
- [x] schema `crm_svc_tasks` với `form_fields` column → Task 2
- [x] 7 public functions: ensure_schema, seed_tasks, list_tasks, update_task, create_custom_task, delete_task, run_ai_assist, get_progress → Task 2
- [x] TDD: tests viết trước, implementation sau → Task 2
- [x] AI model `claude-haiku-4-5-20251001`, synchronous, fail silent → Task 2
- [x] 5 routes trong app.py → Task 3
- [x] Template 7-stage tabs + form + AI assist + tick done → Task 4
- [x] Kanban card click → navigate to detail → Task 5
- [x] `seed_tasks` idempotent → Task 2 (kiểm tra `is_custom=0` count)
- [x] `delete_task` chỉ xoá `is_custom=1` → Task 2

**Type consistency:**
- `seed_tasks` → `int` (đã nhất quán trong tests và implementation)
- `delete_task` → `bool` (đã nhất quán)
- `list_tasks` → `dict[str, list[dict]]` (form_data và form_fields là Python objects sau json.loads)
- `get_progress` → `dict[str, dict]` với keys `total`, `done`, `pct`
- Route function name: `crm_service_workflow_page` (dùng trong url_for tại Task 5)

**Không có placeholder hay TBD nào.**
