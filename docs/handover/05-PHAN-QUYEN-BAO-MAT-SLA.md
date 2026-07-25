# 05 — Phân quyền, bảo mật & SLA

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Tham chiếu:** [`SPEC_AGENCY_OPERATING_PLATFORM.md`](../SPEC_AGENCY_OPERATING_PLATFORM.md) §10–11

---

## 1. Mô hình xác thực

| Lớp | Cơ chế | Ghi chú |
|-----|--------|---------|
| **Staff ops-web** | JWT Bearer (`/api/v1/staff/auth/login`) | Session refresh token |
| **Client portal** | Portal JWT scoped `client_id` | Role: viewer / approver |
| **Webhooks** | Signature verify per channel | Meta HMAC, SendGrid, … |
| **Internal S2S** | `PTT_CRM_INTERNAL_KEY` | Flask legacy → Nest (retired HTTP) |

**Production:** `PTT_CRM_API_AUTH_DISABLED=0` · stub users **tắt**.

---

## 2. RBAC staff — section keys

Phân quyền qua Admin → **Phân quyền trang** → section + action.

### 2.1. CRM core

| Section | Actions tiêu biểu |
|---------|-------------------|
| `crm` | view, write — board CSKH |
| `crm_leads` | view, write, assign |
| `crm_customers` | view, write |
| `crm_agency` | view, create — bypass một số guard |

### 2.2. Meta Enterprise

| Section | Actions |
|---------|---------|
| `crm_meta_ads` | view, write, settings |
| Campaign write | Temporal + governance gate |

### 2.3. SEO/AEO

| Section | Actions |
|---------|---------|
| `crm_seo_aeo` | view |
| | write, approve, technical, settings, reports |

### 2.4. Email Marketing

| Section | Actions |
|---------|---------|
| `crm_email_mkt` | view, write, settings, deliverability, reports, compliance, approve |

Seed prod: `python3 scripts/seed_staff_email_mkt_permissions.py`

### 2.5. Gợi ý gán theo vai trò

| Vai trò | Sections |
|---------|----------|
| Head / Super Admin | Tất cả |
| AM | CRM + view Meta/SEO/Email + settings client |
| Media Buyer | Meta write + view CRM |
| SEO Strategist | seo_aeo view/write/reports |
| Email Strategist | email_mkt view/write/approve |
| Compliance | consent/compliance + approve |
| CSKH | crm + leads |

---

## 3. Portal RBAC

| Role | API scope | UI |
|------|-----------|-----|
| viewer | `client_id` read stats | Dashboard, export |
| approver | + approve/reject endpoints | + approval inbox |

Portal user **không** có quyền staff API.

---

## 4. Bảo mật dữ liệu

### 4.1. Multi-client isolation

- Mọi query domain (Meta, SEO, Email) **bắt buộc** filter `client_id`
- Portal JWT embed `client_id` — cross-tenant blocked at API

### 4.2. PII & logging

- Email/phone **redact** trong application logs
- Full PII chỉ audit log compliance (Email governance, consent)

### 4.3. Secrets management

| Secret | Không được |
|--------|------------|
| `.env` production | Commit git, email plain |
| ESP API keys | Chia sẻ client |
| Webhook secrets | Log stdout |

Khuyến nghị: vault/KV (1Password, Bitwarden business, AWS SM).

### 4.4. TLS & network

- HTTPS only public
- DB/Redis/Temporal **localhost** hoặc private network
- Firewall: 80/443 only

### 4.5. Consent & compliance (Email)

- Consent append-only (ADR-EM-08)
- Unsubscribe SLA < 24h
- Suppression master global + per-client

---

## 5. SLA & support tiers

### 5.1. Support tiers (theo HĐ)

| Tier | Đối tượng | Response P1 | Restore P1 | Báo cáo |
|------|-----------|-------------|------------|---------|
| **Standard** | Internal pods | Best effort | Best effort | Hub |
| **Enterprise client** | HĐ enterprise | 4h business | 24h | Weekly PDF |
| **Platform ops** | Toàn agency | On-call | Runbook VPS | Daily ops JSON |

### 5.2. Incident severity

| Sev | Ví dụ | Ack | Escalation |
|-----|-------|-----|------------|
| **P1** | Portal down; webhook down >15min; mass send fail | 30 min | Tech Lead + DevOps |
| **P2** | Insights sync miss 1 day; single module 5xx | 4h | Ops lead |
| **P3** | Single client token error; UI cosmetic | 1 business day | AM |
| **P4** | Enhancement request | Backlog | — |

### 5.3. Kênh liên hệ (điền tại bàn giao)

| Kênh | Dùng cho |
|------|----------|
| Email support | P2–P4 |
| Hotline / Zalo group | P1 (nếu HĐ có) |
| AM trực tiếp | Giải thích số liệu, duyệt |

---

## 6. Change management

| Thay đổi | Quy trình |
|----------|-----------|
| Bật send email prod | Change ticket + Gate A sign-off |
| Thêm pilot client Meta | AM sign-off + map ad account |
| DDL schema mới | Maintenance window + backup verify |
| Nâng flag portal | UAT portal + client approver test |

---

## 7. Audit & compliance

| Module | Audit trail |
|--------|-------------|
| Email E-13 | `email_mkt.audit_log` — governance CRUD |
| SEO S-14 | governance evaluations |
| CRM | lead status history, workflow steps |
| Portal | approval decisions + actor |

Export audit theo yêu cầu compliance — liên hệ PTT DPO/legal nếu HĐ yêu cầu.

---

## 8. Đào tạo bảo mật cho khách hàng

- Không share credential portal
- Báo ngay truy cập lạ
- Duyệt campaign trên môi trường HTTPS chính thức only
- Không paste ESP/Meta token vào ticket support

Form bàn giao: [`ban-giao-tai-khoan-credentials-a4.html`](../forms/ban-giao-tai-khoan-credentials-a4.html)
