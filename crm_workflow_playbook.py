"""Quy trình quản lý CRM 6 trụ + hướng dẫn áp dụng khi lead marketing đổ về."""
from __future__ import annotations

from typing import Any

# --- Luồng chuẩn khi có lead mới từ bất kỳ kênh marketing nào ---
CRM_LEAD_INTAKE_MASTER_FLOW: list[dict[str, Any]] = [
    {
        "phase": "T+0 (0–15 phút)",
        "pillar_num": 1,
        "title": "Tiếp nhận & ghi vào CRM",
        "actions": [
            "Xác nhận lead đã có case trên Bảng CSKH — nếu chưa: tạo case ngay, không để trong Excel/chat riêng.",
            "Ghi đúng kênh (`channel`), chiến dịch/UTM (nếu có), nguồn marketing (form/ads/MXH…).",
            "Kiểm tra trùng SĐT/email — nếu khách cũ: mở case mới nhưng link ghi chú lịch sử mua.",
            "Gán `Phụ trách` (assigned_staff_id) theo round-robin hoặc ca trực.",
        ],
        "crm_where": "Bảng CSKH → Thêm yêu cầu / card mới",
        "sla": "≤15 phút (lead hot) · ≤4h (lead thường)",
    },
    {
        "phase": "T+0 (15–30 phút)",
        "pillar_num": 2,
        "title": "Phân loại & chấm điểm",
        "actions": [
            "Đánh giá ICP: đúng persona → priority **Cao**; ngoài vùng → **Thấp** + tag nurture.",
            "Chấm điểm nhanh: +2 hỏi giá/booking, +1 điền đủ form, −2 SĐT sai/spam.",
            "Kéo card Kanban: **Mới** → **Đang liên hệ** khi bắt đầu gọi/nhắn.",
        ],
        "crm_where": "Card case → Priority + cột trạng thái",
        "sla": "Trước cuộc gọi đầu tiên",
    },
    {
        "phase": "T+0 → T+1 ngày",
        "pillar_num": 3,
        "title": "Liên hệ & nuôi dưỡng lần 1",
        "actions": [
            "Gọi/nhắn theo script kênh (xem chi tiết từng kênh bên dưới).",
            "Ghi timeline: kết quả cuộc gọi, nhu cầu, ngân sách, timeline mua.",
            "Không liên hệ được → đặt reminder + gửi email/Zalo mẫu D0; lên lịch gọi lại T+1.",
        ],
        "crm_where": "Timeline case + Nhắc việc",
        "sla": "≥3 touch trong 72h (gọi + email/Zalo)",
    },
    {
        "phase": "T+1 → T+3 ngày",
        "pillar_num": 2,
        "title": "Qualify MQL → SQL",
        "actions": [
            "Xác nhận nhu cầu rõ, có ngân sách/timeline → chuyển **MQL**.",
            "Hẹn demo/site visit/meeting → chuyển **SQL**; ghi lịch hẹn + reminder.",
            "Chưa đủ điều kiện → nurture D3/D7, giữ priority Thấp/ Bình thường.",
        ],
        "crm_where": "Kanban + mô tả case",
        "sla": "Qualify trong 3 ngày làm việc",
    },
    {
        "phase": "T+3 → T+14 ngày",
        "pillar_num": 4,
        "title": "Pipeline & chốt",
        "actions": [
            "Gửi báo giá/proposal — ghi version + ngày hết hạn trên mô tả/timeline.",
            "Theo dõi thương lượng; cập nhật giá trị deal ước tính.",
            "Chốt → tạo hợp đồng Hub CRM trong 24h; đóng case hoặc chuyển trạng thái **Đã đóng**.",
        ],
        "crm_where": "Hub Marketing & hợp đồng + Kanban",
        "sla": "Báo giá ≤48h sau meeting",
    },
    {
        "phase": "Sau chốt",
        "pillar_num": 5,
        "title": "Sau bán & giữ chân",
        "actions": [
            "Kick-off onboarding checklist; chuyển owner sang Account/CSKH nếu khác sales.",
            "Survey CSAT sau milestone; ghi NPS vào case.",
            "Lên lịch review upsell 6 tháng.",
        ],
        "crm_where": "Case + KPI nhân viên",
        "sla": "Onboarding ≤3 ngày làm việc",
    },
    {
        "phase": "Liên tục",
        "pillar_num": 6,
        "title": "Đo lường theo nguồn",
        "actions": [
            "Tag mọi case theo chiến dịch để báo cáo CPL/win rate theo kênh.",
            "Họp T6: lead rác theo nguồn → feedback Marketing điều chỉnh ads/form.",
        ],
        "crm_where": "KPI CRM + export case",
        "sla": "Weekly review",
    },
]

