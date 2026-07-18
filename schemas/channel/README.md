# Channel schemas & OpenAPI

Contract cho lớp **ChannelAdapter** — dùng chung Flask hiện tại và NestJS/FastAPI sau migration.

| File | Mục đích |
|------|----------|
| `normalized-lead.schema.json` | Lead chuẩn hóa từ mọi kênh |
| `normalized-event.schema.json` | Pixel / CAPI / webhook / email events |
| `normalized-daily-performance.schema.json` | Insights ngày (CPA, ROAS, …) |
| `webhook-ingest.openapi.yaml` | API `POST /api/v1/webhooks/{channel}` |

## Code Python

- Package: `ptt_channel/`
- Registry: `ptt_channel.registry.get_default_registry()`
- Ingress: `ptt_channel.ingress.parse_channel_webhook()`
- Route Flask: `GET/POST /api/v1/webhooks/<channel>` (blueprint `channel_webhooks`)

## Thêm kênh mới

1. Implement `ChannelAdapter` trong `ptt_channel/adapters/`
2. `registry.register(...)`
3. Bổ sung enum `ChannelCode` nếu cần
4. Cập nhật JSON Schema `enum` cho `channel`
5. Fixture test trong `tests/fixtures/channels/{code}/`
