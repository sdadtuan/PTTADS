# 01 — Tổng quan hệ thống PTTADS (bàn giao khách hàng)

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Tham chiếu:** [`SPEC_AGENCY_OPERATING_PLATFORM.md`](../SPEC_AGENCY_OPERATING_PLATFORM.md) · [`README.md`](README.md)

---

## 1. Giới thiệu

**PTTADS (PTT Agency Delivery System)** là nền tảng vận hành agency quảng cáo đa kênh do PTT Advertising Solutions triển khai, phục vụ:

- Quản lý **nhiều khách hàng (client)** trong một agency PTT
- Vòng đời dịch vụ: **Lead → Hợp đồng → Triển khai → Bàn giao → Duy trì**
- Closed-loop marketing: **Spend → Lead → Deal → Revenue → ROAS/CPL**
- Phân hệ chuyên sâu: **Meta Ads**, **SEO/AEO**, **Email Marketing**, **CRM**, **Client Portal**

### 1.1. Ba lớp sản phẩm

| Lớp | URL | Người dùng |
|-----|-----|------------|
| **Staff console (Internal Ops)** | https://ops.pttads.vn | Nhân viên PTT: AM, CSKH, Buyer, MKT, HR |
| **Client portal** | https://portal.pttads.vn | Khách hàng: viewer, approver |
| **Legacy redirect** | https://rs.pttads.vn | Bookmark cũ → redirect ops-web |

> **Lưu ý:** Website marketing công khai (`pttads.vn` landing) không nằm trong phạm vi bàn giao web-app này trừ khi HĐ ghi rõ.

### 1.2. Kiến trúc tóm tắt (2026-07)

```
Nhân viên / Khách hàng
        ↓ HTTPS
      Nginx (TLS)
        ↓
┌───────────────────┬────────────────────┐
│ ops-web  :3200    │ portal-web :3100   │  ← Next.js UI
└─────────┬─────────┴─────────┬──────────┘
          │                   │
          └─────────┬─────────┘
                    ↓
            Nest ptt-crm-api :3000        ← REST API + webhooks
                    ↓
        ┌───────────┴───────────┐
        │ PostgreSQL + SQLite   │  ← CRM master + domain schemas
        │ ptt_worker + jobs     │  ← Background sync, send, ingest
        │ Temporal (optional)   │  ← Approval workflows
        └───────────────────────┘
```

**Flask monolith HTTP đã retired (Wave 8)** — toàn bộ staff UI và API mới chạy trên Nest + Next.js.

---

## 2. Phạm vi đã bàn giao (in-scope)

### 2.1. CRM & Agency core

| Module | Route chính | Chức năng |
|--------|-------------|-----------|
| Bảng CSKH | `/crm` | Case, SLA, phân công |
| Quản lý Lead | `/crm/leads` | Pipeline, review queue, ingest webhook |
| Khách hàng | `/crm/customers` | Master data client |
| Hub hợp đồng | `/crm/hub` | HĐ, lifecycle dịch vụ |
| Triển khai DV | `/crm/service-delivery` | Workflow 7 stage: Onboard → Retain |
| Launch QA | `/crm/launch-qa` | Checklist trước go-live campaign |
| Creative Hub | `/crm/creatives` | Duyệt creative đa kênh |
| Campaign Write | `/crm/campaign-writes` | Queue chỉnh sửa ads có governance |
| Kinh doanh / BĐS | `/crm/sales`, `/crm/re-projects` | Pipeline, dự án BĐS |
| Nhân sự / KPI | `/crm/staff`, `/crm/kpi`, `/crm/payroll` | HR nội bộ |
| Agency | `/agency` | Channel accounts, ingest, KPI defs |

### 2.2. Meta Enterprise Ops

| Module | Route | Trạng thái |
|--------|-------|------------|
| Meta Ads Hub | `/meta/facebook-ads` | ✅ Production |
| Ads Ops (Launch/Edit) | `/meta/ads-ops` | ✅ Wave B15 |
| Tracking / CAPI | `/meta/tracking` | ✅ Wave B9 |
| Intelligence | `/meta/intelligence` | ✅ Wave B10–11 |
| Portal performance | `portal.pttads.vn/meta` | ✅ Wave B6 |

Chi tiết: [`huong-dan-meta-enterprise-ops.md`](../huong-dan-meta-enterprise-ops.md)

### 2.3. SEO/AEO Enterprise Ops

| Module | Route | Trạng thái |
|--------|-------|------------|
| Executive Hub | `/seo/hub` | ✅ |
| Client workspace | `/seo/clients/:id` | ✅ |
| Research / Content / Technical | `/seo/research`, `/content`, `/technical` | ✅ |
| AEO / Authority | `/seo/aeo`, `/authority` | ✅ |
| Reports / BI | `/seo/reports`, `/seo/bi` | ✅ |
| Governance | `/seo/governance` | ✅ Gate A |
| Portal SEO | `portal.pttads.vn/seo` | ✅ Pilot |

Chi tiết: [`huong-dan-seo-aeo-ops.md`](../huong-dan-seo-aeo-ops.md)