# --- Chi tiết theo kênh marketing đổ về ---
CRM_MARKETING_INGRESS_CHANNELS: tuple[dict[str, Any], ...] = (
    {
        "id": "form_landing",
        "label": "Form web / Landing page",
        "icon": "📝",
        "detect": "Lead từ form website, landing chiến dịch, popup; có UTM trong URL hoặc hidden field.",
        "crm_channel": "khac",
        "crm_channel_label": "Khác (ghi rõ Form web trong mô tả)",
        "sla_contact": "≤15 phút trong giờ hành chính",
        "priority_hint": "Cao nếu điền đủ trường + hỏi giá/booking",
        "intake_fields": [
            "Họ tên, SĐT, email (bắt buộc)",
            "Sản phẩm/dịch vụ quan tâm (dropdown form)",
            "utm_source / utm_campaign / utm_content",
            "Trang landing URL",
            "Thời điểm submit form",
        ],
        "t0_checklist": [
            "Tạo case — tiêu đề: [Form] {Tên} — {Sản phẩm quan tâm}",
            "Dán UTM + URL landing vào mô tả",
            "Kiểm tra trùng SĐT/email trong CRM",
            "Gán phụ trách ca trực",
            "Gọi/Nhắn Zalo trong 15 phút",
        ],
        "pillar_matrix": [
            {"pillar": 1, "action": "Import/sync form → CRM tự động hoặc nhập tay trong 15 phút; không để lead overnight."},
            {"pillar": 2, "action": "Form đủ trường + đúng ICP → priority Cao; form thiếu SĐT → Thấp, email D0 yêu cầu bổ sung."},
            {"pillar": 3, "action": "Email auto xác nhận D0 + gọi xác nhận nhu cầu; nurture D3 case study nếu chưa qualify."},
            {"pillar": 4, "action": "Sau qualify → gửi báo giá PDF + hẹn demo; ghi pipeline trên Kanban."},
            {"pillar": 5, "action": "Khách cũ submit form lại → kiểm tra HĐ cũ, ưu tiên upsell thay vì lead mới."},
            {"pillar": 6, "action": "Đo CVR form → SQL theo từng landing; A/B form với Marketing."},
        ],
        "script_open": (
            "Xin chào anh/chị {Tên}, em là {NV} từ PTT. Em thấy anh/chị vừa đăng ký {Offer} "
            "trên website — em hỗ trợ tư vấn ngắn 3–5 phút được không ạ?"
        ),
        "qualify_questions": [
            "Anh/chị đang quan tâm sản phẩm/dịch vụ nào cụ thể?",
            "Timeline dự kiến triển khai / mua?",
            "Ngân sách dự kiến hoặc quy mô dự án?",
            "Anh/chị là người quyết định hay cần thêm ai tham gia?",
        ],
        "if_no_answer": "Gửi SMS/Zalo + email D0; gọi lại T+1, T+3; sau 3 lần → nurture email tuần.",
        "if_spam": "Đánh dấu priority Thấp, ghi chú spam; loại khỏi báo cáo MQL.",
    },
    {
        "id": "ads_meta_google",
        "label": "Lead quảng cáo (Meta / Google)",
        "icon": "📢",
        "detect": "Lead sync Lead Ads, Instant Form, Google Lead Form; có campaign_id / adset / creative.",
        "crm_channel": "khac",
        "crm_channel_label": "Khác (tag: Ads Meta/Google)",
        "sla_contact": "≤15 phút (lead ads nguội nhanh)",
        "priority_hint": "Cao — ads lead cần phản hồi cực nhanh",
        "intake_fields": [
            "Tên, SĐT, email từ form ads",
            "Campaign / Ad set / Ad name",
            "Chi phí lead (CPL) nếu biết",
            "Creative/offer đang chạy",
            "Platform: Meta / Google / TikTok Lead",
        ],
        "t0_checklist": [
            "Verify lead thật (SĐT VN 10 số, không trùng spam pattern)",
            "Ghi campaign + ad vào mô tả case",
            "So khớp offer trên ad với script gọi",
            "Gọi ngay — không chờ email",
            "Nếu lead form partiale → retarget hoặc gọi bổ sung",
        ],
        "pillar_matrix": [
            {"pillar": 1, "action": "Webhook/Zapier đồ bộ ads → CRM; backup CSV import 2 lần/ngày."},
            {"pillar": 2, "action": "Lead ads thường cold hơn landing — hỏi thêm 2 câu qualify trước khi SQL."},
            {"pillar": 3, "action": "Gọi 3 lần trong 24h (sáng/trưa/chiều); SMS sau mỗi missed call."},
            {"pillar": 4, "action": "Báo giá khớp offer trên ad; không hứa khác creative."},
            {"pillar": 5, "action": "Retarget khách won bằng lookalike — tag nguồn referral ads."},
            {"pillar": 6, "action": "Báo cáo CPL, MQL rate, win rate theo campaign — pause adset CPL cao."},
        ],
        "script_open": (
            "Dạ em gọi từ PTT — anh/chị vừa để lại thông tin qua quảng cáo {Offer} đúng không ạ? "
            "Em tư vấn nhanh phần {Pain} anh/chị quan tâm nhé."
        ),
        "qualify_questions": [
            "Anh/chị thấy quảng cáo trên Facebook/Google đúng không — phần nào anh/chị quan tâm?",
            "Mình đang so sánh thêm đơn vị nào không?",
            "Khi nào cần triển khai?",
        ],
        "if_no_answer": "3 cuộc gọi/24h + Zalo template; day 4 chuyển nurture + loại khỏi hot queue.",
        "if_spam": "Báo Marketing khóa lead form field validation; block SĐT pattern.",
    },
    {
        "id": "hotline",
        "label": "Cuộc gọi đến (Hotline / telesales)",
        "icon": "📞",
        "detect": "Khách gọi số hotline, click-to-call từ web/ads, số trên brochure.",
        "crm_channel": "dien_thoai",
        "crm_channel_label": "Điện thoại",
        "sla_contact": "Ngay khi cúp máy (≤5 phút ghi CRM)",
        "priority_hint": "Cao — khách chủ động gọi intent cao",
        "intake_fields": [
            "SĐT gọi đến (CLI)",
            "Thời lượng cuộc gọi",
            "Nhu cầu chính (ghi ngay khi đang gọi)",
            "Nguồn biết đến (hỏi: anh/chị biết PTT qua đâu?)",
            "Ghi âm/log cuộc gọi (nếu có tổng đài)",
        ],
        "t0_checklist": [
            "Tạo/cập nhật case ngay sau cuộc gọi",
            "Channel = Điện thoại",
            "Ghi summary 3–5 dòng trên timeline",
            "Đặt reminder nếu hẹn gọi lại",
            "Gửi SMS/email xác nhận nếu đã hẹn",
        ],
        "pillar_matrix": [
            {"pillar": 1, "action": "Mọi cuộc gọi có log — không chỉ ghi nhớ cá nhân."},
            {"pillar": 2, "action": "Inbound call = +3 điểm scoring; hỏi giá ngay = hot."},
            {"pillar": 3, "action": "Follow-up đúng hẹn 100%; gửi tài liệu promised trong 2h."},
            {"pillar": 4, "action": "Chuyển SQL khi hẹn demo/site visit có ngày cụ thể."},
            {"pillar": 5, "action": "CSKH inbound khiếu nại → tag P1, SLA 4h."},
            {"pillar": 6, "action": "Đo contact rate, conversion inbound vs outbound."},
        ],
        "script_open": "Xin chào, PTT xin nghe — em hỗ trợ anh/chị ạ?",
        "qualify_questions": [
            "Anh/chị cần hỗ trợ về vấn đề gì ạ?",
            "Anh/chị biết bên em qua kênh nào (web, ads, giới thiệu)?",
            "Khi nào cần giải pháp hoạt động?",
        ],
        "if_no_answer": "Không áp dụng — đã có cuộc gọi; nếu missed call inbound → gọi lại ≤15 phút.",
        "if_spam": "Lưu SĐT spam vào ghi chú team; không tạo case trùng.",
    },
    {
        "id": "email",
        "label": "Email (campaign / inbox)",
        "icon": "✉️",
        "detect": "Reply email marketing, email đến sales@, form contact gửi qua email gateway.",
        "crm_channel": "email",
        "crm_channel_label": "Email",
        "sla_contact": "≤4h làm việc (≤1h nếu tiêu đề urgent/báo giá)",
        "priority_hint": "Cao nếu reply campaign hoặc hỏi báo giá",
        "intake_fields": [
            "Email khách, subject thread",
            "Campaign email nguồn (nếu reply)",
            "Tệp đính kèm",
            "Người được CC",
        ],
        "t0_checklist": [
            "Tạo case — tiêu đề: [Email] {Subject rút gọn}",
            "Channel = Email",
            "Copy nội dung email quan trọng vào timeline",
            "Gán owner mailbox phụ trách",
            "Trả lời email trong SLA — CC team nếu cần",
        ],
        "pillar_matrix": [
            {"pillar": 1, "action": "Link email thread ID vào case; dùng CRM làm nguồn chính."},
            {"pillar": 2, "action": "Reply báo giá/hợp đồng → priority Cao + SQL candidate."},
            {"pillar": 3, "action": "Chuỗi nurture email D0/D3/D7 cho lead im lặng."},
            {"pillar": 4, "action": "Đính kèm proposal vào timeline; track mở email nếu có tool."},
            {"pillar": 5, "action": "Email CSKH sau bán — ticket từ reply vào case cũ."},
            {"pillar": 6, "action": "Open rate, reply rate, SQL từ email campaign."},
        ],
        "script_open": "Kính gửi anh/chị {Tên}, cảm ơn anh/chị đã phản hồi email về {Chủ đề}…",
        "qualify_questions": [
            "Anh/chị cần thêm thông tin cụ thể phần nào?",
            "Có thể sắp xếp call 15 phút để trao đổi chi tiết không?",
        ],
        "if_no_answer": "Gửi follow-up email T+2, T+5; chuyển gọi nếu có SĐT.",
        "if_spam": "Unsubscribe / mark spam; không count MQL.",
    },
    {
        "id": "social",
        "label": "Mạng xã hội (FB / IG / TikTok / Zalo OA)",
        "icon": "💬",
        "detect": "Inbox, comment, DM, Zalo OA message, lead từ social widget.",
        "crm_channel": "zalo",
        "crm_channel_label": "Zalo (hoặc ghi MXH trong mô tả)",
        "sla_contact": "≤30 phút inbox; ≤2h comment công khai",
        "priority_hint": "Cao nếu DM hỏi giá/đặt lịch",
        "intake_fields": [
            "Platform + username/handle",
            "Screenshot/link bài post nguồn",
            "Nội dung tin nhắn",
            "SĐT nếu khách cung cấp qua chat",
        ],
        "t0_checklist": [
            "Trả lời inbox/comment (công khai lịch sự, ngắn gọn)",
            "Chuyển hội thoại sang Zalo/SĐT khi có thể",
            "Tạo case khi có SĐT hoặc intent mua rõ",
            "Ghi platform vào mô tả",
            "Không để hội thoại chỉ nằm trên app MXH",
        ],
        "pillar_matrix": [
            {"pillar": 1, "action": "Export chat quan trọng vào timeline CRM."},
            {"pillar": 2, "action": "Comment hỏi giá = warm; DM số điện thoại = hot."},
            {"pillar": 3, "action": "Template Zalo OA + retarget custom audience từ CRM list."},
            {"pillar": 4, "action": "Gửi catalog/PDF qua Zalo; hẹn call chốt."},
            {"pillar": 5, "action": "Review MXH monitoring — phản hồi review xấu ≤24h."},
            {"pillar": 6, "action": "Lead/inbox → SQL conversion theo platform."},
        ],
        "script_open": "Dạ chào anh/chị, bên em nhận được tin nhắn về {Sản phẩm}. Anh/chị cho em xin SĐT để tư vấn chi tiết ạ?",
        "qualify_questions": [
            "Anh/chị quan tâm gói nào bên em đang post?",
            "Khu vực / quy mô dự án?",
        ],
        "if_no_answer": "Nhắn follow-up 24h/72h; retarget ads nếu có pixel match.",
        "if_spam": "Ẩn/block; không tạo case.",
    },
    {
        "id": "chatbot",
        "label": "Chatbot / Live chat web",
        "icon": "🤖",
        "detect": "Transcript chatbot web, live chat widget, AI assistant chuyển sang người.",
        "crm_channel": "khac",
        "crm_channel_label": "Khác (Chatbot)",
        "sla_contact": "≤15 phút khi chuyển sang agent",
        "priority_hint": "Theo scoring bot (intent = báo giá → Cao)",
        "intake_fields": [
            "Transcript chat đầy đủ",
            "Intent tag từ bot",
            "Trang URL đang chat",
            "SĐT/email thu được",
        ],
        "t0_checklist": [
            "Đọc transcript trước khi gọi — cá nhân hóa mở đầu",
            "Tạo case với paste transcript rút gọn",
            "Tiếp nối đúng ngữ cảnh bot đã hứa",
            "Gọi/Nhắn trong SLA handoff",
        ],
        "pillar_matrix": [
            {"pillar": 1, "action": "API bot → CRM auto-create case khi có SĐT."},
            {"pillar": 2, "action": "Bot score ≥80 → priority Cao + alert Slack/Zalo nội bộ."},
            {"pillar": 3, "action": "Bot nurture FAQ; người takeover khi SQL signal."},
            {"pillar": 4, "action": "Handoff có summary → sales không hỏi lại từ đầu."},
            {"pillar": 5, "action": "Bot CSKH FAQ sau bán; escalate ticket P1."},
            {"pillar": 6, "action": "Bot completion rate, handoff → win rate."},
        ],
        "script_open": "Em là {NV} tiếp nối hỗ trợ từ chatbot — em thấy anh/chị quan tâm {Intent}, em tư vấn thêm nhé?",
        "qualify_questions": ["Phần bot chưa trả lời đủ anh/chị cần là gì?", "Mình có timeline cụ thể không?"],
        "if_no_answer": "Email transcript + CTA đặt lịch; gọi nếu có SĐT.",
        "if_spam": "Bot filter; không handoff.",
    },
    {
        "id": "event_offline",
        "label": "Sự kiện / Offline / QR booth",
        "icon": "🎪",
        "detect": "Lead từ check-in sự kiện, phiếu thu thập, quét QR booth, hội thảo.",
        "crm_channel": "truc_tiep",
        "crm_channel_label": "Trực tiếp",
        "sla_contact": "≤24h sau sự kiện (≤4h nếu hot tại booth)",
        "priority_hint": "Cao nếu gặp trực tiếp và hẹn follow-up",
        "intake_fields": [
            "Tên sự kiện, ngày",
            "Nhân viên booth gặp",
            "Ghi chú tại booth",
            "Ảnh namecard",
        ],
        "t0_checklist": [
            "Nhập hàng loạt từ CSV booth cùng ngày sự kiện",
            "Tag campaign sự kiện trong mô tả",
            "Gọi cảm ơn + xác nhận nhu cầu trong 24h",
            "Gửi slide/tài liệu đã hứa tại booth",
        ],
        "pillar_matrix": [
            {"pillar": 1, "action": "Import CSV đồng bộ 1 lần/ngày sự kiện."},
            {"pillar": 2, "action": "Gặp trực tiếp + hẹn lịch = SQL tiềm năng."},
            {"pillar": 3, "action": "Email cảm ơn D0 + invite demo tuần sau."},
            {"pillar": 4, "action": "Deal cycle dài — reminder 7/14/30 ngày."},
            {"pillar": 5, "action": "Mời KH cũ tham sự kiện — upsell networking."},
            {"pillar": 6, "action": "Cost/lead sự kiện vs win rate."},
        ],
        "script_open": "Em gọi từ PTT — hôm {Ngày} event em có gặp anh/chị tại booth. Em gửi thêm tài liệu và hỗ trợ follow-up ạ.",
        "qualify_questions": ["Phần nào anh/chị quan tâm nhất tại booth?", "Team mình đang triển khai timeline thế nào?"],
        "if_no_answer": "Email + LinkedIn/Zalo; 3 touch trong 2 tuần.",
        "if_spam": "Namecard không liên lạc được — loại sau 3 lần.",
    },
    {
        "id": "returning",
        "label": "Khách cũ / Lịch sử mua hàng",
        "icon": "🔄",
        "detect": "SĐT/email khớp HĐ cũ, mua thêm, renewal, referral từ KH hiện hữu.",
        "crm_channel": "dien_thoai",
        "crm_channel_label": "Theo kênh liên hệ thực tế",
        "sla_contact": "≤4h — ưu tiên account owner cũ",
        "priority_hint": "Cao — LTV cao, chi phí acquire thấp",
        "intake_fields": [
            "Mã HĐ / case cũ",
            "Sản phẩm đã mua",
            "Account manager trước",
            "Loại nhu cầu: renewal / upsell / support",
        ],
        "t0_checklist": [
            "Tìm case/HĐ cũ trước khi tạo mới",
            "Gán owner là AM quen khách nếu còn active",
            "Ghi link hợp đồng cũ trong mô tả",
            "Phân biệt support ticket vs cơ hội upsell",
        ],
        "pillar_matrix": [
            {"pillar": 1, "action": "Single customer view — lịch sử mua hiển thị trên case."},
            {"pillar": 2, "action": "Upsell intent = priority Cao; support = route CSKH."},
            {"pillar": 3, "action": "Renewal reminder trước 60 ngày tự động."},
            {"pillar": 4, "action": "Pipeline upsell riêng; không lẫn lead lạnh."},
            {"pillar": 5, "action": "NPS sau milestone; referral program."},
            {"pillar": 6, "action": "LTV, repeat rate, NRR theo cohort."},
        ],
        "script_open": "Dạ chào anh/chị {Tên}, em {NV} phụ trách account PTT — em thấy mình có nhu cầu {Nhu cầu mới}, em hỗ trợ ạ.",
        "qualify_questions": ["Lần trước mình hài lòng phần nào cần cải thiện?", "Lần này mình mở rộng thêm phạm vi gì?"],
        "if_no_answer": "Email AM cá nhân; nhắc renewal theo timeline HĐ.",
        "if_spam": "N/A",
    },
)

