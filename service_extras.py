"""
Nội dung trang dịch vụ theo từng slug (bố cục & giọng văn tham chiếu bngagency.vn).
Có thể ghi đè từng trường qua `service_categories_json` trong settings / CMS.
"""
from __future__ import annotations

from typing import Any

# fmt: off
DEFAULT_SERVICE_LANDING_EXTRAS: dict[str, dict[str, Any]] = {
    "dich-vu-aeo": {
        "tagline": "Tối ưu nội dung cho kỷ nguyên trả lời tức thì — từ Google SGE đến AI chatbot",
        "overview": [
            "Khi người dùng không còn chỉ “đọc danh sách xanh 10 mục” mà cần câu trả lời gọn, đáng tin ngay tại màn tìm kiếm, việc chuẩn hóa cấu trúc câu hỏi–câu trả lời, entity và dữ liệu có cấu trúc (FAQ, schema) trở thành nền tảng của tăng trưởng tự nhiên.",
            "Gói AEO tại PTT bám theo cách hệ tìm kiếm và mô hình trích dẫn ưu tiên: làm rõ ý định tìm hiểu, ưu tiên mục tiêu hiển thị trong câu trả lời, và điều phối nội dung dài hạn với SEO tổng thể nếu bạn cần thứ hạng từ khóa song song với tín hiệu cho AI.",
        ],
        "stats": [
            {"value": "AEO+SEO", "label": "Có thể tích hợp từ khóa, entity và câu hỏi dài"},
            {"value": "FAQ / Schema", "label": "Hướng tới câu trả lời trực diện & hộp tìm kiếm"},
            {"value": "Lộ trình giai đoạn", "label": "Nội dung & đo lường từng mốc"},
        ],
        "pillars": [
            {
                "title": "Cấu trúc câu trả lời rõ ràng",
                "body": "Chia từng vấn đề người dùng theo từng bước, tránh câu từ vựng mơ hồ, trùng nội dung. Ưu tiên câu hỏi mở ở heading và đoạn mở đoạn, giúp dễ bị tóm tắt bởi công cụ tìm kiếm và AI.",
            },
            {
                "title": "Dữ liệu có cấu trúc & cập nhật thực tế",
                "body": "Hướng dẫn triển khai FAQ, HowTo, giá, chính sách — phù hợp từng trang, tránh cài schema mang tính mẫu. Đồng bộ với thay đổi sản phẩm/dịch vụ thực tế.",
            },
            {
                "title": "Theo dõi hiển thị & cải tiến",
                "body": "Theo từng mục: nguồn tham chiếu, loại câu hỏi, vùng địa lý, nhóm dịch vụ. Điều chỉnh ưu tiên cập nhật theo tác động.",
            },
        ],
        "outcomes": [
            "Nâng tín hiệu tính thuyết (E-E-A-T) theo từng trụ sản phẩm, ngành hàng",
            "Giảm nội dung trùng lặp ý, tăng tỷ lệ câu trả lời hữu ích theo từng truy vấn",
            "Phối hợp ổn với lộ trình SEO/ads khi cần thúc click vào site",
        ],
        "deliverable_title": "Hạng mục & phạm vi bàn giao",
        "stats_section_title": "Trọng tâm theo từng giai đoạn",
        "pillars_section_title": "Cách PTT triển khai AEO",
        "outcomes_section_title": "Kết quả hướng tới",
        "faq": [
            {
                "q": "AEO khác SEO truyền thống chỗ nào?",
                "a": "SEO từ khóa thường tối ưu theo từ khóa và thứ hạng. AEO thêm tầng: cấu trúc câu hỏi–trả lời, tính trích dẫn, schema và tính đầy đủ để công cụ/AI tóm tắt đúng. Hai hướng nên bổ trợ, không thay thế hẳn nhau.",
            },
            {
                "q": "Có cam kết xuất hiện trên AI cụ thể không?",
                "a": "Không nên hứa tuyệt đối vì thuật toán và sản phẩm tìm kiếm thay đổi. Chúng tôi cam kết theo từng mốc: cấu trúc, nội dung, theo dõi hiển thị và ưu tiên tối ưu tác động cao.",
            },
        ],
        "inline_cta": "Bạn muốn ưu tiên từ khóa, trích dẫn AI, hay cả hai? Để lại thông tin để nhận lộ trình tích hợp phù hợp giai đoạn.",
        "cta_wide_title": "Bắt đầu lộ trình AEO phù hợp ngành hàng & dữ liệu hiện có?",
        "cta_wide_lead": "Chúng tôi đối chiếu hạ tầng nội dung, tín hiệu kỹ thuật và mục tiêu truyền thông, sau đó trả về bản tóm tắt ưu tiên trước khi bạn chốt phạm vi.",
        "meta_description": "Dịch vụ AEO (Answer Engine Optimization) — tối ưu nội dung & schema để tăng khả năng hiển thị trong câu trả lời tìm kiếm và AI. PTT Advertising Solutions, Việt Nam.",
    },
    "dich-vu-seo-tong-the": {
        "tagline": "Kết hợp kỹ thuật, nội dung và tín hiệu liên kết theo bền vững dài hạn",
        "overview": [
            "SEO tổng thể cần đồng bộ từ cấu trúc thu thập, index, tốc độ trang, đến nội dung trả lời đúng ý định và liên kết bên ngoài phù hợp mức độ cạnh tranh. Chúng tôi tránh tối ưu hình thức — tập trung tác động đo được (traffic, chuyển đổi, từ khóa cạnh tranh ưu tiên).",
            "Bạn nhận lịch ưu tiên, báo cáo theo mốc, và tùy dự án sẽ phối hợp với ads, nội dung, web để không kéo traffic về trang yếu chuyển đổi.",
        ],
        "stats": [
            {"value": "On & off", "label": "On-page, kỹ thuật, nội dung, liên kết"},
            {"value": "CWV", "label": "Theo dõi tốc độ & trải nghiệm cơ bản"},
            {"value": "Báo cáo", "label": "Thứ hạng, traffic, mục tiêu trang đích"},
        ],
        "pillars": [
            {
                "title": "Hạ tầng thu thập & index ổn định",
                "body": "Rà crawl, redirect, cấu trúc, trang trùng, sitemap. Giảm lỗi hạ tầng trước khi tối ưu sâu nội dung từng trang — tránh tốn công tối ưu mà trang không được index ổn.",
            },
            {
                "title": "Nội dung theo hành trình, không dàn trải từ khóa",
                "body": "Ưu tiên từ khóa ngắn + dài, cluster chủ đề, internal link. Tránh tạo nhiều trang cạnh tranh cùng ý.",
            },
            {
                "title": "Liên kết bền vững, phù hợp chính sách",
                "body": "Hướng tới tín hiệu tự nhiên và từ quan hệ hợp tác, tránh công thức mua link rủi ro. Phù hợp mức cạnh tranh từng lĩnh vực.",
            },
        ],
        "outcomes": [
            "Lộ rõ ưu tiên sửa kỹ thuật vs nội dung theo tác động gần với mục tiêu doanh số/lead",
            "Báo cáo theo từng mốc, dễ so sánh theo mùa / đợt ưu tiên sản phẩm",
            "Phối hợp với ads/AEO nếu cần thúc tốc tần suất cập nhật",
        ],
        "deliverable_title": "Gói triển khai & hạng mục bàn giao",
        "stats_section_title": "Chỉ số theo dõi",
        "pillars_section_title": "Nền tảng SEO tổng thể tại PTT",
        "outcomes_section_title": "Kết quả kinh doanh hướng tới",
        "faq": [
            {
                "q": "Bao lâu thấy tín hiệu tích cực?",
                "a": "Tùy độ cạnh tranh, lịch sử site, và phạm vi tối ưu. Thường ưu tiên sửa lỗi hạ tầng và từ khóa ưu tiên trước, sau đó mở rộng theo từng giai đoạn.",
            },
            {
                "q": "Có tối ưu song song bản mobile không?",
                "a": "Có. Google dùng mobile-first; tốc độ, hiển thị và cấu trúc cần kiểm tra trên thiết bị thật.",
            },
        ],
        "inline_cta": "Bạn ưu tiên doanh số, lead, hay từ khóa cạnh tranh? Gửi ngắn gọn để nhận bản ưu tiên hành động.",
        "cta_wide_title": "Thống nhất mục tiêu tìm kiếm với tăng trưởng thực tế",
        "cta_wide_lead": "Chúng tôi lập ưu tiên theo tác động, không dàn công sức đồng đều mọi trang. Nhận đề xuất triển khai sau khi rà tình trạng hiện tại.",
        "meta_description": "Dịch vụ SEO tổng thể: kỹ thuật, nội dung, liên kết, báo cáo thứ hạng & chuyển đổi. PTT Advertising Solutions, Việt Nam.",
    },
    "dich-vu-seo-local": {
        "tagline": "Hiện diện bản đồ, tìm kiếm theo vùng và hành vi “gần tôi”",
        "overview": [
            "Doanh nghiệp cửa hàng, dịch vụ tận nơi hoặc nhiều chi nhánh cần tín hiệu đồng nhất (NAP), đánh giá, và nội dung địa phương — không chỉ từ khóa thành phố mà cả từng khu vực kinh doanh thực tế.",
            "Chúng tôi phối hợp hồ sơ Google Business, tối ưu landing địa phương trên site, và theo dõi cuộc gọi, chỉ đường, form theo từng mục.",
        ],
        "stats": [
            {"value": "GBP", "label": "Hồ sơ doanh nghiệp, danh mục, bài đăng"},
            {"value": "NAP", "label": "Thống nhất tên, địa chỉ, SĐT đa nền tảng"},
            {"value": "Địa phương", "label": "Nội dung theo từng vùng / chi nhánh"},
        ],
        "pillars": [
            {
                "title": "Hồ sơ & chính sách hiển thị hợp lệ",
                "body": "Cập nhật thông tin chính xác, hình ảnh, giờ hoạt động, dịch vụ. Hạn chế vi phạm chính sách tìm bản đồ dẫn đến hạ hiển thị.",
            },
            {
                "title": "Nội dung theo từng vùng",
                "body": "Trang landing hoặc mục con phục vụ từ khu vực, kèm tín hiệu nội bộ tới trang tổng hợp dịch vụ.",
            },
            {
                "title": "Đánh giá & phản hồi",
                "body": "Hướng dẫn quy trình mời đánh giá, phản hồi phù hợp, tránh cách tăng tín hiệu rủi ro.",
            },
        ],
        "outcomes": [
            "Nâng tỷ lệ hiện tại bản đồ và tìm kiếm theo từ khóa địa phương ưu tiên",
            "Theo dõi số lượt gọi, chỉ đường, truy cập từ local pack khi cấu hình cho phép",
        ],
        "deliverable_title": "Công việc thực hiện theo từng mốc",
        "stats_section_title": "Kênh & tín hiệu",
        "pillars_section_title": "Hướng tiếp cận Local SEO tại PTT",
        "outcomes_section_title": "Kết quả theo từng mục kinh doanh",
        "faq": [
            {
                "q": "Nhiều chi nhánh có cần nhiều tài khoản?",
                "a": "Tùy mô hình. Một số dùng địa điểm hợp lệ, một số tách tài khoản. Chúng tôi tư vấn theo chính sách và tình trạng thương hiệu thực tế.",
            }
        ],
        "inline_cta": "Bạn cần tối ưu một điểm hay cả mạng lưới chi nhánh? Mô tả nhanh để nhận cấu trúc hợp lệ với từng mục.",
        "cta_wide_title": "Tăng số tương tác từ khu vực kinh doanh thực",
        "cta_wide_lead": "Kết hợp tín hiệu bản đồ, nội dung site và tùy theo tình trạng — nhận đề xuất ưu tiên trước khi mở rộng toàn tỉnh/thành.",
        "meta_description": "Dịch vụ SEO local: Google Business Profile, từ khóa địa phương, đánh giá, báo cáo cuộc gọi & chỉ đường. PTT Advertising Solutions, Việt Nam.",
    },
    "dich-vu-seo-audit": {
        "tagline": "Rà soát có thứ tự ưu tiên — biết cái gì cần sửa trước, vì sao, với ước lượng công sức",
        "overview": [
            "Audit phục vụ cả tình huống chuẩn bị đầu tư SEO, sau redesign, hợp nhất tên miền, hoặc khi tăng trưởng chững. Kết quả trình bày theo ưu tiên tác động, không dàn bảng lỗi dài mà hết ngân sách sửa.",
            "Bàn giao tài liệu có mục lục, bảng ưu tiên, gợi ý tự triển khai nội bộ hoặc bàn giao cho đội triển khai.",
        ],
        "stats": [
            {"value": "Ưu tiên", "label": "Bảng hành động theo tác động"},
            {"value": "Crawl", "label": "Index, cấu trúc, redirect, trùng lặp"},
            {"value": "On-page", "label": "Nội dung, nội bộ, meta cơ bản"},
        ],
        "pillars": [
            {
                "title": "Kỹ thuật thu thập & index",
                "body": "Phát hiện chặn crawl, sitemap, redirect dây, trùng nội dung, vấn đề canonical — ảnh hưởng trực tiếp đến việc trang xuất hiện trên tìm kiếm.",
            },
            {
                "title": "Chất lượng on-page từng mẫu trang",
                "body": "Mẫu sản phẩm, dịch vụ, blog, địa phương: tiêu đề, mô tả, heading, mật độ, internal link. Trùng lặp ý giữa các URL.",
            },
            {
                "title": "Lộ trình triển khai thực tế",
                "body": "Gợi ý tự sửa / outsource theo ưu tiên. Tách phần cần dev vs content để ước thời gian sát hơn.",
            },
        ],
        "outcomes": [
            "Một tài liệu duy nhất làm cơ sở ưu tiên nội bộ & đối tác kỹ thuật",
            "Giảm rủi ro triển khai cải tạo lớn mà thiếu cơ sở số",
        ],
        "deliverable_title": "Phạm vi audit & tài liệu bàn giao",
        "stats_section_title": "Các mảng rà soát",
        "pillars_section_title": "Phương pháp SEO Audit tại PTT",
        "outcomes_section_title": "Bạn sử dụng kết quả thế nào",
        "faq": [
            {
                "q": "Có cần truy cập Search Console / hosting?",
                "a": "Càng đầy đủ càng tốt. Một số mục cần quyền kỹ thuật để xác định chính xác, song chúng tôi cũng làm việc với dump crawl và tài khoản giới hạn nếu bạn cần tách quyền.",
            }
        ],
        "inline_cta": "Bạn cần audit tổng thể hay chỉ tập trung mảng kỹ thuật / nội dung? Ghi chú mục tiêu để nhận gói phù hợp.",
        "cta_wide_title": "Làm rõ ưu tiên sửa trước — hạn chế chi phí triển khai mù",
        "cta_wide_lead": "Nhận tài liệu audit, thảo luận phạm vi sửa nội bộ nếu cần — đề xuất sau khi xem tình trạng site thực tế.",
        "meta_description": "Dịch vụ SEO Audit: rà kỹ thuật, nội dung, ưu tiên hành động. Tài liệu bàn giao rõ ràng. PTT Advertising Solutions, Việt Nam.",
    },
    "dich-vu-quan-tri-website": {
        "tagline": "Vận hành ổn định, cập nhật định kỳ, bảo mật & sao lưu có kế hoạch",
        "overview": [
            "Website khi tắc bảo trì, lỗi cập nhật hoặc tấn công sẽ làm gián đoạn cả công sức marketing. Gói quản trị giúp bạn duy trì tần suất cập nhật, cảnh báo rủi ro, và tích hợp tag/form cơ bản theo từng mốc.",
            "Có thể gắn SLA theo từng mức: thời gian phản hồi, tần suất sao lưu, số nội dung/landing cần cập nhật trong tháng — tránh cảm giác 'tháng nào cũng hỏng giữa quảng cáo đang chạy'.",
        ],
        "stats": [
            {"value": "Backup", "label": "Lịch & kiểm tra phục hồi"},
            {"value": "An toàn", "label": "Cập nhật lõi, plugin, tường lửa cơ bản"},
            {"value": "Hỗ trợ", "label": "Tag, form, theo dõi cơ bản (theo gói)"},
        ],
        "pillars": [
            {
                "title": "Cập nhật có kế hoạch",
                "body": "Lịch cập nhật core/plugin, kiểm tra tương thích staging nếu cần, tránh cập nhật tự do ngày cao trương công.",
            },
            {
                "title": "Bảo mật & tốc độ cơ bản",
                "body": "Cấu hình tối thiểu, ẩn thông tin nhạy cảm, phát hiện sớm dấu hiệu tấn công phổ biến.",
            },
            {
                "title": "Phối hợp marketing",
                "body": "Gắn event cơ bản, form, pixel nếu thuộc gói — đảm bảo deploy không gãy cấu hình cũ.",
            },
        ],
        "outcomes": [
            "Giảm số sự cố cập nhật đột xuất ảnh hưởng quảng cáo/landing",
            "Tài khoản rõ mốc bàn giao log bảo trì, backup",
        ],
        "deliverable_title": "Hạng mục theo từng gói",
        "stats_section_title": "Trong phạm vi gói",
        "pillars_section_title": "Cách bảo trì website tại PTT",
        "outcomes_section_title": "Ổn định hạ tầng nền tảng",
        "faq": [
            {
                "q": "Có hỗ trợ tích hợp CRM, chat không?",
                "a": "Tùy mức kỹ thuật và quyền từ phía bên cung cấp chat/CRM. Chúng tôi ghi rõ nằm trong gói hay tính theo từng tích hợp.",
            }
        ],
        "inline_cta": "Bạn cần gói theo tần suất cập nhật, hay ưu tiên tốc độ xử lý sự cố? Ghi chú mô hình vận hành nội bộ.",
        "cta_wide_title": "Bảo vệ tài sản số: website luôn sẵn sàng khi cần chạy ads",
        "cta_wide_lead": "Nhận tư vấn mức gói phù hợp quy mô site và tần suất cập nhật thực tế — không cần ký gói tràn trước khi rõ nhu cầu.",
        "meta_description": "Dịch vụ quản trị & bảo trì website: cập nhật, bảo mật, sao lưu, hỗ trợ tích hợp cơ bản. PTT Advertising Solutions, Việt Nam.",
    },
    "thiet-ke-website": {
        "tagline": "Giao diện rõ, tốc độ tải, chuyển đổi trên từng màn hình",
        "overview": [
            "Thiết kế website không chỉ là màu sắc: là hệ thống cấp thông tin, kêu gọi hành động, và chuẩn kỹ thuật để Google thu thập, ads đo chuyển đổi, và nội dung lâu dài cập nhật dễ.",
            "PTT đồng bộ wireframe, UI, component với từng ngành, tránh mẫu dàn trên nhiều dự án. Chú trọng mobile và LCP, CLS cơ bản theo từng mức triển khai.",
        ],
        "stats": [
            {"value": "UI/UX", "label": "Wireframe, design system, brand"},
            {"value": "CWV", "label": "Hướng tốc độ & trải nghiệm tải cơ bản"},
            {"value": "Bàn giao", "label": "Tài liệu, hướng dẫn cập nhật nội dung"},
        ],
        "pillars": [
            {
                "title": "Làm rõ mục tiêu từng trang mẫu",
                "body": "Trang tổng, dịch vụ, sản phẩm, liên hệ, blog — từng mẫu một kịch bản hành động, không mọi trang đều cùng layout.",
            },
            {
                "title": "Thiết kế theo từng thiết bị thật",
                "body": "Kiểm tra trên kích thước màn, font, độ tương phản, form — giảm bỏ xót khi lên bản cắt.",
            },
            {
                "title": "Sẵn sàng tích hợp marketing",
                "body": "Khoảng cách cho form, sự kiện, pixel cơ bản, tránh cấu trúc khó cài đo chuyển đổi sau này.",
            },
        ],
        "outcomes": [
            "Bàn giao file & hướng dẫn giúp nội bộ/đối tác dev triển khai đúng",
            "Giảm xung đột thiết kế vs tốc độ vs hạ tầng nội dung bằng thống nhất sớm",
        ],
        "deliverable_title": "Hạng mục bàn giao thiết kế",
        "stats_section_title": "Hướng tối ưu",
        "pillars_section_title": "Cách thiết kế website tại PTT",
        "outcomes_section_title": "Sau khi bàn giao bạn kiểm soát gì",
        "faq": [
            {
                "q": "Có thi công (code) luôn không?",
                "a": "Có dự án tách thiết kế và dự án thi công. Chúng tôi ghi rõ phạm vi: chỉ hình, hay kèm triển khai theme/framework thỏa thuận.",
            }
        ],
        "inline_cta": "Bạn cần redesign hay website mới? Có tích hợp thương mại / booking không? Ghi mục tiêu để nhận bản ước lượng phù hợp.",
        "cta_wide_title": "Thiết kế website tôn trọng tốc độ & chuẩn tìm kiếm cơ bản",
        "cta_wide_lead": "Thảo luận ngành hàng, mục tiêu chuyển đổi, và tài liệu thương hiệu — nhận lộ trình thiết kế có mốc rõ ràng.",
        "meta_description": "Thiết kế website: UI/UX, chuẩn mobile, tốc độ cơ bản, bàn giao tài liệu. PTT Advertising Solutions, Việt Nam.",
    },
    "thiet-ke-website-tron-goi": {
        "tagline": "Một đầu mối: từ ý tưởng, nội dung, triển khai đến bàn giao & bảo hành giai đoạn",
        "overview": [
            "Gói trọn gói dành cho tổ chức cần cam kết mốc rõ, tránh tách bốn đầu mối (design, dev, host, nội dung) không cùng ngôn ngữ. Mỗi bước gắn với tài sản cần bàn giao: wireframe, design, cài đặt, tracking, go-live, hướng dẫn cập nhật.",
            "Tùy hợp đồng, có bảo hành sửa lỗi theo từng mày hoặc số tháng sau go-live — giảm tình trạng 'lên mạng rồi không ai sửa'.",
        ],
        "stats": [
            {"value": "Mốc", "label": "Thiết kế → tích hợp → go-live"},
            {"value": "Một hợp đồng", "label": "Phạm vi & ước lượng rõ từng bước"},
            {"value": "Bảo hành", "label": "Theo từng gói (khi thỏa thuận)"},
        ],
        "pillars": [
            {
                "title": "Phối hợp nội dung sớm",
                "body": "Tránh thi công mà còn thiếu nội dung chuẩn, gây trễ mốc. Có thể tách: doanh nghiệp cung cấp, hoặc PTT hỗ trợ soạn theo từng mức.",
            },
            {
                "title": "Dựng tích hợp, tracking, form",
                "body": "Form liên hệ, event, pixel/GA4 cơ bản, email — kiểm tra trên staging trước go-live thật.",
            },
            {
                "title": "Go-live & bảo hành theo mốc",
                "body": "Checklist DNS, SSL, redirect, 404, tốc độ cơ bản. Giai đoạn sau: hỗ trợ theo số tháng/gói.",
            },
        ],
        "outcomes": [
            "Rõ từng bên chịu trách nhiệm gì khi cần sửa sau go-live",
            "Tài sản: truy cập hosting/cpanel, mã, tài khoản tracking — tránh cô lập tài sản số",
        ],
        "deliverable_title": "Mốc bàn giao theo từng hạng mục",
        "stats_section_title": "Mô hình gói trọn gói",
        "pillars_section_title": "Quy trình thi công tại PTT",
        "outcomes_section_title": "Sau go-live bạn còn được hỗ trợ gì",
        "faq": [
            {
                "q": "Tôi đã có domain/hosting, có tính lại gói không?",
                "a": "Có. Trừ bớt mục tương ứng hoặc bạn giữ quyền quản trị — chúng tôi ghi rõ trên bảng phạm vi.",
            }
        ],
        "inline_cta": "Bạn ưu tiên lên nhanh hay chạy quảng cáo song song? Ghi cả deadline để ước mốc thực tế hơn.",
        "cta_wide_title": "Một bản ước lượng gắn mốc — không tách rời nội dung, kỹ thuật, go-live",
        "cta_wide_lead": "Nhận tư vấn phạm vi trọn gói: từ tài sản sẵn có đến mức tích hợp marketing cần cho giai đoạn đầu.",
        "meta_description": "Thiết kế website trọn gói: từ ý tưởng đến go-live, mốc rõ, bảo hành theo hợp đồng. PTT Advertising Solutions, Việt Nam.",
    },
    "thiet-ke-landing-page": {
        "tagline": "Một mục tiêu rõ, một trang đo được — phục vụ quảng cáo, ra mắt, lead",
        "overview": [
            "Landing tách khỏi trang tổng: nội dung ngắn, CTA mạnh, tốc độ tải ưu tiên, đồng bộ từng thông điệp với nhóm quảng cáo. Không cần 'đủ mọi tính năng' mà cần đo được chuyển đổi theo từng nguồn traffic.",
            "Có thể tích hợp A/B trên từng mức traffic; tag chuyển đổi, form, chat — tránh tình trạng cài pixel sai trên trang cũ/redirect khi cập nhật quảng cáo.",
        ],
        "stats": [
            {"value": "1 trang 1 mục tiêu", "label": "Form / gọi / chat ưu tiên rõ"},
            {"value": "Đo lường", "label": "Event, pixel, mapping conversion"},
            {"value": "A/B (tuỳ gói)", "label": "Khi đủ volume & cấu hình hợp lệ"},
        ],
        "pillars": [
            {
                "title": "Bám message quảng cáo & kênh",
                "body": "Tiêu đề, ưu đãi, thứ tự block — đồng bộ từng tệp, tránh tải traffic về trang còn tên sản phẩm/ưu đãi cũ.",
            },
            {
                "title": "Cấu trúc CTA & trust",
                "body": "Chứng nhận, số cảm nghiệm, câu hỏi thường gặp — tùy từng dự án, không dàn block giống nhau mọi ngành.",
            },
            {
                "title": "Bàn giao theo mốc media",
                "body": "Ưu tiên tốc độ lên theo lịch ads; staging kiểm tra sự kiện trước khi bật budget lớn.",
            },
        ],
        "outcomes": [
            "Cấu hình theo dõi chuyển đổi cùng team ads — giảm lệch số khi tối ưu",
            "Bản tối ưu theo từng đợt (ưu đãi, mùa, vùng) mà vẫn giữ tài sản cũ để tham chiếu",
        ],
        "deliverable_title": "Công việc cụ thể theo từng mốc hợp đồng",
        "stats_section_title": "Nguyên tắc landing",
        "pillars_section_title": "Thiết kế landing tại PTT",
        "outcomes_section_title": "Khi chạy quảng cáo, bạn kỳ vọng gì",
        "faq": [
            {
                "q": "Một trang dùng cho nhiều chiến dịch khác nội dung có được không?",
                "a": "Nên tách theo từng tệp/ưu đãi hoặc dùng query phân biệt để theo dõi. Dùng chung một nội dung mơ hồ thường kéo tỷ lệ lệch tệp/website.",
            }
        ],
        "inline_cta": "Bạn ưu tiên lead, gọi, hay bán hàng? Kênh chính Meta, Google, hay cả hai? Ghi mục tiêu để lên layout tương ứng.",
        "cta_wide_title": "Một trang tối ưu cho từng quảng cáo — hạn chế tối đa tải nặng dư",
        "cta_wide_lead": "Nhận đề xuất: phạm vi nội dung, thời gian, và tích hợp theo dõi trước khi tăng ngân sách.",
        "meta_description": "Thiết kế landing page: tối ưu chuyển đổi, theo dõi quảng cáo, bàn giao nhanh. PTT Advertising Solutions, Việt Nam.",
    },
    "quang-cao-facebook": {
        "tagline": "Meta: Facebook, Instagram — từ tài khoản, pixel, cho đến tối ưu tệp & creative theo từng mục tiêu",
        "overview": [
            "Chạy quảng cáo Meta không dừng ở 'bật campaign': cần tài khoản, catalog/sự kiện, pixel (hoặc CAPI) đo đúng, và vòng tối ưu tệp, giá mỗi chuyển đổi, creative. Nếu website chậm / landing thiếu tính nhất quán, ngân sách dễ tốn mà tín hiệu lệch khi scale.",
            "PTT cấu trúc tài khoản, đặt tên theo từng bài học, báo cáo dễ đọc, và tư vấn cập nhật nội dung/landing cùng với tần tối ưu.",
        ],
        "stats": [
            {"value": "Funnel", "label": "Nhận thức → cân nhắc → chuyển đổi (theo từng dự án)"},
            {"value": "Pixel / CAPI", "label": "Cấu hình theo từng mức theo dõi cần thiết"},
            {"value": "Creative", "label": "Gợi ý tối ưu theo từng giai đoạn tệp"},
        ],
        "pillars": [
            {
                "title": "Cấu trúc tài khoản & tên đo được",
                "body": "Tách từng mục tiêu, từng sản phẩm, từng thị trường nếu cần. Tránh gộp hết khiến tối ưu bị rối tín hiệu.",
            },
            {
                "title": "Tệp, creative, tối ưu theo từng mốc",
                "body": "Phân tích tệp, loại bỏ trùng, cập nhật theo từng giai đoạn sale/sản phẩm. Giải thích phần tự nhiên do thuật toán, phần cần can thiệp sáng tạo.",
            },
            {
                "title": "Báo cáo & cải tiến hàng tuần",
                "body": "Tóm tắt chi phí, từng tệp, từng bài, đề xuất điều chỉnh budget, creative, landing. Phối hợp với SEO/nội dung nếu cùng câu chuyện sản phẩm.",
            },
        ],
        "outcomes": [
            "Hiểu rõ phần ngân sách đang đổ về tệp, creative, hay cấu hình tài khoản kém",
            "Giảm thách thức theo dõi chuyển đổi bằng cấu hình pixel/CAPI tương xứng sản phẩm/website thực tế",
        ],
        "deliverable_title": "Phạm vi thực hiện & tần suất báo cáo",
        "stats_section_title": "Trong phạm vi dự án",
        "pillars_section_title": "Cách vận hành quảng cáo Meta tại PTT",
        "outcomes_section_title": "KPI thường cùng thống nhất",
        "faq": [
            {
                "q": "Có tối ưu video / catalog không?",
                "a": "Có, nếu sản phẩm, feed catalog và tài sản cần từ phía bạn. Chúng tôi ghi rõ phạm vi kỹ thuật feed.",
            }
        ],
        "inline_cta": "Bạn ưu tiên ROAS, lead, hay traffic? Catalog hay lead form? Ghi tóm tắt để gợi cấu trúc tài khoản sơ bộ.",
        "cta_wide_title": "Tăng tác động từ quảng cáo Facebook/Instagram, không chỉ tăng bật mức ngân sách",
        "cta_wide_lead": "Nhận tư vấn: cấu hình, tệp, creative, và tài sản landing cùng đồng bộ từng đợt.",
        "meta_description": "Dịch vụ chạy quảng cáo Facebook & Instagram: tài khoản, pixel, tệp, creative, báo cáo. PTT Advertising Solutions, Việt Nam.",
    },
    "quang-cao-google": {
        "tagline": "Tìm kiếm, hiển thị, Performance Max, Shopping — cấu trúc tài khoản theo từng mục tiêu & ngành hàng",
        "overview": [
            "Hệ thống Google Ads đa dạng loại chiến dịch; chọn sai cấu trúc, từ khóa, feed hoặc mục quảng cáo sẽ khiến tối ưu tốn công. Chúng tôi ưu tiên: đo lường trước (conversion, tên biến thể), từ khóa & loại trừ, tài sản hiển thị, dữ liệu sản phẩm nếu Shopping/PMax, và tốc độ landing.",
            "Báo cáo: chi phí, từng nguồn, từng nhóm từ khóa/sản phẩm, đề xuất tăng / giảm theo từng mốc, không cầu kỳ biểu đồ mà cần quyết định sửa gì mỗi tuần.",
        ],
        "stats": [
            {"value": "Cấu trúc", "label": "Tài khoản, tên, ngân sách, giá thầu theo từng tầng mục tiêu"},
            {"value": "Chuyển đổi", "label": "Gắn đo, loại bỏ trùng, feed (nếu cần)"},
            {"value": "Báo cáo", "label": "Theo từng mốc thống nhất với bạn"},
        ],
        "pillars": [
            {
                "title": "Cấu trúc tài khoản rõ, đồng bộ tên biến thể",
                "body": "Tránh tạo 10 nhóm giống cạnh cạnh; gom theo từng sản phẩm, vùng, hoặc mục tiêu chuyển đổi. Loại từ khóa, trang đích, feed — tránh ăn budget chéo.",
            },
            {
                "title": "Từ khóa, creative, tài sản tìm & hiển thị",
                "body": "Cập nhật từ khóa, ad copy, tài sản, feed theo từng mùa hàng, thay đổi chính sách website.",
            },
            {
                "title": "Tối ưu giá mỗi chuyển đổi / ROAS theo từng mục",
                "body": "Không tối ưu tất cả mục tiêu cùng hệ số. Chia rõ: kênh tìm, remarketing, thương hiệu, PMax/Shopping — mỗi cái một giới hạn ngân sách hợp lý.",
            },
        ],
        "outcomes": [
            "Hạn chế lãng phí click không đúng ý định nhờ từ loại trừ & tên biến thể cập nhật",
            "Rõ hơn phần do landing yếu vs phần do cài đo / tài khoản cần sửa",
        ],
        "deliverable_title": "Công việc & tần suất tối ưu",
        "stats_section_title": "Hướng tối ưu",
        "pillars_section_title": "Quy trình quảng cáo Google tại PTT",
        "outcomes_section_title": "Mục tiêu & KPI cùng thống nhất",
        "faq": [
            {
                "q": "Một tài khoản hay nhiều tài khoản?",
                "a": "Tùy tổ chức, thương hiệu, mức ngân sách, và tách công tác. Chúng tôi tư vấn theo nhu cầu thật, không tách tài khoản mù.",
            }
        ],
        "inline_cta": "Bạn ưu tiên search, PMax, hay shopping? ROAS tối thiểu hay volume lead? Tóm tắt để gợi cấu trúc tài khoản.",
        "cta_wide_title": "Hợp lý hóa từng kênh trả phí, không tối ưu dàn giống nhau mọi ngành hàng",
        "cta_wide_lead": "Nhận thảo luận: feed, từ khóa, sản phẩm, và tài sản web phục vụ từng loại quảng cáo.",
        "meta_description": "Dịch vụ quảng cáo Google: Search, PMax, Shopping, tối ưu tài khoản & chuyển đổi. PTT Advertising Solutions, Việt Nam.",
    },
    "thue-tai-khoan-quang-cao": {
        "tagline": "Hợp đồng rõ, minh bạch chi phí, hành vi kinh doanh theo hướng bền lâu theo từng nền tảng",
        "overview": [
            "Cho thuê / dùng tài khoản quảng cáo cần minh bạch quyền, phí, trách nhiệm mỗi bên, và tôn trọng chính sách từng nền tảng. Mục tiêu là hạn chế gián đoạn, khoá, hoặc mất tài sản tích lũy tệ/creative theo từng tài khoản.",
            "PTT ưu tiên làm rõ: phạm vi, quy tắc cập nhật thông tin doanh nghiệp, thanh toán, và báo cáo. Không tư vấn cách bám vi phạm gây mất tài sản số dài hạn — kể cả 'chạy nhanh' ngắn hạn gây rủi ro khoá thanh toán tập trung.",
        ],
        "stats": [
            {"value": "Hợp đồng", "label": "Rõ thời hạn, quyền, phí, cách tách tài sản dữ liệu"},
            {"value": "Báo cáo", "label": "Chi phí theo từng tháng / chiến dịch (theo thỏa thuận)"},
            {"value": "Tuân thủ", "label": "Hành vi quảng cáo, thanh toán, thông tin doanh nghiệp hợp lệ"},
        ],
        "pillars": [
            {
                "title": "Khai báo mục sử dụng rõ từ đầu",
                "body": "Ngành, thị trường, mức ngân sách, loại tài sản. Tránh tình trạng tài khoản tích lũy tệp kém phù hợp ngành thật dẫn tới tối ưu khó.",
            },
            {
                "title": "Phối hợp cấu hình, thanh toán, tài sản tích hợp",
                "body": "Cấp quyền, pixel, tài sản, catalog — tách trách nhiệm: ai tạo, ai duy trì, khi kết hợp tài sản cần tách ra sao.",
            },
            {
                "title": "Chính sách nền tảng & cập nhật theo từng mùa",
                "body": "Theo dõi thông báo từng nền tảng, cập nhật thông tin doanh nghiệp, tài sản, tránh tự ý tạo mục cấm.",
            },
        ],
        "outcomes": [
            "Giảm bất ổn tài sản: quyền, tài sản, và chi phí minh bạch hơn theo từng mốc",
        ],
        "deliverable_title": "Hạng mục theo từng bản hợp đồng",
        "stats_section_title": "Nguyên tắc hợp tác",
        "pillars_section_title": "Cách tiếp cận dịch vụ tài khoản",
        "outcomes_section_title": "Kỳ vọng thực tế từ góc độ tài sản số & rủi ro nền tảng",
        "faq": [
            {
                "q": "Có bảo đảm không bị tạm ngưng không?",
                "a": "Không ai cam kết tuyệt đối vì quyền hạn thuộc từng nền tảng. Chúng tôi ưu tiên khai thật, minh bạch, và phản ứng sớm theo từng cảnh báo khi cấu hình cho phép.",
            }
        ],
        "inline_cta": "Bạn cần tài khoản cho từng nền nào, mức volume dự kiến? Ghi rõ để ước mức hợp tác tương ứng.",
        "cta_wide_title": "Làm rõ pháp lý, phí, tài sản thuê — hạn chế khoá, hạn chế mâu thuẫn sau 3 tháng",
        "cta_wide_lead": "Nhận tư vấn theo từng tình huống: tài sản, ngành, và nền tảng dự dùng — không tư vấn chạy xám trái hướng bền lâu.",
        "meta_description": "Dịch vụ cho thuê / hợp tác tài khoản quảng cáo: minh bạch, hợp đồng, báo cáo. PTT Advertising Solutions, Việt Nam.",
    },
    "tiep-thi-noi-dung": {
        "tagline": "Kế hoạch sản xuất & lịch phát hành theo từng hành trình, không cần tạo tức số lượng bài tách rời SEO/ads",
        "overview": [
            "Tiếp thị nội dung cần cả chiến lược (câu chuyện, persona, từng bước hành trình) và sản xuất (bài sâu, bài cập nhật, social, tài liệu). Tách khỏi từ khoá: nội dung phải phục vụ tín hiệu tìm kiếm, tính đọc, và chuyển đổi khi cần phối hợp quảng cáo/landing.",
            "Có thể tích hợp cùng SEO, AEO, quảng cáo — cùng một câu chuyện sản phẩm, cập nhật từng mùa, từng ưu đãi, tránh tình trạng bài cũ ăn cả tệp ads mới chạy.",
        ],
        "stats": [
            {"value": "Lịch", "label": "Theo từng mảng: web, social, tài liệu"},
            {"value": "Sâu & cập nhật", "label": "Bài cột, bài cập nhật, case"},
            {"value": "Tích hợp", "label": "SEO / AEO / ads khi cùng dự án"},
        ],
        "pillars": [
            {
                "title": "Rõ từng mục tiêu: nhận diện, lead, nuôi dưỡng, chốt",
                "body": "Lịch từng tháng theo ưu tiên sản phẩm, sự kiện, ưu đãi. Không dàn 20 bài chung tính từ ngày hình thức.",
            },
            {
                "title": "E-E-A-T theo từng lĩnh (khi cần)",
                "body": "Chuyên gia, tài liệu, trích dẫn, case — tùy ngành, đặc biệt y tế, tài chính, công nghiệp, tránh nội dung cộng tác viên mơ hồ.",
            },
            {
                "title": "Đo tín hiệu, không đo hết bằng lượt thích",
                "body": "Kết hợp: traffic, thời gian trang, từ khóa, form, tương tác, tuỳ mục. Điều chỉnh tần hình thức từng mảng theo từng mốc.",
            },
        ],
        "outcomes": [
            "Bộ tài sản nội dung có tên, từng cột, dễ chuyển hóa cho sales/CS",
            "Phối hợp ổn hơn với SEO & ads cùng thông điệp",
        ],
        "deliverable_title": "Công việc sản xuất & tần suất",
        "stats_section_title": "Hướng tích hợp",
        "pillars_section_title": "Cách PTT lập kế hoạch nội dung",
        "outcomes_section_title": "Sau 3—6 tháng thường cải thiện gì",
        "faq": [
            {
                "q": "Có tự cung cấp writer không?",
                "a": "Có, hoặc PTT cung ứng theo từng mức, có proofreading/chỉnh sửa. Chúng tôi ghi rõ trên bảng phạm vi.",
            }
        ],
        "inline_cta": "Bạn cần bài cột sâu, bài tần cập nhật, hay cả tài liệu nội bộ? Tóm tắt kênh chính.",
        "cta_wide_title": "Nội dung ăn theo từng mục tiêu kinh doanh — không chỉ số bài theo tháng",
        "cta_wide_lead": "Nhận tư vấn: từng mảng, tần, và cách tích hợp với tìm kiếm & quảng cáo nếu cùng thương hiệu.",
        "meta_description": "Dịch vụ tiếp thị nội dung: kế hoạch, sản xuất, tích hợp SEO & quảng cáo. PTT Advertising Solutions, Việt Nam.",
    },
}
# fmt: on
