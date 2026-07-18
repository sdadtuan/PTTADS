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
        "KH: {customer_name}, ngành: {niche}. Tình trạng hiện tại: {current_status}.\n\n"
        "BANT Intake: {bant_total}/30 · Quyết định: {decision}\n"
        "Red flags: {red_flags}\n"
        "Lead qualify (JSON): {lead_form_json}\n"
        "Tóm tắt Intake:\n{intake_summary}\n\n"
        "Brief readiness:\n{consult_brief_json}\n\n"
        "Viết phân tích 250 từ: tình trạng hiện tại, cơ hội tăng trưởng, "
        "thách thức, hướng tiếp cận đề xuất — bám sát dữ liệu Intake/BANT ở trên."
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
    "intake_summary": (
        "Bạn là AM PTT agency digital marketing.\n"
        "Tóm tắt buổi {mode_label} dịch vụ {service_name} cho khách {contact_name} "
        "({company_name}).\n\n"
        "BANT {bant_total}/30: {bant_json}\n"
        "Nhiệt độ: {lead_temperature} · Quyết định: {decision}\n"
        "Lý do quyết định: {decision_reason}\n"
        "Red flags đã tick: {red_flags}\n"
        "Urgency triggers: {urgency}\n"
        "Ghi chú buổi:\n{answers_excerpt}\n\n"
        "Trả về JSON hợp lệ (không markdown):\n"
        '{{"summary": "<2-4 câu tóm tắt cho AM/Director>", '
        '"risks": ["<rủi ro 1>", "..."], '
        '"missing_questions": ["<câu cần hỏi thêm 1>", "..."], '
        '"recommended_next_step": "<hành động cụ thể tiếp theo>"}}'
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
