# Bộ tài liệu bàn giao hệ thống PTTADS — Customer Handover Pack

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Đơn vị bàn giao:** PTT Advertising Solutions  
> **Đối tượng nhận:** Ban lãnh đạo, PO, AM, vận hành agency, khách hàng enterprise (portal)  
> **Kiến trúc bàn giao:** NestJS + Next.js (ops-web / portal-web) + Python workers · Flask HTTP **retired**

---

## Mục đích bộ tài liệu

Bộ tài liệu này là **gói bàn giao chính thức** cho khách hàng và đội vận hành PTT sau triển khai **PTT Agency Operating Platform** trên PTTADS, bao gồm:

- Tổng quan hệ thống và phạm vi đã giao
- Hướng dẫn sử dụng theo vai trò (staff nội bộ + portal khách hàng)
- Kiến trúc, URL, hạ tầng và quy trình nghiệm thu
- Phân quyền, bảo mật, SLA và xử lý sự cố
- Biểu mẫu in A4 ký nghiệm thu và bàn giao tài khoản

---

## Danh mục tài liệu

| # | Tài liệu | Đối tượng | Mô tả |
|---|----------|-----------|-------|
| **01** | [Tổng quan hệ thống](01-TONG-QUAN-HE-THONG.md) | PO, lãnh đạo | Vision, module đã giao, URL, giới hạn đã thống nhất |
| **02** | [Hướng dẫn người dùng nội bộ](02-HUONG-DAN-NGUOI-DUNG-NOI-BO.md) | AM, CSKH, MKT, Ops | CRM, Meta, SEO, Email — thao tác hàng ngày |
| **03** | [Hướng dẫn Portal khách hàng](03-HUONG-DAN-PORTAL-KHACH-HANG.md) | Client viewer/approver | Đăng nhập, duyệt, báo cáo Meta/SEO/Email |
| **04** | [Kiến trúc & triển khai bàn giao](04-KIEN-TRUC-TRIEN-KHAI-BAN-GIAO.md) | PO, IT khách, DevOps | Sơ đồ, domain, dịch vụ, smoke test, rollback |
| **05** | [Phân quyền, bảo mật & SLA](05-PHAN-QUYEN-BAO-MAT-SLA.md) | Admin, Compliance | RBAC, JWT, webhook, tier hỗ trợ |
| **06** | [Nghiệm thu & báo cáo deliverables](06-NGHIEM-THU-VA-BAO-CAO.md) | PO, AM | Checklist nghiệm thu, catalog báo cáo client |

### Use Case (101 UC — traceability spec)

| Tài liệu | Mô tả |
|----------|-------|
| [Catalog Use Case](../use-cases/README.md) | Index 101 UC · ma trận actor · sơ đồ phụ thuộc |
| [00 — System Overview](../use-cases/00-SYSTEM-OVERVIEW.md) | 12 UC cross-module (onboard, closed-loop, approval, incident) |
| [01 — CRM Core](../use-cases/01-CRM-CORE.md) | 15 UC lead → customer → pipeline |
| [02 — Service Delivery](../use-cases/02-AGENCY-SERVICE-DELIVERY.md) | 12 UC lifecycle, Launch QA, campaign write |
| [03 — Meta Enterprise](../use-cases/03-META-ENTERPRISE.md) | 14 UC sync, CAPI, Ads wizard |
| [04 — SEO/AEO](../use-cases/04-SEO-AEO.md) | 14 UC workspace, content, governance |
| [05 — Email Marketing](../use-cases/05-EMAIL-MARKETING.md) | 14 UC domain, segment, send, F3 |
| [06 — Client Portal](../use-cases/06-CLIENT-PORTAL.md) | 10 UC login, KPI, approvals |
| [07 — Platform](../use-cases/07-PLATFORM-AUTH-WEBHOOKS.md) | 10 UC auth, webhook, worker, health |

**Chi tiết hành động (UAT):** [Use Case Actions](../use-cases/actions/README.md) · [Gap analysis](../use-cases/ACTION-GAP-ANALYSIS.md)

### Biểu mẫu in (A4)

