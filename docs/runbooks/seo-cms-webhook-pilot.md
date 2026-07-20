# CMS Webhook Pilot — SEO/AEO → Client CMS

Pilot gửi nội dung **approved/published** từ PTTADS SEO/AEO Ops tới CMS client qua **HTTP POST JSON**.

## Kiến trúc

```
Content detail → POST /api/v1/seo/content/:id/cms/publish
       ↓
seo_cms_publish_jobs (PG)
       ↓
POST {webhook_url}  Authorization: Bearer {secret}
       ↓
Client CMS (hoặc pilot receiver nội bộ)
```

## A. Pilot nội bộ (local dev)

### 1. Biến môi trường

Copy từ `deploy/env.cms-webhook-pilot.example` hoặc thêm vào `.env`:

```bash
export PTT_SEO_ENTERPRISE_ENABLED=1
export PTT_SEO_CMS_WEBHOOK_SECRET=pilot-dev-secret
export PTT_FLASK_MONOLITH_URL=http://127.0.0.1:8002
export PTT_SEO_CMS_PILOT_WEBHOOK_URL=http://127.0.0.1:8002/api/v1/seo/internal/cms-webhook/receive
```

### 2. Seed client

```bash
python3 scripts/seed_cms_webhook_pilot.py --customer-id <CRM_CUSTOMER_ID>
```

Hoặc trong UI: **Client workspace** → **CMS Publish — Webhook Pilot** → **Áp dụng pilot mặc định**.

### 3. Test connectivity

- Client workspace → **Test webhook** (gửi payload `seo.content.publish.test`)
- Hoặc: `curl -X POST http://127.0.0.1:8002/api/v1/seo/clients/<id>/cms/test` (cần session CRM)

### 4. Publish thật

1. Tạo/mở content → chuyển trạng thái **approved**
2. Tab **Workflow** → **Publish → CMS**
3. Kiểm tra **Publish jobs** trên client workspace hoặc `GET /api/v1/seo/clients/<id>/cms/jobs`

## B. Pilot với CMS client thật

### Webhook contract (JSON body)

| Field | Mô tả |
|-------|--------|
| `event` | `seo.content.publish` hoặc `seo.content.publish.test` |
| `title`, `slug`, `content_type` | Metadata |
| `body_html` | HTML body |
| `meta_title`, `meta_description` | SEO meta |
| `schema_json` | JSON-LD (optional) |
| `content_id`, `customer_id` | CRM references |

### Response mong đợi (200)

```json
{
  "ok": true,
  "url": "https://client.com/blog/my-slug",
  "permalink": "https://client.com/blog/my-slug"
}
```

### Cấu hình trên client workspace

1. **Webhook URL** — endpoint CMS client (POST)
2. **Bearer token** — shared secret (CMS validate `Authorization: Bearer …`)
3. **Test webhook** — verify trước khi publish production content

## C. API tham khảo

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/api/v1/seo/clients/:id/cms/target` | Đọc cấu hình |
| PUT | `/api/v1/seo/clients/:id/cms/target` | Lưu cấu hình (quyền `configure`) |
| POST | `/api/v1/seo/clients/:id/cms/test` | Ping webhook |
| POST | `/api/v1/seo/clients/:id/cms/pilot/apply-defaults` | Pilot nội bộ |
| POST | `/api/v1/seo/content/:id/cms/publish` | Publish content |
| POST | `/api/v1/seo/internal/cms-webhook/receive` | Receiver pilot (Flask) |

## D. Troubleshooting

| Triệu chứng | Xử lý |
|-------------|--------|
| 401 Unauthorized | Kiểm tra `PTT_SEO_CMS_WEBHOOK_SECRET` khớp Bearer token |
| `enterprise_disabled` | `PTT_SEO_ENTERPRISE_ENABLED=1` |
| Job `pending` | Chưa lưu CMS target — seed hoặc UI |
| Job `failed` | Xem `error_message` trong jobs list; test curl trực tiếp tới webhook URL |

## F. Staging — Gate E auto-publish

Sau `staging_seo_gate_e_deploy.sh` với `APPLY=1`:

1. `.env` có `PTT_SEO_CMS_AUTO_PUBLISH=1`
2. Content chuyển **published** → tự queue CMS publish (nếu target active)
3. Kiểm tra jobs: `GET /api/v1/seo/clients/<id>/cms/jobs`

```bash
PTT_VPS_HOST=<host> APPLY=1 PILOT_CUSTOMER_ID=<id> ./scripts/staging_seo_gate_e_deploy.sh
```

## E. Prod checklist

- [ ] Đổi `PTT_SEO_CMS_WEBHOOK_SECRET` sang secret mạnh (≥32 ký tự)
- [ ] Webhook URL HTTPS only
- [ ] CMS client xác thực Bearer + rate limit
- [ ] Dry-run trên 1 bài approved trước batch publish
- [ ] Log jobs ≥7 ngày trước go-live