CRM_WORKFLOW_PILLARS: tuple[dict[str, Any], ...] = (
    {
        "id": "data_hub",
        "num": 1,
        "title": "Thu thập & quản lý dữ liệu khách hàng tập trung",
        "summary": (
            "Gom mọi điểm chạm vào một hồ sơ khách duy nhất — form, cuộc gọi, email, ads, MXH và lịch sử mua."
        ),
        "goal": "Một nguồn sự thật (single source of truth) cho mọi lead/khách trên CRM PTT.",
        "owner": "CRM Admin · Marketing Ops",
        "apply_marketing": [
            "Lead vừa đổ về → tạo case trên Bảng CSKH trong 15 phút (ads/form) hoặc ngay sau cuộc gọi.",
            "Điền đủ: tên, SĐT, email, kênh CRM, nguồn marketing, UTM/campaign, sản phẩm quan tâm.",
            "Kiểm tra trùng — nếu khách cũ: mở case mới + link HĐ/case cũ trong mô tả.",
            "Không lưu lead trong Zalo cá nhân/Excel quá 24h.",
        ],
        "crm_links": [
            {"label": "Bảng CSKH (Kanban)", "route": "crm_board"},
            {"label": "Marketing & hợp đồng", "route": "crm_hub_page"},
        ],
        "steps": [
            {
                "title": "Chuẩn hóa nguồn dữ liệu đầu vào",
                "detail": (
                    "Form web/landing, lead ads (Meta/Google), hotline, email, Zalo OA, chatbot, sự kiện offline — "
                    "mỗi nguồn gắn UTM + mã kênh (`channel`) khi tạo yêu cầu CRM. "
                    "Xem bảng **Kênh marketing** bên dưới để biết trường bắt buộc từng kênh."
                ),
                "owner": "Marketing · Dev",
                "sla": "Trước khi chạy campaign",
            },
            {
                "title": "Hợp nhất hồ sơ trùng lặp",
                "detail": (
                    "Đối chiếu SĐT, email, tên công ty; gộp lịch sử tương tác; giữ một case chính / link case cũ."
                ),
                "owner": "CRM Admin",
                "sla": "Hàng ngày",
            },
            {
                "title": "Ghi nhận đầy đủ touchpoint",
                "detail": (
                    "Mỗi cuộc gọi, email, ghi chú, file đính kèm, thay đổi trạng thái được log trên timeline case."
                ),
                "owner": "CSKH · Sales",
                "sla": "Trong 4h sau tương tác",
            },
            {
                "title": "Đồng bộ lịch sử mua & hợp đồng",
                "detail": (
                    "Liên kết case → hợp đồng (Hub CRM), giá trị deal, ngày ký — quan trọng với khách quay lại từ marketing."
                ),
                "owner": "Sales Admin",
                "sla": "Trong 24h sau chốt",
            },
            {
                "title": "Phân quyền & bảo mật dữ liệu",
                "detail": "Chỉ nhân viên được gán mới xem hồ sơ; export có log; tuân thủ PDPA.",
                "owner": "CRM Admin · IT",
                "sla": "Review quý",
            },
        ],
        "checklist": [
            "100% lead ads có UTM + channel trên case CRM",
            "Không lead “treo” ngoài hệ thống >24h",
            "Timeline case có ít nhất 1 ghi chú sau mỗi cuộc gọi",
            "Trùng SĐT/email được merge trong tuần",
            "Hợp đồng đã ký được link về customer/case",
        ],
        "kpis": [
            {"name": "Tỷ lệ lead vào CRM", "target": "≥98%", "freq": "Tuần"},
            {"name": "Lead trùng chưa merge", "target": "≤2%", "freq": "Tuần"},
            {"name": "Case thiếu nguồn/kênh", "target": "≤5%", "freq": "Tháng"},
            {"name": "Thời gian ghi log TB", "target": "≤4h", "freq": "Tuần"},
        ],
    },
    {
        "id": "lead_scoring",
        "num": 2,
        "title": "Phân loại & chấm điểm khách hàng tiềm năng",
        "summary": (
            "Chia lead theo nhu cầu, hành vi, mức quan tâm và giai đoạn phễu — ưu tiên đúng người, đúng lúc."
        ),
        "goal": "Sales/CSKH tập trung vào lead có xác suất chốt cao nhất.",
        "owner": "Sales Lead · Marketing",
        "apply_marketing": [
            "Ngay khi tạo case: chọn Priority — **Cao** (hot: ads/form+hỏi giá, gọi đến), **Bình thường**, **Thấp** (nurture).",
            "Bảng chấm điểm nhanh: +3 inbound call/hỏi báo giá, +2 form đủ trường, +1 mở email, −2 spam/sai SĐT.",
            "Kéo Kanban: Mới → Đang liên hệ (khi gọi) → MQL (đủ nhu cầu) → SQL (hẹn demo).",
            "Lead cùng chiến dịch nhưng điểm thấp → đưa vào nurture, không tranh queue với hot lead.",
        ],
        "crm_links": [
            {"label": "Bảng CSKH", "route": "crm_board"},
            {"label": "Kế hoạch MK (KHTN)", "route": "crm_marketing_plan_page"},
        ],
        "steps": [
            {
                "title": "Định nghĩa phân khúc & persona (ICP)",
                "detail": "Ngành, quy mô, ngân sách, khu vực — hỏi trong 60 giây đầu cuộc gọi từ lead marketing.",
                "owner": "Marketing",
                "sla": "Cập nhật mỗi quý",
            },
            {
                "title": "Ma trận chấm điểm theo kênh",
                "detail": (
                    "Ads lead: cần thêm 2 câu qualify. Form landing: điểm cao hơn nếu điền budget. "
                    "MXH: DM+SĐT = hot. Khách cũ: auto priority Cao."
                ),
                "owner": "Marketing · Sales",
                "sla": "Áp dụng ngay T+0",
            },
            {
                "title": "Gán giai đoạn phễu trên Kanban",
                "detail": "Mới → Đang liên hệ → MQL → SQL → Báo giá → Chốt / Mất. Cần bằng chứng mới chuyển cột.",
                "owner": "Sales · CSKH",
                "sla": "Cập nhật trong ngày",
            },
            {
                "title": "Ưu tiên theo SLA kênh",
                "detail": "Ads/form ≤15 phút · Hotline ngay · Email ≤4h · MXH ≤30 phút · Event ≤24h.",
                "owner": "Team Lead CSKH",
                "sla": "Theo bảng kênh",
            },
            {
                "title": "Review chất lượng lead theo campaign",
                "detail": "T6: lead rác từ campaign X → Marketing tắt adset / sửa form.",
                "owner": "Sales Lead",
                "sla": "Thứ 6 hàng tuần",
            },
        ],
        "checklist": [
            "Mọi case mới có priority trong 30 phút",
            "Hot lead không quá 15 phút chưa có owner",
            "MQL/SQL có ghi chú bằng chứng qualify",
            "Lead rác được tag, không tính vào conversion",
        ],
        "kpis": [
            {"name": "Lead hot phản hồi ≤15 phút", "target": "≥90%", "freq": "Tuần"},
            {"name": "MQL → SQL", "target": "≥25%", "freq": "Tuần"},
            {"name": "Lead rác / không qualify", "target": "≤20%", "freq": "Tháng"},
            {"name": "Độ chính xác scoring (audit)", "target": "≥80%", "freq": "Quý"},
        ],
    },
    {
        "id": "nurture",
        "num": 3,
        "title": "Chăm sóc & nuôi dưỡng lead",
        "summary": (
            "Tự động hóa email, nhắc gọi lại, phân công owner và cá nhân hóa nội dung theo từng nhóm khách."
        ),
        "goal": "Không bỏ rơi lead giữa phễu; tăng tỷ lệ chuyển đổi nhờ follow-up có hệ thống.",
        "owner": "CSKH Lead · Marketing Automation",
        "apply_marketing": [
            "Sau touch đầu: luôn đặt **Nhắc việc** next step (gọi lại, gửi báo giá, demo).",
            "Không liên hệ được: D0 SMS/Zalo + D1 gọi + D3 email case study.",
            "Lead ấm nhưng chưa SQL → SOP nurture (module Quy trình SOP).",
            "Mỗi case mở không quá 7 ngày không activity — Team Lead review.",
        ],
        "crm_links": [
            {"label": "Bảng CSKH + Nhắc việc", "route": "crm_board"},
            {"label": "Quy trình SOP", "route": "crm_sop_page"},
        ],
        "steps": [
            {
                "title": "Journey nurture theo nguồn",
                "detail": "Ads/form: 3 touch/72h. Email: thread + call. MXH: chuyển Zalo rồi nurture. Event: D0 cảm ơn + D7 invite.",
                "owner": "Marketing",
                "sla": "Template sẵn theo kênh",
            },
            {
                "title": "Phân công owner & backup",
                "detail": "Round-robin lead mới; lead chiến dịch lớn → senior; khách cũ → AM cũ.",
                "owner": "CRM Admin",
                "sla": "≤1h",
            },
            {
                "title": "Nhắc lịch & escalation",
                "detail": "Miss SLA 2 lần → escalate Team Lead; priority tăng hoặc chuyển owner.",
                "owner": "CSKH",
                "sla": "Theo lịch hẹn",
            },
            {
                "title": "Script & nội dung theo kênh",
                "detail": "Dùng mẫu mở đầu/câu hỏi qualify trong bảng kênh marketing — không đọc script máy móc.",
                "owner": "CSKH · Content",
                "sla": "Mỗi touch",
            },
            {
                "title": "Đo hiệu quả nurture",
                "detail": "Touch count trước SQL; tỷ lệ trả lời theo kênh; tối ưu template tháng.",
                "owner": "Marketing",
                "sla": "Review tháng",
            },
        ],
        "checklist": [
            "100% case mới có owner trong 1h",
            "100% cuộc gọi có next reminder",
            "Lead warm ≥3 touch trong 72h",
            "Không case stale >7 ngày",
        ],
        "kpis": [
            {"name": "Case có owner", "target": "100%", "freq": "Ngày"},
            {"name": "Follow-up đúng hạn", "target": "≥85%", "freq": "Tuần"},
            {"name": "Lead nurture → SQL", "target": "≥15%", "freq": "Tháng"},
            {"name": "Case stale (>7 ngày)", "target": "≤5%", "freq": "Tuần"},
        ],
    },
    {
        "id": "pipeline",
        "num": 4,
        "title": "Quản lý cơ hội & quy trình bán hàng",
        "summary": (
            "Theo dõi pipeline, báo giá, hợp đồng, công nợ, lịch hẹn, cuộc gọi — không bỏ sót cơ hội."
        ),
        "goal": "Minh bạch pipeline, dự báo doanh thu và kiểm soát từng deal.",
        "owner": "Sales Manager",
        "apply_marketing": [
            "Lead marketing qualify → ghi **giá trị deal ước tính** trên case/mô tả.",
            "Sau demo/meeting: gửi báo giá ≤48h; ghi timeline “Đã gửi BG v1”.",
            "Chốt từ lead ads/form → tạo HĐ Hub + tag campaign để đo ROI.",
            "Deal >30 ngày không tiến triển → họp pipeline, đổi chiến lược nurture hoặc pause.",
        ],
        "crm_links": [
            {"label": "Marketing & hợp đồng", "route": "crm_hub_page"},
            {"label": "Bảng CSKH", "route": "crm_board"},
        ],
        "steps": [
            {
                "title": "Pipeline stages trên Kanban",
                "detail": "SQL → Báo giá sent → Thương lượng → Won/Lost — mỗi bước có tiêu chí rõ.",
                "owner": "Sales Lead",
                "sla": "Review quý",
            },
            {
                "title": "Báo giá khớp offer marketing",
                "detail": "Lead từ ad offer X → báo giá không lệch messaging; ghi campaign trên HĐ.",
                "owner": "Sales",
                "sla": "≤48h sau meeting",
            },
            {
                "title": "Hợp đồng & công nợ",
                "detail": "Won → Hub CRM trong 24h; milestone thu tiền; nhắc công nợ.",
                "owner": "Sales Admin · Finance",
                "sla": "24h",
            },
            {
                "title": "Lịch hẹn từ lead marketing",
                "detail": "Demo/site visit — reminder confirm T-24h; ghi no-show rate.",
                "owner": "Sales · CSKH",
                "sla": "Confirm trước 24h",
            },
            {
                "title": "Forecast theo nguồn",
                "detail": "Pipeline value split: ads / form / referral / event — dự báo riêng.",
                "owner": "Sales Manager",
                "sla": "Weekly",
            },
        ],
        "checklist": [
            "SQL có ngày follow-up tiếp theo",
            "Báo giá ghi trên timeline",
            "Won có HĐ Hub + tag campaign",
            "Lost có lý do (giá/ timing/ competitor)",
        ],
        "kpis": [
            {"name": "Win rate", "target": "Theo target quý", "freq": "Tháng"},
            {"name": "Thời gian chốt TB", "target": "Giảm 10%/quý", "freq": "Quý"},
            {"name": "Báo giá → Won", "target": "≥25%", "freq": "Tháng"},
            {"name": "ROI theo campaign", "target": "≥3× chi ads", "freq": "Tháng"},
        ],
    },
    {
        "id": "retention",
        "num": 5,
        "title": "Chăm sóc sau bán & giữ chân khách hàng",
        "summary": (
            "Hỗ trợ sau bán, xử lý phản hồi, upsell/cross-sell và duy trì quan hệ — tăng doanh thu lặp lại."
        ),
        "goal": "LTV cao, churn thấp, khách hàng trung thành và giới thiệu thêm.",
        "owner": "CSKH Lead · Account Manager",
        "apply_marketing": [
            "Lead marketing chốt → handoff onboarding ≤3 ngày; case chuyển owner CSKH/AM.",
            "Khách quay lại qua form/ads → nhận diện KH cũ, ưu tiên upsell không xử lý như lead lạnh.",
            "Referral từ KH cũ → tag nguồn referral + cảm ơn referrer.",
            "Renewal nhắc T-60 ngày; NPS sau milestone dự án.",
        ],
        "crm_links": [
            {"label": "Bảng CSKH", "route": "crm_board"},
            {"label": "KPI nhân viên", "route": "crm_kpi_page"},
        ],
        "steps": [
            {
                "title": "Onboarding sau ký HĐ",
                "detail": "Kick-off checklist; contact point; case status chuyển sang triển khai.",
                "owner": "Account · CSKH",
                "sla": "≤3 ngày",
            },
            {
                "title": "Phản hồi & ticket",
                "detail": "Khiếu nại từ email/MXH sau bán → gắn case cũ; SLA P1/P2.",
                "owner": "CSKH",
                "sla": "P1: 4h",
            },
            {
                "title": "Upsell từ lead marketing cũ",
                "detail": "Campaign remarketing list = KH đã mua; AM chủ động gọi, không để telesales lạ treat như lead mới.",
                "owner": "Account Manager",
                "sla": "6 tháng/KH",
            },
            {
                "title": "Referral & giữ chân",
                "detail": "Chương trình giới thiệu; newsletter; ưu đãi renewal.",
                "owner": "Marketing · CSKH",
                "sla": "Quý",
            },
            {
                "title": "Win-back",
                "detail": "Churn → chiến dịch 30/60/90 ngày; phân tích lý do vào CRM.",
                "owner": "CSKH Lead",
                "sla": "14 ngày",
            },
        ],
        "checklist": [
            "100% HĐ mới onboarding xong",
            "KH cũ quay lại được route đúng AM",
            "Referral có tag nguồn",
            "Renewal T-60 có task",
        ],
        "kpis": [
            {"name": "NPS / CSAT", "target": "≥40 / ≥4.2", "freq": "Quý"},
            {"name": "Churn rate", "target": "≤5%/năm", "freq": "Quý"},
            {"name": "Doanh thu upsell", "target": "≥15% tổng DT", "freq": "Năm"},
            {"name": "Referral lead → won", "target": "≥30%", "freq": "Quý"},
        ],
    },
    {
        "id": "analytics",
        "num": 6,
        "title": "Đo lường & tối ưu liên tục",
        "summary": (
            "Theo dõi KPI: chuyển đổi, thời gian chốt, doanh thu theo nguồn lead, hiệu suất sales và CSKH."
        ),
        "goal": "Ra quyết định dựa trên dữ liệu; cải tiến quy trình mỗi chu kỳ.",
        "owner": "CRM Admin · Leadership",
        "apply_marketing": [
            "Mọi case từ marketing phải có campaign/UTM trong mô tả để báo cáo CPL → SQL → Won.",
            "Daily: số lead mới theo kênh + hot chưa xử lý.",
            "Weekly T6: conversion funnel theo form/ads/MXH; feedback Marketing.",
            "Monthly: ROMI từng campaign; coaching NV có SLA thấp.",
        ],
        "crm_links": [
            {"label": "KPI nhân viên", "route": "crm_kpi_page"},
            {"label": "Chấm công & lương", "route": "crm_payroll_page"},
        ],
        "steps": [
            {
                "title": "Dashboard theo nguồn marketing",
                "detail": "Lead count, MQL, SQL, won, revenue — split form/ads/email/MXH/event/referral.",
                "owner": "CRM Admin",
                "sla": "Thiết lập ban đầu",
            },
            {
                "title": "Cadence báo cáo",
                "detail": "Daily hot queue · Weekly funnel by channel · Monthly ROMI · Quarterly playbook review.",
                "owner": "Sales · Marketing Lead",
                "sla": "Cố định",
            },
            {
                "title": "Tối ưu campaign từ CRM data",
                "detail": "Lead rác cao → sửa form/target ads; win rate thấp → đào tạo script qualify.",
                "owner": "Marketing",
                "sla": "Tháng",
            },
            {
                "title": "KPI nhân viên theo kênh",
                "detail": "SLA phản hồi ads vs email; số SQL/NV; audit call mẫu.",
                "owner": "Team Lead",
                "sla": "Tháng",
            },
            {
                "title": "PDCA playbook",
                "detail": "Cập nhật bảng kênh marketing + 6 trụ sau mỗi quý.",
                "owner": "Leadership",
                "sla": "Quý",
            },
        ],
        "checklist": [
            "Case marketing có tag campaign",
            "Báo cáo T6 có action items",
            "CPL/SQL tracked per channel",
            "Playbook review quý",
        ],
        "kpis": [
            {"name": "Conversion funnel", "target": "Theo target quý", "freq": "Tháng"},
            {"name": "Thời gian chốt TB", "target": "Giảm QoQ", "freq": "Quý"},
            {"name": "Doanh thu / nguồn lead", "target": "ROI ≥3× ads", "freq": "Tháng"},
            {"name": "SLA phản hồi lead", "target": "≥90%", "freq": "Tuần"},
        ],
    },
)


def get_crm_workflow_playbook() -> list[dict[str, Any]]:
    return [dict(p) for p in CRM_WORKFLOW_PILLARS]


def get_crm_lead_intake_master_flow() -> list[dict[str, Any]]:
    return [dict(p) for p in CRM_LEAD_INTAKE_MASTER_FLOW]


def get_crm_marketing_ingress_channels() -> list[dict[str, Any]]:
    return [dict(c) for c in CRM_MARKETING_INGRESS_CHANNELS]
