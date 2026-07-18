# Risk Management — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi lifecycle có risk registry (seeded từ fixed list per service + AM thêm custom) và nút AI Scan cảnh báo TOP 3 rủi ro cấp bách dựa trên giai đoạn hiện tại.

**Architecture:** 2 module Python mới (`crm_svc_risk_registry.py` — data-only, `crm_svc_risk.py` — schema + logic), 5 routes mới + cập nhật 1 route hiện có trong `app.py`, thêm risk section vào template `crm_service_workflow.html`.

**Tech Stack:** Flask 3 monolith, SQLite (`get_connection()`), Anthropic SDK trực tiếp (`claude-haiku-4-5-20251001`), Jinja2 + Vanilla JS.

## Global Constraints

- Working directory: `/Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP`
- Auth pattern mọi page route: `redir = _ensure_admin_session_html(); if redir: return redir`
- DB: `with get_connection() as conn:` — không dùng `conn.close()` thủ công
- Timestamps: `datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")`
- AI model: `claude-haiku-4-5-20251001`, synchronous, fail silent (return `""`)
- Tests: `unittest.TestCase` + SQLite in-memory + `conn.row_factory = sqlite3.Row`
- `seed_risks` idempotent: check `COUNT(*) WHERE is_custom=0` trước khi seed
- `delete_risk` chỉ xoá `is_custom=1`, returns `bool`
- `probability` và `impact` values: `'cao'`, `'trung'`, `'thap'`
- Phase 1 đã tồn tại: `crm_svc_workflow_steps.py`, `crm_svc_tasks.py`, `crm_svc_risk.py` chưa tồn tại
- `crm_service_workflow_page` route đã có ở app.py — cần cập nhật để seed risks + pass chúng vào template

---

### Task 1: crm_svc_risk_registry.py — Risk data + AI prompt

**Files:**
- Create: `crm_svc_risk_registry.py`

**Interfaces:**
- Produces: `SERVICE_RISK_REGISTRY: dict[str, list[dict]]` — key là service_slug, value là list `{stage, title, category, probability, impact, mitigation}`
- Produces: `AI_RISK_SCAN_PROMPT: str` — prompt template với placeholders `{service_name}`, `{customer_name}`, `{current_stage}`, `{progress_summary}`, `{risks_list}`

- [ ] **Step 1: Tạo file**

```python
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
```

- [ ] **Step 2: Verify import OK**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -c "
from crm_svc_risk_registry import SERVICE_RISK_REGISTRY, AI_RISK_SCAN_PROMPT
total = sum(len(v) for v in SERVICE_RISK_REGISTRY.values())
print(len(SERVICE_RISK_REGISTRY), 'services,', total, 'risks')
print('Prompt placeholders OK:', all(p in AI_RISK_SCAN_PROMPT for p in ['{service_name}','{customer_name}','{current_stage}','{risks_list}']))
"
```

Expected: `12 services, 40 risks` (hoặc gần đó) và `Prompt placeholders OK: True`

---

### Task 2: crm_svc_risk.py + tests/test_crm_svc_risk.py (TDD)

**Files:**
- Create: `crm_svc_risk.py`
- Create: `tests/test_crm_svc_risk.py`

**Interfaces:**
- Consumes: `crm_svc_risk_registry.SERVICE_RISK_REGISTRY`, `crm_svc_risk_registry.AI_RISK_SCAN_PROMPT`
- Produces:
  - `ensure_schema(conn: sqlite3.Connection) -> None`
  - `seed_risks(conn, lifecycle_id: int, service_slug: str) -> int`
  - `list_risks(conn, lifecycle_id: int) -> list[dict]`
  - `update_risk(conn, risk_id: int, *, probability=None, impact=None, mitigation=None, is_active=None) -> None`
  - `create_custom_risk(conn, lifecycle_id: int, stage: str, title: str, category: str = "") -> int`
  - `delete_risk(conn, risk_id: int) -> bool`
  - `get_latest_scan(conn, lifecycle_id: int) -> str`
  - `run_ai_risk_scan(conn, lifecycle_id: int, customer_context: dict) -> str`

- [ ] **Step 1: Viết tests (failing)**

```python
# tests/test_crm_svc_risk.py
"""Tests cho crm_svc_risk module."""
from __future__ import annotations

import sqlite3
import unittest

