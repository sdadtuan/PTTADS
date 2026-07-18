# Phụ lục: Task Consult theo 12 dịch vụ

> **Auto-generated** từ `crm_svc_workflow_steps.py`. Không sửa tay — chạy lại:
> `python3 scripts/generate_consult_runbook_appendix.py`

---

## 1. Dịch vụ AEO

- **Slug CRM:** `dich-vu-aeo`
- **Nhóm:** Tìm kiếm tự nhiên
- **Task:** Audit AI search presence

**Mô tả:** Kiểm tra KH xuất hiện trong ChatGPT/Gemini/Perplexity như thế nào. Xác định content gaps cần lấp.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `current_status` | Kết quả audit AI search hiện tại | textarea |
| `content_gaps` | Content gaps phát hiện | textarea |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 2. Quản trị Website

- **Slug CRM:** `dich-vu-quan-tri-website`
- **Nhóm:** Thiết kế & web
- **Task:** Đánh giá website & xác định scope

**Mô tả:** Kiểm tra: tốc độ, bảo mật, backup, phiên bản plugin. Xác định scope quản trị hàng tháng.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `current_status` | Tình trạng website hiện tại | textarea |
| `pain_points` | Vấn đề cần giải quyết | textarea |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 3. SEO Audit

- **Slug CRM:** `dich-vu-seo-audit`
- **Nhóm:** Tìm kiếm tự nhiên
- **Task:** Scoping & phân tích sơ bộ

**Mô tả:** Xác định phạm vi audit: technical, on-page, off-page, content, competitor. Báo giá chính xác.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `audit_scope` | Phạm vi audit | textarea |
| `current_status` | Tình trạng website sơ bộ | textarea |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 4. SEO Local

- **Slug CRM:** `dich-vu-seo-local`
- **Nhóm:** Tìm kiếm tự nhiên
- **Task:** GBP audit & local keyword research

**Mô tả:** Audit GBP: thông tin đầy đủ chưa, review count, ảnh, Q&A. Nghiên cứu từ khóa local.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `current_status` | Kết quả GBP audit | textarea |
| `local_keywords` | Từ khóa local mục tiêu | textarea |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 5. SEO Tổng thể

- **Slug CRM:** `dich-vu-seo-tong-the`
- **Nhóm:** Tìm kiếm tự nhiên
- **Task:** Audit website & phân tích từ khóa

**Mô tả:** Phân tích technical SEO, tốc độ tải, Core Web Vitals. Nghiên cứu từ khóa mục tiêu, volume, difficulty. Ghi nhận đối thủ.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `current_status` | Tình trạng website hiện tại | textarea |
| `top_competitors` | Đối thủ chính | text |
| `target_keywords` | Từ khóa mục tiêu | textarea |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 6. Quảng cáo Facebook

- **Slug CRM:** `quang-cao-facebook`
- **Nhóm:** Quảng cáo
- **Task:** Phân tích & lên strategy

**Mô tả:** Phân tích đối tượng, sản phẩm, đối thủ. Strategy: objective, targeting, format creative.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `target_audience` | Đối tượng mục tiêu | textarea |
| `current_status` | Kết quả Ads trước đây | textarea |
| `product_usp` | USP sản phẩm | textarea |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 7. Quảng cáo Google

- **Slug CRM:** `quang-cao-google`
- **Nhóm:** Quảng cáo
- **Task:** Keyword research & account strategy

**Mô tả:** Nghiên cứu từ khóa, đối thủ, ước tính CPC. Lên account structure.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `target_keywords` | Từ khóa mục tiêu | textarea |
| `current_status` | Kết quả Google Ads hiện tại | textarea |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 8. Landing Page

- **Slug CRM:** `thiet-ke-landing-page`
- **Nhóm:** Thiết kế & web
- **Task:** Brief landing page

**Mô tả:** Xác định: đối tượng mục tiêu, USP, CTA chính, offer, tone of voice.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `target_audience` | Đối tượng mục tiêu | textarea |
| `usp` | USP / điểm khác biệt | text |
| `cta` | CTA chính | text |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 9. Thiết kế Website

- **Slug CRM:** `thiet-ke-website`
- **Nhóm:** Thiết kế & web
- **Task:** Thu thập yêu cầu chi tiết

**Mô tả:** Họp tư vấn: mục tiêu website, đối tượng người dùng, website tham khảo, tính năng cần có.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `current_status` | Yêu cầu chi tiết | textarea |
| `design_refs` | Website tham khảo (URLs) | textarea |
| `pages_count` | Số trang cần thiết kế | number |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 10. Website Trọn gói

- **Slug CRM:** `thiet-ke-website-tron-goi`
- **Nhóm:** Thiết kế & web
- **Task:** Tư vấn kỹ thuật & thu thập yêu cầu

**Mô tả:** Họp chi tiết: tính năng, tích hợp (payment/CRM), hosting, domain, SEO cơ bản.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `current_status` | Yêu cầu kỹ thuật chi tiết | textarea |
| `integrations` | Tích hợp cần thiết | text |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 11. Thuê Tài khoản Ads

- **Slug CRM:** `thue-tai-khoan-quang-cao`
- **Nhóm:** Quảng cáo
- **Task:** Đánh giá rủi ro & điều khoản

**Mô tả:** Đánh giá lịch sử tài khoản KH, rủi ro vi phạm policy. Giải thích điều khoản sử dụng.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `current_status` | Lịch sử tài khoản KH | textarea |
| `risk_assessment` | Đánh giá rủi ro | text |

**AI:** prompt `consult_analysis` trên task card workflow.

---

## 12. Tiếp thị Nội dung

- **Slug CRM:** `tiep-thi-noi-dung`
- **Nhóm:** Nội dung
- **Task:** Phân tích content & lên strategy

**Mô tả:** Phân tích content KH đang có, đối thủ, cơ hội. Gợi ý cluster chủ đề và content calendar sơ bộ.

**Form CRM (bắt buộc điền trước khi tick ✓):**

| Field key | Label | Loại |
|-----------|-------|------|
| `current_status` | Content KH đang có | textarea |
| `top_competitors` | Đối thủ về content | text |
| `target_audience` | Đối tượng độc giả | textarea |

**AI:** prompt `consult_analysis` trên task card workflow.

---
