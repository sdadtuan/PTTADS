# crm_svc_risk_registry.py
"""Risk registry data-only cho 12 dịch vụ PTTP."""
from __future__ import annotations

AI_RISK_SCAN_PROMPT: str = (
    "Bạn là chuyên gia quản lý rủi ro {service_name} của agency PTT.\n"
    "KH: {customer_name}, đang ở giai đoạn: {current_stage}.\n"
    "Tóm tắt tiến độ: {progress_summary}\n\n"
    "Danh sách rủi ro đang theo dõi:\n{risks_list}\n\n"
    "Phân tích và xác định TOP 3 rủi ro CÓ KHẢ NĂNG XẢY RA NHẤT ở thời điểm này.\n"
    "Với mỗi rủi ro, giải thích ngắn gọn (1-2 câu) tại sao nó đang cần chú ý.\n"
    "Nếu không có rủi ro đáng lo ngại, viết: 'Không phát hiện rủi ro cấp bách.'\n\n"
    "Format:\n⚠️ [Tên rủi ro]: [Lý do cụ thể dựa trên giai đoạn {current_stage}]"
)

SERVICE_RISK_REGISTRY: dict[str, list[dict]] = {

    "dich-vu-seo-tong-the": [
        {
            "stage": "deliver",
            "title": "Google core update ảnh hưởng ranking đột ngột",
            "category": "external",
            "probability": "cao",
            "impact": "cao",
            "mitigation": "Monitor Google Search Console và Search Central Blog hàng ngày. Diversify traffic sources, không phụ thuộc 1 nhóm từ khóa. Chuẩn bị plan phục hồi nhanh.",
        },
        {
            "stage": "deliver",
            "title": "Nội dung bị thin content hoặc duplicate",
            "category": "technical",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Audit content hàng tháng. Đảm bảo mỗi trang >500 từ unique, không sao chép từ nguồn khác. Dùng Copyscape để check.",
        },
        {
            "stage": "deliver",
            "title": "Đối thủ tăng link building đột biến",
            "category": "external",
            "probability": "trung",
            "impact": "trung",
            "mitigation": "Monitor backlink đối thủ hàng tháng qua Ahrefs/SEMrush. Tăng tốc link building cho KH khi phát hiện đối thủ đang bứt phá.",
        },
        {
            "stage": "onboard",
            "title": "KH không cung cấp access GSC/GA4 đúng hạn",
            "category": "communication",
            "probability": "cao",
            "impact": "trung",
            "mitigation": "Yêu cầu access trong 48h sau ký hợp đồng. Gửi hướng dẫn từng bước bằng video screen record. Có thể bắt đầu on-page mà không cần GSC.",
        },
        {
            "stage": "deliver",
            "title": "Ngân sách bị cắt giảm giữa chừng",
            "category": "resource",
            "probability": "thap",
            "impact": "cao",
            "mitigation": "Báo cáo ROI hàng tháng rõ ràng. Chuẩn bị package scaled-down nếu KH cần giảm chi phí. Tránh phụ thuộc vào tools trả phí cao.",
        },
    ],

    "dich-vu-aeo": [
        {
            "stage": "deliver",
            "title": "AI model providers thay đổi cách trả kết quả tìm kiếm",
            "category": "external",
            "probability": "cao",
            "impact": "cao",
            "mitigation": "Theo dõi changelog của ChatGPT, Gemini, Perplexity hàng tuần. Đa dạng hóa loại content (FAQ, how-to, definition) để cover nhiều query pattern.",
        },
        {
            "stage": "deliver",
            "title": "Nội dung không đáp ứng E-E-A-T signals",
            "category": "technical",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Thêm author bio, credentials, ngày cập nhật vào mọi bài viết. Trích dẫn nguồn uy tín. Gắn schema markup Person và Organization.",
        },
        {
            "stage": "onboard",
            "title": "KH thiếu dữ liệu cấu trúc (schema markup) cơ bản",
            "category": "technical",
            "probability": "cao",
            "impact": "trung",
            "mitigation": "Audit schema markup ngay tuần đầu. Implement FAQ, HowTo, Article schema. Verify qua Google Rich Results Test.",
        },
    ],

    "dich-vu-seo-local": [
        {
            "stage": "onboard",
            "title": "GBP bị suspended hoặc có duplicate listing",
            "category": "external",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Audit GBP ngay khi onboard. Report duplicate listing. Nếu bị suspend: liên hệ Google Business support ngay, chuẩn bị tài liệu xác minh địa chỉ.",
        },
        {
            "stage": "deliver",
            "title": "Review tiêu cực đột ngột từ đối thủ (review bombing)",
            "category": "external",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Monitor GBP reviews hàng ngày. Report review fake ngay lên Google. Khuyến khích KH thu thập review thật từ khách hàng hài lòng.",
        },
        {
            "stage": "deliver",
            "title": "NAP inconsistency giữa các citation",
            "category": "technical",
            "probability": "cao",
            "impact": "trung",
            "mitigation": "Audit citation hàng quý qua Moz Local. Chuẩn hóa Name, Address, Phone trước khi build citation mới. Dùng template NAP cố định.",
        },
    ],

    "dich-vu-seo-audit": [
        {
            "stage": "onboard",
            "title": "KH không cung cấp access GSC/GA4 đúng hạn",
            "category": "communication",
            "probability": "cao",
            "impact": "cao",
            "mitigation": "Ghi rõ trong hợp đồng: cung cấp access trong 24h sau ký. Không có access = không thể bắt đầu audit. Tính phí delay nếu quá 48h.",
        },
        {
            "stage": "deliver",
            "title": "Website quá nhiều vấn đề kỹ thuật dẫn đến scope creep",
            "category": "scope",
            "probability": "trung",
            "impact": "trung",
            "mitigation": "Giới hạn rõ phạm vi audit trong hợp đồng (N trang, N issues). Issues ngoài scope → báo giá thêm riêng. Dùng priority matrix để focus vào critical trước.",
        },
    ],

    "dich-vu-quan-tri-website": [
        {
            "stage": "deliver",
            "title": "Plugin conflict sau khi update WordPress",
            "category": "technical",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Test update trên staging trước. Backup toàn bộ trước mỗi lần update. Cập nhật plugin từng cái một, không batch update. Có rollback plan sẵn.",
        },
        {
            "stage": "deliver",
            "title": "Website bị inject malware hoặc hack",
            "category": "external",
            "probability": "thap",
            "impact": "cao",
            "mitigation": "Setup Wordfence/Sucuri security monitoring. Scan malware hàng tuần. 2FA cho tất cả admin accounts. Backup daily off-site.",
        },
        {
            "stage": "deliver",
            "title": "KH tự chỉnh sửa admin gây lỗi layout",
            "category": "communication",
            "probability": "cao",
            "impact": "trung",
            "mitigation": "Training KH quy tắc chỉnh sửa an toàn. Giới hạn quyền KH (Editor, không phải Admin). Ghi rõ SLA fix lỗi do KH gây ra (có thể tính phí).",
        },
        {
            "stage": "deliver",
            "title": "Hosting downtime ảnh hưởng uptime SLA",
            "category": "external",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Setup UptimeRobot monitoring với alert 5 phút. Liên hệ hosting provider ngay khi phát hiện. Document incident. Ghi rõ trong SLA: downtime do hosting không thuộc trách nhiệm.",
        },
    ],

    "thiet-ke-website": [
        {
            "stage": "deliver",
            "title": "KH thay đổi yêu cầu design sau khi đã approve",
            "category": "scope",
            "probability": "cao",
            "impact": "cao",
            "mitigation": "KH ký approval form trước khi bắt đầu code/production. Thay đổi sau approve = revision ngoài scope, tính phí. Ghi rõ trong hợp đồng số lần revision miễn phí.",
        },
        {
            "stage": "onboard",
            "title": "Brand assets KH cung cấp không đúng chất lượng",
            "category": "resource",
            "probability": "trung",
            "impact": "trung",
            "mitigation": "Checklist assets cần thiết: logo vector (AI/EPS/SVG), ảnh min 2MB, màu sắc HEX. Gửi checklist ngay sau ký hợp đồng. Báo ngay nếu assets không đạt.",
        },
        {
            "stage": "deliver",
            "title": "Số vòng revision vượt quá cam kết",
            "category": "scope",
            "probability": "cao",
            "impact": "trung",
            "mitigation": "Ghi rõ trong hợp đồng: tối đa N vòng revision. Feedback phải tổng hợp, không gửi rải rác. Vòng thêm = phí phát sinh.",
        },
    ],

    "thiet-ke-website-tron-goi": [
        {
            "stage": "deliver",
            "title": "Tính năng mới phát sinh ngoài scope ban đầu",
            "category": "scope",
            "probability": "cao",
            "impact": "cao",
            "mitigation": "Scope document chi tiết ký trước khi bắt đầu. Tính năng mới = change request form + báo giá riêng. Không implement gì ngoài scope mà không có written approval.",
        },
        {
            "stage": "onboard",
            "title": "Nội dung KH cung cấp chậm ảnh hưởng timeline",
            "category": "communication",
            "probability": "cao",
            "impact": "cao",
            "mitigation": "Ghi deadline cung cấp nội dung vào hợp đồng. Content muộn → timeline bị đẩy tương ứng. Có thể dùng placeholder content để tiến hành song song.",
        },
        {
            "stage": "handover",
            "title": "Bug phát sinh sau go-live trên thiết bị thực",
            "category": "technical",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Test trên ít nhất 3 browser (Chrome/Firefox/Safari) và mobile thực tế trước go-live. Setup staging environment. Warranty 30 ngày bug fix miễn phí sau go-live.",
        },
    ],

    "thiet-ke-landing-page": [
        {
            "stage": "handover",
            "title": "Landing page có CVR thấp sau khi live",
            "category": "external",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Brief KH rõ: design ảnh hưởng CVR nhưng traffic quality và offer mới là quyết định chính. Đề xuất A/B test sau 2 tuần live. Setup heatmap (Hotjar) để phân tích.",
        },
        {
            "stage": "onboard",
            "title": "Assets KH cung cấp không đúng định dạng/kích thước",
            "category": "resource",
            "probability": "trung",
            "impact": "trung",
            "mitigation": "Gửi asset checklist ngay sau ký hợp đồng. Ảnh sản phẩm cần: nền trắng, min 1000x1000px, JPG/PNG. Logo: SVG/EPS. Copy đã final, không chỉnh sau khi design.",
        },
    ],

    "quang-cao-facebook": [
        {
            "stage": "deliver",
            "title": "Tài khoản Ads bị disabled hoặc review đột ngột",
            "category": "external",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Không vi phạm policy quảng cáo Meta. Review creative trước khi chạy. Có backup tài khoản/BM. Liên hệ Meta support ngay khi bị review. Thông báo KH trong 2h.",
        },
        {
            "stage": "deliver",
            "title": "Creative fatigue khiến hiệu quả giảm sau 2-3 tuần",
            "category": "technical",
            "probability": "cao",
            "impact": "trung",
            "mitigation": "Chuẩn bị bank creative đủ cho 4-6 tuần. Lên lịch refresh creative định kỳ 2 tuần/lần. Monitor frequency: >3 lần/người cần đổi creative.",
        },
        {
            "stage": "deliver",
            "title": "CPL tăng đột biến do market/mùa vụ",
            "category": "external",
            "probability": "cao",
            "impact": "cao",
            "mitigation": "Brief KH về biến động CPL theo mùa (Tết, sale season...). Điều chỉnh ngân sách và bid strategy linh hoạt. Tập trung vào retargeting khi cold audience tăng giá.",
        },
        {
            "stage": "onboard",
            "title": "Pixel tracking không hoạt động đúng",
            "category": "technical",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Verify pixel với Meta Pixel Helper trong 24h đầu. Test event tracking bằng Test Events tool. Không chạy conversion campaign khi chưa có đủ conversion event (min 50/tuần).",
        },
    ],

    "quang-cao-google": [
        {
            "stage": "deliver",
            "title": "Quality Score thấp làm tăng CPC đột ngột",
            "category": "technical",
            "probability": "cao",
            "impact": "trung",
            "mitigation": "Kiểm tra Expected CTR, Ad Relevance, Landing Page Experience hàng tuần. Tối ưu ad copy để match từ khóa. Landing page phải load <3s và có nội dung liên quan.",
        },
        {
            "stage": "deliver",
            "title": "Budget depleted trước cuối tháng",
            "category": "resource",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Setup budget alert tại 50%, 75%, 90%. Dùng Shared Budget để phân bổ. Báo KH ngay khi budget sắp cạn. Có plan contingency: pause non-performing campaigns.",
        },
        {
            "stage": "deliver",
            "title": "Competitor bidding war đẩy CPC vượt ngưỡng ROI",
            "category": "external",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Monitor auction insights hàng tuần. Chuyển sang long-tail keywords ít cạnh tranh hơn. Tối ưu Quality Score để giảm CPC thực tế mà không cần tăng bid.",
        },
        {
            "stage": "onboard",
            "title": "Conversion tracking setup sai gây data không chính xác",
            "category": "technical",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Test conversion tracking với Google Tag Assistant trước khi launch. Verify ít nhất 5 conversions test. Không optimize campaign khi conversion data chưa ổn định.",
        },
    ],

    "thue-tai-khoan-quang-cao": [
        {
            "stage": "deliver",
            "title": "Tài khoản bị review/suspend từ platform",
            "category": "external",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Monitor tài khoản daily. Không để spend bất thường. Liên hệ support trong 2h nếu phát hiện vấn đề. Có backup account plan sẵn. Thông báo KH ngay lập tức.",
        },
        {
            "stage": "deliver",
            "title": "KH chạy sản phẩm/dịch vụ vi phạm policy platform",
            "category": "communication",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Review creative KH trước khi approve. Ghi rõ trong hợp đồng: KH chịu trách nhiệm nội dung quảng cáo. Suspend ngay nếu phát hiện vi phạm để bảo vệ tài khoản.",
        },
        {
            "stage": "deliver",
            "title": "Payment method gặp vấn đề dẫn đến gián đoạn campaign",
            "category": "resource",
            "probability": "thap",
            "impact": "cao",
            "mitigation": "Setup 2 payment method backup. Monitor billing threshold. Báo KH 3 ngày trước khi cần nạp tiền. Có manual payment plan dự phòng.",
        },
    ],

    "tiep-thi-noi-dung": [
        {
            "stage": "deliver",
            "title": "KH không duyệt content đúng hạn làm trễ lịch publish",
            "category": "communication",
            "probability": "cao",
            "impact": "cao",
            "mitigation": "Ghi SLA duyệt content vào hợp đồng: KH duyệt trong 48h. Quá thời gian = tự động publish theo lịch. Gửi nhắc nhở tự động 24h trước deadline duyệt.",
        },
        {
            "stage": "deliver",
            "title": "Topic đã plan mất tính thời sự hoặc đã bị đối thủ cover",
            "category": "external",
            "probability": "trung",
            "impact": "trung",
            "mitigation": "Content calendar linh hoạt: 70% planned topics + 30% trending. Monitor đối thủ hàng tuần. Cập nhật calendar hàng tháng theo xu hướng ngành.",
        },
        {
            "stage": "deliver",
            "title": "Keyword cannibalization với nội dung cũ KH đã có",
            "category": "technical",
            "probability": "trung",
            "impact": "trung",
            "mitigation": "Audit content KH hiện có trước khi lên content plan. Mỗi từ khóa chỉ được target bởi 1 trang chính. Consolidate content trùng lặp.",
        },
        {
            "stage": "deliver",
            "title": "Nội dung AI-generated bị detect và bị phạt SEO",
            "category": "technical",
            "probability": "trung",
            "impact": "cao",
            "mitigation": "Mọi content phải có human review và rewrite ≥40%. Thêm insights thực tế, case studies, quotes từ expert. Tránh generic AI output không có unique value.",
        },
    ],
}