### 2.4. Email Marketing Enterprise Ops

| Module | Route | Trạng thái |
|--------|-------|------------|
| Email Hub | `/email/hub` | ✅ |
| Contacts / Consent / Suppression | `/email/contacts` … | ✅ |
| Segments / Templates / Campaigns | `/email/segments` … | ✅ |
| Deliverability / Reports / Governance | `/email/deliverability` … | ✅ P1 |
| Portal Email | `portal.pttads.vn/email` | 🟡 Pilot (flag) |
| Public preference/unsub | `/email/public/*` | ✅ |

Chi tiết: [`huong-dan-email-marketing-ops.md`](../huong-dan-email-marketing-ops.md)

### 2.5. Tích hợp kênh (webhooks)

| Kênh | Endpoint webhook | Hướng |
|------|------------------|-------|
| Meta Lead Ads | `/api/v1/webhooks/meta` | Inbound lead |
| Zalo OA | `/api/v1/webhooks/zalo` | Inbound lead/message |
| Google Ads | `/api/v1/webhooks/google` | Inbound lead |
| Email ESP | `/api/v1/webhooks/email` | Engagement events |

---

## 3. Phạm vi ngoài / giới hạn đã thống nhất

| Hạng mục | Trạng thái | Ghi chú |
|----------|------------|---------|
| CRM staff + API Nest | ✅ Production | Canonical stack |
| Webhooks 4 kênh | ✅ Nest native | |
| AI brief / intake summary | 🟡 Stub | Cần `ANTHROPIC_API_KEY` để bật |
| Temporal workflows | 🟡 Stub | Cần `PTT_TEMPORAL_ADDRESS` |
| Google Ads campaign write API | 🟡 Phase 2 | Webhook lead OK |
| Email send prod ESP | 🟡 Gate A | Staged cutover B1→B4 |
| SaaS multi-agency | ❌ Out of scope | Một agency PTT |
| Mobile app native | ❌ Out of scope | Responsive web |
| ERP/kế toán tổng hợp | ❌ Out of scope | Module tài chính cơ bản |

---

## 4. Personas & quyền truy cập

| Persona | Console | Quyền điển hình |
|---------|---------|-----------------|
| Super Admin | ops-web | Toàn hệ thống, phân quyền |
| Account Manager | ops-web | CRM, hub HĐ, client workspace |
| Media Buyer | ops-web | Meta hub, ads-ops (có gate) |
| SEO Strategist | ops-web | `/seo/*` theo cap |
| Email Strategist | ops-web | `/email/*` theo cap |
| CSKH / Sales | ops-web | Leads, customers, cases |
| Client Viewer | portal | Xem báo cáo read-only |
| Client Approver | portal | Duyệt creative, campaign, content |

Chi tiết RBAC: [05-PHAN-QUYEN-BAO-MAT-SLA.md](05-PHAN-QUYEN-BAO-MAT-SLA.md)

---

## 5. URL tra cứu nhanh

### 5.1. Staff (ops.pttads.vn)

| Nhóm | URL |
|------|-----|
| Đăng nhập | `/login` |
| CRM board | `/crm` |
| Leads | `/crm/leads` |
| Hub HĐ | `/crm/hub` |
| Meta Ads | `/meta/facebook-ads` |
| SEO Hub | `/seo/hub` |
| Email Hub | `/email/hub` |
| Agency | `/agency` |

### 5.2. Portal (portal.pttads.vn)

| Trang | URL |
|-------|-----|
| Login | `/login` |
| Dashboard | `/dashboard` |
| Meta | `/meta` |
| SEO | `/seo` |
| Email | `/email` |
| Duyệt | `/approvals` (tuỳ module) |

---

## 6. KPI & giá trị nghiệp vụ

| Chuỗi giá trị | KPI chính |
|---------------|-----------|
| **Paid (Meta)** | Spend, Lead CRM, CPL, ROAS, CAPI match rate |
| **SEO/AEO** | GSC clicks, rankings, content pipeline, AEO coverage |
| **Email** | Open/click rate, complaint rate, revenue attrib. |
| **CRM** | Lead SLA, conversion funnel, lifecycle stage |
| **Agency** | Service delivery stage, Launch QA pass, client health |

---

## 7. Tài liệu liên quan trong bộ bàn giao

| # | Tài liệu |
|---|----------|
| 02 | [Hướng dẫn người dùng nội bộ](02-HUONG-DAN-NGUOI-DUNG-NOI-BO.md) |
| 03 | [Hướng dẫn Portal khách hàng](03-HUONG-DAN-PORTAL-KHACH-HANG.md) |
| 04 | [Kiến trúc & triển khai](04-KIEN-TRUC-TRIEN-KHAI-BAN-GIAO.md) |
| 05 | [Phân quyền, bảo mật & SLA](05-PHAN-QUYEN-BAO-MAT-SLA.md) |
| 06 | [Nghiệm thu & báo cáo](06-NGHIEM-THU-VA-BAO-CAO.md) |