| Form | File | Dùng khi |
|------|------|----------|
| Nghiệm thu bàn giao | [`../forms/ban-giao-pttads-nghiem-thu-a4.html`](../forms/ban-giao-pttads-nghiem-thu-a4.html) | Ký PO sau UAT |
| Bàn giao tài khoản | [`../forms/ban-giao-tai-khoan-credentials-a4.html`](../forms/ban-giao-tai-khoan-credentials-a4.html) | Ghi nhận credential (vault) |
| Checklist SEO/AEO | [`../forms/seo-aeo-ops-checklist-a4.html`](../forms/seo-aeo-ops-checklist-a4.html) | Vận hành SEO hàng ngày |
| Checklist Email MKT | [`../forms/email-marketing-ops-checklist-a4.html`](../forms/email-marketing-ops-checklist-a4.html) | Vận hành Email hàng ngày |

### Slide đào tạo

```bash
python3 scripts/generate_pttads_handover_training_pptx.py
# → docs/handover/PTTADS_Ban_Giao_Dao_Tao.pptx
```

---

## Hướng dẫn vận hành chi tiết theo phân hệ

Tài liệu bàn giao **tóm tắt** — chi tiết kỹ thuật và từng màn hình nằm ở ops guide chuyên sâu:

| Phân hệ | Ops guide | Master spec |
|---------|-----------|-------------|
| **SEO/AEO** | [`huong-dan-seo-aeo-ops.md`](../huong-dan-seo-aeo-ops.md) | [`SPEC_SEO_AEO_OPERATING_SYSTEM.md`](../SPEC_SEO_AEO_OPERATING_SYSTEM.md) |
| **Email Marketing** | [`huong-dan-email-marketing-ops.md`](../huong-dan-email-marketing-ops.md) | [`SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md`](../SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md) |
| **Meta Enterprise** | [`huong-dan-meta-enterprise-ops.md`](../huong-dan-meta-enterprise-ops.md) | [`SPEC_META_ENTERPRISE_PTTADS.md`](../SPEC_META_ENTERPRISE_PTTADS.md) |
| **Agency Platform** | [`runbooks/vps-full-system-deploy.md`](../runbooks/vps-full-system-deploy.md) | [`SPEC_AGENCY_OPERATING_PLATFORM.md`](../SPEC_AGENCY_OPERATING_PLATFORM.md) |

---

## Runbook nội bộ (PTT — không giao trực tiếp khách trừ khi HĐ yêu cầu)

| Runbook | Mục đích |
|---------|----------|
| [`handover-production-flask-to-nest.md`](../runbooks/handover-production-flask-to-nest.md) | Bàn giao 1 trang · pilot · sign-off |
| [`vps-full-system-deploy.md`](../runbooks/vps-full-system-deploy.md) | Deploy greenfield / cutover |
| [`vps-production-operations.md`](../runbooks/vps-production-operations.md) | Vận hành hàng ngày VPS |
| [`email-marketing-prod-pilot-checklist.md`](../runbooks/email-marketing-prod-pilot-checklist.md) | Gate A Email |
| [`email-deliverability-incident.md`](../runbooks/email-deliverability-incident.md) | Sự cố deliverability |

---

## Quy trình bàn giao đề xuất (5 bước)

```mermaid
flowchart LR
    A[1. Walkthrough 01–03] --> B[2. UAT smoke 04]
    B --> C[3. Bàn giao tài khoản form]
    C --> D[4. Đào tạo PPT + ops guides]
    D --> E[5. Ký nghiệm thu form A4]
```

1. **Walkthrough** — trình bày tài liệu 01–03 với PO và key users (2–3 giờ).
2. **UAT smoke** — thực hiện checklist mục 4 trong tài liệu 04 + 06 (staff + portal).
3. **Credentials** — điền form bàn giao tài khoản; mật khẩu lưu vault/KV, **không** email plain text.
4. **Đào tạo** — slide PPT + module ops guide theo vai trò (AM → Meta+CRM; MKT → SEO+Email).
5. **Sign-off** — ký biểu mẫu nghiệm thu A4; lưu artifact gate JSON (nội bộ PTT).

---

## Liên hệ hỗ trợ (điền tại bàn giao)

| Vai trò | Họ tên | Email | SĐT |
|---------|--------|-------|-----|
| PO khách hàng | | | |
| AM phụ trách | | | |
| PTT Tech Lead | | | |
| PTT DevOps | | | |

---

**Lịch sử**

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-25 | Initial customer handover pack |