from crm_svc_risk import (
    create_custom_risk,
    delete_risk,
    ensure_schema,
    get_latest_scan,
    list_risks,
    seed_risks,
    update_risk,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
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
        VALUES (1, 'dich-vu-seo-tong-the', 'deliver', 'active',
                '2026-06-23 00:00:00', '2026-06-23 00:00:00', '2026-06-23 00:00:00')
    """)
    conn.commit()
    ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_tables_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_svc_risks", tables)
        self.assertIn("crm_svc_risk_scans", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        ensure_schema(conn)
        ensure_schema(conn)


class TestSeedRisks(unittest.TestCase):
    def test_seeds_correct_count(self):
        conn = _setup_conn()
        count = seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertGreater(count, 0)
        db_count = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_risks WHERE lifecycle_id = 1"
        ).fetchone()[0]
        self.assertEqual(db_count, count)

    def test_idempotent(self):
        conn = _setup_conn()
        count1 = seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        count2 = seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertGreater(count1, 0)
        self.assertEqual(count2, 0)

    def test_unknown_slug_returns_zero(self):
        conn = _setup_conn()
        self.assertEqual(seed_risks(conn, lifecycle_id=1, service_slug="nonexistent"), 0)

    def test_seeded_risks_are_active(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rows = conn.execute(
            "SELECT is_active FROM crm_svc_risks WHERE lifecycle_id = 1"
        ).fetchall()
        self.assertTrue(all(r["is_active"] == 1 for r in rows))

    def test_seeded_are_not_custom(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rows = conn.execute(
            "SELECT is_custom FROM crm_svc_risks WHERE lifecycle_id = 1"
        ).fetchall()
        self.assertTrue(all(r["is_custom"] == 0 for r in rows))


class TestListRisks(unittest.TestCase):
    def test_returns_list(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        risks = list_risks(conn, lifecycle_id=1)
        self.assertIsInstance(risks, list)
        self.assertGreater(len(risks), 0)

    def test_empty_lifecycle_returns_empty(self):
        conn = _setup_conn()
        self.assertEqual(list_risks(conn, lifecycle_id=999), [])

    def test_risk_has_required_fields(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        risk = list_risks(conn, lifecycle_id=1)[0]
        for field in ["id", "lifecycle_id", "stage", "title", "category",
                      "probability", "impact", "mitigation", "is_active", "is_custom"]:
            self.assertIn(field, risk, f"Missing field: {field}")

    def test_active_risks_listed_first(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        first_id = conn.execute(
            "SELECT id FROM crm_svc_risks WHERE lifecycle_id = 1 LIMIT 1"
        ).fetchone()["id"]
        update_risk(conn, first_id, is_active=False)
        risks = list_risks(conn, lifecycle_id=1)
        # Active risks should come before resolved ones
        active_statuses = [r["is_active"] for r in risks]
        self.assertEqual(active_statuses, sorted(active_statuses, reverse=True))


class TestUpdateRisk(unittest.TestCase):
    def _seed_and_get_id(self, conn):
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        return conn.execute(
            "SELECT id FROM crm_svc_risks WHERE lifecycle_id = 1 LIMIT 1"
        ).fetchone()["id"]

    def test_update_probability(self):
        conn = _setup_conn()
        rid = self._seed_and_get_id(conn)
        update_risk(conn, rid, probability="thap")
        row = conn.execute(
            "SELECT probability FROM crm_svc_risks WHERE id = ?", (rid,)
        ).fetchone()
        self.assertEqual(row["probability"], "thap")

    def test_update_impact(self):
        conn = _setup_conn()
        rid = self._seed_and_get_id(conn)
        update_risk(conn, rid, impact="thap")
        row = conn.execute(
            "SELECT impact FROM crm_svc_risks WHERE id = ?", (rid,)
        ).fetchone()
        self.assertEqual(row["impact"], "thap")

    def test_resolve_risk(self):
        conn = _setup_conn()
        rid = self._seed_and_get_id(conn)
        update_risk(conn, rid, is_active=False)
        row = conn.execute(
            "SELECT is_active FROM crm_svc_risks WHERE id = ?", (rid,)
        ).fetchone()
        self.assertEqual(row["is_active"], 0)

    def test_reactivate_risk(self):
        conn = _setup_conn()
        rid = self._seed_and_get_id(conn)
        update_risk(conn, rid, is_active=False)
        update_risk(conn, rid, is_active=True)
        row = conn.execute(
            "SELECT is_active FROM crm_svc_risks WHERE id = ?", (rid,)
        ).fetchone()
        self.assertEqual(row["is_active"], 1)

    def test_update_mitigation(self):
        conn = _setup_conn()
        rid = self._seed_and_get_id(conn)
        update_risk(conn, rid, mitigation="Plan B mới")
        row = conn.execute(
            "SELECT mitigation FROM crm_svc_risks WHERE id = ?", (rid,)
        ).fetchone()
        self.assertEqual(row["mitigation"], "Plan B mới")


class TestCustomRisk(unittest.TestCase):
    def test_create_custom_risk(self):
        conn = _setup_conn()
        rid = create_custom_risk(
            conn, lifecycle_id=1, stage="deliver", title="Rủi ro tuỳ chỉnh"
        )
        self.assertIsInstance(rid, int)
        row = conn.execute(
            "SELECT * FROM crm_svc_risks WHERE id = ?", (rid,)
        ).fetchone()
        self.assertEqual(row["is_custom"], 1)
        self.assertEqual(row["title"], "Rủi ro tuỳ chỉnh")
        self.assertEqual(row["is_active"], 1)
        self.assertEqual(row["probability"], "trung")
        self.assertEqual(row["impact"], "trung")

    def test_delete_custom_risk(self):
        conn = _setup_conn()
        rid = create_custom_risk(
            conn, lifecycle_id=1, stage="deliver", title="Xoá đi"
        )
        self.assertTrue(delete_risk(conn, rid))
        self.assertIsNone(
            conn.execute(
                "SELECT id FROM crm_svc_risks WHERE id = ?", (rid,)
            ).fetchone()
        )

    def test_cannot_delete_template_risk(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rid = conn.execute(
            "SELECT id FROM crm_svc_risks WHERE is_custom = 0 LIMIT 1"
        ).fetchone()["id"]
        self.assertFalse(delete_risk(conn, rid))

    def test_delete_nonexistent_returns_false(self):
        conn = _setup_conn()
        self.assertFalse(delete_risk(conn, 99999))


class TestGetLatestScan(unittest.TestCase):
    def test_no_scan_returns_empty_string(self):
        conn = _setup_conn()
        self.assertEqual(get_latest_scan(conn, lifecycle_id=1), "")

    def test_returns_latest_not_first(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_risk_scans (lifecycle_id, ai_output, created_at) "
            "VALUES (1, 'scan cũ', '2026-06-23 08:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_risk_scans (lifecycle_id, ai_output, created_at) "
            "VALUES (1, 'scan mới nhất', '2026-06-23 09:00:00')"
        )
        conn.commit()
        self.assertEqual(get_latest_scan(conn, lifecycle_id=1), "scan mới nhất")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy tests — expect FAIL**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -m pytest tests/test_crm_svc_risk.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'crm_svc_risk'`

- [ ] **Step 3: Implement crm_svc_risk.py**

```python
# crm_svc_risk.py
"""Risk management per-lifecycle cho 12 dịch vụ PTTP."""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)
_HAIKU = "claude-haiku-4-5-20251001"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_risks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            stage        TEXT NOT NULL DEFAULT '',
            title        TEXT NOT NULL DEFAULT '',
            category     TEXT NOT NULL DEFAULT '',
            probability  TEXT NOT NULL DEFAULT 'trung',
            impact       TEXT NOT NULL DEFAULT 'trung',
            mitigation   TEXT NOT NULL DEFAULT '',
            is_active    INTEGER NOT NULL DEFAULT 1,
            is_custom    INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_risks_lifecycle ON crm_svc_risks(lifecycle_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_risk_scans (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            ai_output    TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()


def seed_risks(
    conn: sqlite3.Connection, lifecycle_id: int, service_slug: str
) -> int:
    from crm_svc_risk_registry import SERVICE_RISK_REGISTRY
    existing = conn.execute(
        "SELECT COUNT(*) FROM crm_svc_risks WHERE lifecycle_id = ? AND is_custom = 0",
        (lifecycle_id,),
    ).fetchone()[0]
    if existing > 0:
        return 0
    risks = SERVICE_RISK_REGISTRY.get(service_slug, [])
    ts = _ts()
    for risk in risks:
        conn.execute(
            """
            INSERT INTO crm_svc_risks
                (lifecycle_id, stage, title, category, probability, impact,
                 mitigation, is_active, is_custom, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
            """,
            (
                lifecycle_id,
                risk.get("stage", ""),
                risk["title"],
                risk.get("category", ""),
                risk.get("probability", "trung"),
                risk.get("impact", "trung"),
                risk.get("mitigation", ""),
                ts, ts,
            ),
        )
    conn.commit()
    return len(risks)


def list_risks(
    conn: sqlite3.Connection, lifecycle_id: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM crm_svc_risks
        WHERE lifecycle_id = ?
        ORDER BY is_active DESC, impact DESC, probability DESC, id
        """,
        (lifecycle_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_risk(
    conn: sqlite3.Connection,
    risk_id: int,
    *,
    probability: str | None = None,
    impact: str | None = None,
    mitigation: str | None = None,
    is_active: bool | None = None,
) -> None:
    ts = _ts()
    sets = ["updated_at = ?"]
    params: list[Any] = [ts]
    if probability is not None:
        sets.append("probability = ?")
        params.append(probability)
    if impact is not None:
        sets.append("impact = ?")
        params.append(impact)
    if mitigation is not None:
        sets.append("mitigation = ?")
        params.append(mitigation[:2000])
    if is_active is not None:
        sets.append("is_active = ?")
        params.append(1 if is_active else 0)
    params.append(risk_id)
    conn.execute(
        f"UPDATE crm_svc_risks SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()


def create_custom_risk(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    stage: str,
    title: str,
    category: str = "",
) -> int:
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_svc_risks
            (lifecycle_id, stage, title, category, probability, impact,
             mitigation, is_active, is_custom, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'trung', 'trung', '', 1, 1, ?, ?)
        """,
        (lifecycle_id, stage, title[:500], category[:100], ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def delete_risk(conn: sqlite3.Connection, risk_id: int) -> bool:
    row = conn.execute(
        "SELECT is_custom FROM crm_svc_risks WHERE id = ?", (risk_id,)
    ).fetchone()
    if row is None or not row["is_custom"]:
        return False
    conn.execute("DELETE FROM crm_svc_risks WHERE id = ?", (risk_id,))
    conn.commit()
    return True


def get_latest_scan(conn: sqlite3.Connection, lifecycle_id: int) -> str:
    row = conn.execute(
        "SELECT ai_output FROM crm_svc_risk_scans "
        "WHERE lifecycle_id = ? ORDER BY id DESC LIMIT 1",
        (lifecycle_id,),
    ).fetchone()
    return row["ai_output"] if row else ""


def run_ai_risk_scan(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    customer_context: dict,
) -> str:
    from crm_svc_risk_registry import AI_RISK_SCAN_PROMPT
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    active_risks = [r for r in list_risks(conn, lifecycle_id) if r["is_active"]]
    if not active_risks:
        return ""
    risk_lines = "\n".join(
        f"- [{r['stage'] or 'tổng'}/{r['category']}] {r['title']} "
        f"(xác suất: {r['probability']}, ảnh hưởng: {r['impact']})"
        for r in active_risks
    )
    ctx = {
        "service_name": customer_context.get("service_name", ""),
        "customer_name": customer_context.get("customer_name", "KH"),
        "current_stage": customer_context.get("current_stage", ""),
        "progress_summary": customer_context.get("progress_summary", ""),
        "risks_list": risk_lines,
    }
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=600,
            messages=[{"role": "user", "content": AI_RISK_SCAN_PROMPT.format(**ctx)}],
        )
        output = response.content[0].text.strip()
        conn.execute(
            "INSERT INTO crm_svc_risk_scans (lifecycle_id, ai_output, created_at) "
            "VALUES (?, ?, ?)",
            (lifecycle_id, output, _ts()),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_risk_scan lỗi lifecycle_id=%s: %s", lifecycle_id, exc)
        return ""
```

- [ ] **Step 4: Chạy tests — expect PASS**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -m pytest tests/test_crm_svc_risk.py -v
```

Expected: All tests PASS. Nếu fail → fix trước khi tiếp tục.

---

### Task 3: Wire app.py — init schema + 5 routes + cập nhật crm_service_workflow_page

**Files:**
- Modify: `app.py` — thêm import, init schema, 5 routes mới, cập nhật `crm_service_workflow_page`

**Interfaces:**
- Consumes: `crm_svc_risk.ensure_schema`, `seed_risks`, `list_risks`, `update_risk`, `create_custom_risk`, `delete_risk`, `get_latest_scan`, `run_ai_risk_scan`
- Consumes existing: `get_connection`, `_opt_pos_int`, `jsonify`, `request`, `render_template`
- The existing function `crm_service_workflow_page` (Phase 1) cần được cập nhật để seed risks và pass chúng vào template

- [ ] **Step 1: Thêm import vào app.py**

Tìm dòng (khoảng 332–333, ngay sau import crm_svc_tasks):
```python
from crm_svc_tasks import ensure_schema as _ensure_svc_tasks_schema
```

Thêm ngay sau:
```python
from crm_svc_risk import ensure_schema as _ensure_svc_risk_schema
```

- [ ] **Step 2: Thêm schema init vào init section**

Tìm dòng (khoảng 2273–2274):
```python
        _ensure_svc_tasks_schema(conn)
```

Thêm ngay sau:
```python
        _ensure_svc_risk_schema(conn)
```

- [ ] **Step 3: Cập nhật crm_service_workflow_page để seed risks**

Tìm `crm_service_workflow_page` trong app.py. Trong phần `with get_connection() as conn:`, thêm sau dòng `_svc_seed(...)`:

```python
        # Seed và load risks
        from crm_svc_risk import (
            seed_risks as _risk_seed,
            list_risks as _risk_list,
            get_latest_scan as _risk_latest_scan,
        )
        _risk_seed(conn, lifecycle_id=lifecycle_id, service_slug=lc["service_slug"])
        risks = _risk_list(conn, lifecycle_id=lifecycle_id)
        latest_risk_scan = _risk_latest_scan(conn, lifecycle_id=lifecycle_id)
```

Và thêm vào `render_template(...)`:
```python
        risks=risks,
        latest_risk_scan=latest_risk_scan,
```

- [ ] **Step 4: Thêm 5 routes mới vào app.py — sau nhóm routes svc-tasks**

Tìm `api_svc_task_ai_assist` (route cuối của Phase 1) và thêm sau nó:

```python
# ── Service Risk Management ──────────────────────────────────────────────────

@app.get("/api/crm/svc-risks/<int:lifecycle_id>")
def api_svc_risks_list(lifecycle_id: int) -> Any:
    from crm_svc_risk import list_risks as _risk_list, get_latest_scan as _risk_scan
    with get_connection() as conn:
        risks = _risk_list(conn, lifecycle_id)
        latest_scan = _risk_scan(conn, lifecycle_id)
    return jsonify({"risks": risks, "latest_scan": latest_scan})


@app.patch("/api/crm/svc-risks/<int:risk_id>")
def api_svc_risk_patch(risk_id: int) -> Any:
    from crm_svc_risk import update_risk as _risk_update
    payload = request.get_json(force=True) or {}
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM crm_svc_risks WHERE id = ?", (risk_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Không tìm thấy risk"}), 404
        _risk_update(
            conn, risk_id,
            probability=str(payload["probability"]) if "probability" in payload else None,
            impact=str(payload["impact"]) if "impact" in payload else None,
            mitigation=str(payload["mitigation"])[:2000] if "mitigation" in payload else None,
            is_active=bool(payload["is_active"]) if "is_active" in payload else None,
        )
        updated = conn.execute(
            "SELECT * FROM crm_svc_risks WHERE id = ?", (risk_id,)
        ).fetchone()
    return jsonify(dict(updated))


@app.post("/api/crm/svc-risks")
def api_svc_risk_create() -> Any:
    from crm_svc_risk import create_custom_risk as _risk_create
    payload = request.get_json(force=True) or {}
    lifecycle_id = _opt_pos_int(payload.get("lifecycle_id"))
    title = str(payload.get("title", "")).strip()[:500]
    stage = str(payload.get("stage", "")).strip()
    category = str(payload.get("category", "")).strip()[:100]
    if not lifecycle_id or not title:
        return jsonify({"error": "Cần lifecycle_id và title"}), 400
    with get_connection() as conn:
        rid = _risk_create(
            conn, lifecycle_id=lifecycle_id, stage=stage, title=title, category=category
        )
        row = conn.execute("SELECT * FROM crm_svc_risks WHERE id = ?", (rid,)).fetchone()
    return jsonify(dict(row)), 201


@app.delete("/api/crm/svc-risks/<int:risk_id>")
def api_svc_risk_delete(risk_id: int) -> Any:
    from crm_svc_risk import delete_risk as _risk_delete
    with get_connection() as conn:
        ok = _risk_delete(conn, risk_id)
    if not ok:
        return jsonify({"error": "Không thể xoá — không phải custom risk"}), 404
    return jsonify({"ok": True})


@app.post("/api/crm/svc-risks/<int:lifecycle_id>/ai-scan")
def api_svc_risk_ai_scan(lifecycle_id: int) -> Any:
    from crm_svc_risk import run_ai_risk_scan as _risk_scan_fn
    from crm_svc_tasks import SERVICE_LABELS as _svc_labels
    with get_connection() as conn:
        lc = conn.execute(
            "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
        ).fetchone()
        if lc is None:
            return jsonify({"error": "Không tìm thấy lifecycle"}), 404
        lc = dict(lc)
        ctx: dict = {
            "service_name": _svc_labels.get(lc["service_slug"], lc["service_slug"]),
            "current_stage": lc["stage"],
            "progress_summary": "",
            "customer_name": "KH",
        }
        if lc.get("customer_id"):
            cust = conn.execute(
                "SELECT name FROM crm_customers WHERE id = ?", (lc["customer_id"],)
            ).fetchone()
            if cust:
                ctx["customer_name"] = cust["name"] or "KH"
        output = _risk_scan_fn(conn, lifecycle_id=lifecycle_id, customer_context=ctx)
    return jsonify({"ai_output": output, "lifecycle_id": lifecycle_id})
```

- [ ] **Step 5: Verify app import OK + tests still pass**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -c "import app; print('OK')"
python3 -m pytest tests/test_crm_svc_risk.py tests/test_crm_svc_tasks.py -q 2>&1 | tail -3
```

Expected: `OK` và `N passed in X.XXs`

---

### Task 4: Update crm_service_workflow.html — thêm Risk section

**Files:**
- Modify: `templates/crm_service_workflow.html`

**Interfaces:**
- Nhận từ route: `risks` (list[dict]), `latest_risk_scan` (str)
- JS calls: `PATCH /api/crm/svc-risks/<id>`, `DELETE /api/crm/svc-risks/<id>`, `POST /api/crm/svc-risks`, `POST /api/crm/svc-risks/<lifecycle_id>/ai-scan`

- [ ] **Step 1: Thêm risk section vào cuối `{% block admin_main %}`, trước `</script>` cuối của file**

Tìm đoạn `</script>` cuối cùng trong `{% block admin_main %}` của `crm_service_workflow.html`. Thêm risk section VÀO TRONG block, TRƯỚC thẻ `</script>` cuối:

```html
{# ─── Risk Section ────────────────────────────────────────────────────── #}
<div style="margin-top:2rem;border-top:2px solid #fee2e2;padding-top:1.5rem;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;">
    <h3 style="margin:0;font-size:.95rem;color:#dc2626;">
      ⚠️ Quản lý rủi ro
      <span style="font-weight:400;font-size:.8rem;color:#888;">
        ({{ risks|selectattr('is_active','equalto',1)|list|length }} đang hoạt động /
         {{ risks|length }} tổng)
      </span>
    </h3>
    <button onclick="riskAiScan()"
            id="risk-scan-btn"
            style="padding:.3rem .75rem;background:#dc2626;color:#fff;border:none;
                   border-radius:6px;font-size:.78rem;cursor:pointer;">
      AI Scan rủi ro
    </button>
  </div>

  {# AI Scan result #}
  <div id="risk-scan-output"
       style="{% if not latest_risk_scan %}display:none;{% endif %}
              background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;
              padding:.75rem;margin-bottom:1rem;font-size:.8rem;white-space:pre-wrap;">{{ latest_risk_scan }}</div>
  <div id="risk-scan-status" style="font-size:.75rem;color:#888;margin-bottom:.5rem;"></div>

  {# Risk list #}
  {% if risks %}
  <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-size:.8rem;">
      <thead>
        <tr style="background:#f8fafc;border-bottom:1px solid #e2e8f0;">
          <th style="text-align:left;padding:.5rem .75rem;font-weight:600;">Rủi ro</th>
          <th style="text-align:center;padding:.5rem .5rem;font-weight:600;">Stage</th>
          <th style="text-align:center;padding:.5rem .5rem;font-weight:600;">Xác suất</th>
          <th style="text-align:center;padding:.5rem .5rem;font-weight:600;">Ảnh hưởng</th>
          <th style="text-align:left;padding:.5rem .75rem;font-weight:600;">Biện pháp</th>
          <th style="text-align:center;padding:.5rem .5rem;font-weight:600;">Trạng thái</th>
        </tr>
      </thead>
      <tbody>
        {% for risk in risks %}
        <tr id="risk-row-{{ risk.id }}"
            style="border-bottom:1px solid #f1f5f9;
                   {% if not risk.is_active %}opacity:.45;{% endif %}">
          <td style="padding:.5rem .75rem;">
            <div style="font-weight:500;">{{ risk.title }}</div>
            {% if risk.category %}
            <div style="font-size:.7rem;color:#6366f1;">{{ risk.category }}</div>
            {% endif %}
            {% if risk.is_custom %}
            <span style="font-size:.65rem;background:#fef3c7;color:#92400e;
                         padding:1px 5px;border-radius:3px;">tuỳ chỉnh</span>
            {% endif %}
          </td>
          <td style="text-align:center;padding:.5rem .5rem;">
            <span style="font-size:.7rem;background:#e0e7ff;color:#4338ca;
                         padding:1px 6px;border-radius:3px;">
              {{ stage_labels.get(risk.stage, risk.stage) if risk.stage else '—' }}
            </span>
          </td>
          <td style="text-align:center;padding:.5rem .5rem;">
            {% set prob_color = {'cao': '#dc2626', 'trung': '#d97706', 'thap': '#16a34a'} %}
            <span style="font-size:.7rem;background:{{ prob_color.get(risk.probability, '#888') }}20;
                         color:{{ prob_color.get(risk.probability, '#888') }};
                         padding:1px 6px;border-radius:3px;font-weight:600;">
              {{ risk.probability }}
            </span>
          </td>
          <td style="text-align:center;padding:.5rem .5rem;">
            {% set imp_color = {'cao': '#dc2626', 'trung': '#d97706', 'thap': '#16a34a'} %}
            <span style="font-size:.7rem;background:{{ imp_color.get(risk.impact, '#888') }}20;
                         color:{{ imp_color.get(risk.impact, '#888') }};
                         padding:1px 6px;border-radius:3px;font-weight:600;">
              {{ risk.impact }}
            </span>
          </td>
          <td style="padding:.5rem .75rem;max-width:240px;">
            <div style="font-size:.75rem;color:#555;line-height:1.4;">
              {{ risk.mitigation[:120] ~ '...' if risk.mitigation|length > 120 else risk.mitigation }}
            </div>
          </td>
          <td style="text-align:center;padding:.5rem .5rem;">
            <div style="display:flex;gap:.25rem;justify-content:center;flex-wrap:nowrap;">
              <button onclick="riskToggleActive({{ risk.id }}, {{ 0 if risk.is_active else 1 }})"
                      title="{{ 'Đánh dấu đã xử lý' if risk.is_active else 'Kích hoạt lại' }}"
                      style="padding:2px 8px;border-radius:4px;border:none;cursor:pointer;font-size:.72rem;
                             background:{{ '#dcfce7' if risk.is_active else '#f3f4f6' }};
                             color:{{ '#16a34a' if risk.is_active else '#666' }};">
                {{ '✓ Active' if risk.is_active else '↺ Done' }}
              </button>
              {% if risk.is_custom %}
              <button onclick="riskDelete({{ risk.id }})"
                      title="Xoá"
                      style="padding:2px 6px;border-radius:4px;border:none;cursor:pointer;
                             background:#fee2e2;color:#dc2626;font-size:.72rem;">✕</button>
              {% endif %}
            </div>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <p style="color:#aaa;font-size:.85rem;">Chưa có rủi ro. Tải lại trang để seed.</p>
  {% endif %}

  {# Add custom risk #}
  <div style="margin-top:.75rem;">
    <details>
      <summary style="font-size:.8rem;color:#dc2626;cursor:pointer;user-select:none;">
        + Thêm rủi ro tuỳ chỉnh
      </summary>
      <div style="display:flex;gap:.5rem;margin-top:.5rem;flex-wrap:wrap;">
        <input type="text" id="risk-title-input"
               placeholder="Tên rủi ro..."
               style="flex:2;min-width:180px;padding:.375rem .5rem;border:1px solid #ddd;
                      border-radius:6px;font-size:.8rem;">
        <select id="risk-stage-input"
                style="padding:.375rem .5rem;border:1px solid #ddd;border-radius:6px;font-size:.8rem;">
          <option value="">— Stage —</option>
          {% for stage in stages %}
          <option value="{{ stage }}">{{ stage_labels.get(stage, stage) }}</option>
          {% endfor %}
        </select>
        <input type="text" id="risk-category-input"
               placeholder="Loại (optional)"
               style="width:120px;padding:.375rem .5rem;border:1px solid #ddd;
                      border-radius:6px;font-size:.8rem;">
        <button onclick="riskCreate()"
                style="padding:.375rem .75rem;background:#dc2626;color:#fff;border:none;
                       border-radius:6px;font-size:.8rem;cursor:pointer;">Thêm</button>
      </div>
    </details>
  </div>
</div>
```

Thêm JS sau đoạn HTML trên (vẫn trong `{% block admin_main %}`), trước thẻ `</script>` cuối của file:

```javascript
// ─── Risk JS ───────────────────────────────────────────────────────────────
function riskToggleActive(riskId, newActive) {
  fetch('/api/crm/svc-risks/' + riskId, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({is_active: newActive === 1}),
  }).then(() => location.reload()).catch(console.error);
}

function riskDelete(riskId) {
  if (!confirm('Xoá rủi ro này?')) return;
  fetch('/api/crm/svc-risks/' + riskId, {method: 'DELETE'})
    .then(() => location.reload())
    .catch(console.error);
}

function riskCreate() {
  const title = (document.getElementById('risk-title-input').value || '').trim();
  const stage = document.getElementById('risk-stage-input').value;
  const category = (document.getElementById('risk-category-input').value || '').trim();
  if (!title) return;
  fetch('/api/crm/svc-risks', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({lifecycle_id: _lifecycleId, stage, title, category}),
  }).then(() => location.reload()).catch(console.error);
}

function riskAiScan() {
  const btn = document.getElementById('risk-scan-btn');
  const status = document.getElementById('risk-scan-status');
  const out = document.getElementById('risk-scan-output');
  if (btn) btn.disabled = true;
  if (status) status.textContent = 'AI đang phân tích rủi ro...';
  fetch('/api/crm/svc-risks/' + _lifecycleId + '/ai-scan', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: '{}',
  }).then(r => r.json()).then(data => {
    if (out) {
      out.textContent = data.ai_output || '(Không có kết quả)';
      out.style.display = 'block';
    }
    if (status) status.textContent = '';
    if (btn) btn.disabled = false;
  }).catch(err => {
    if (status) status.textContent = 'Lỗi: ' + err;
    if (btn) btn.disabled = false;
  });
}
```

- [ ] **Step 2: Verify app import OK**

```bash
cd /Users/quoctuan/Documents/PTTCOM/ProjectAI/PTTP && python3 -c "import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verify all tests still pass**

```bash
python3 -m pytest tests/test_crm_svc_risk.py tests/test_crm_svc_tasks.py -q 2>&1 | tail -3
```

Expected: all PASS

---

## Self-Review

**Spec coverage:**
- [x] Fixed risk list seeded per service_slug (idempotent) → Task 2 `seed_risks`
- [x] AM có thể thêm custom risk → `create_custom_risk` + Task 4 UI form
- [x] AM có thể xoá custom risk → `delete_risk` + Task 4 UI button
- [x] AM có thể resolve/reactivate risk → `update_risk(is_active=...)` + Task 4 toggle button
- [x] AI dynamic alerts scan → `run_ai_risk_scan` + Task 3 route + Task 4 button
- [x] AI scan lưu lịch sử vào `crm_svc_risk_scans` → `get_latest_scan` + Task 4 display
- [x] Tích hợp vào `crm_service_workflow.html` → Task 4
- [x] Template nhận `risks` + `latest_risk_scan` từ route → Task 3 cập nhật `crm_service_workflow_page`
- [x] TDD: tests trước, implementation sau → Task 2
- [x] `seed_risks` idempotent → Task 2 (check `COUNT(*) WHERE is_custom=0`)
- [x] `delete_risk` chỉ xoá `is_custom=1` → Task 2
- [x] Model: `claude-haiku-4-5-20251001`, fail silent → Task 2 `run_ai_risk_scan`
- [x] 12 services có risk registry → Task 1

**Type consistency:**
- `seed_risks` → `int` ✓
- `delete_risk` → `bool` ✓
- `list_risks` → `list[dict]` ✓
- `get_latest_scan` → `str` ✓
- Route `crm_service_workflow_page` pass `risks=risks, latest_risk_scan=latest_risk_scan` → Template nhận đúng tên ✓

**Không có placeholder hay TBD nào.**
