# Phase 3 UAT sign-off

> Gate trước khi đánh dấu Phase 3 Done trên prod.

## Participants

| Role | Name | Sign-off |
|------|------|----------|
| AM lead | | [ ] |
| Client approver (pilot) | | [ ] |
| DevOps | | [ ] |
| QA | | [ ] |

## Checklist

### Portal (Track P)

- [ ] Login pilot user (scrypt PG, không stub env)
- [ ] Dashboard T-7/T-30 khớp Agency Ops CPL (Meta + Google)
- [ ] Creative approve E2E trên staging/prod
- [ ] Cross-tenant: approver client A không duyệt creative client B

### Temporal (Track T)

- [ ] Worker systemd healthy 48h
- [ ] Onboarding / Launch QA / Creative WF start từ Agency Ops
- [ ] `GET /api/v1/workflows/*/status` trả status hợp lệ

### Google (Track G)

- [ ] OAuth connect 1 client thành công
- [ ] `./scripts/sync_google_insights.sh` upsert `channel=google`

### Migration (Track D)

- [ ] DDL v4 applied + migrate Hub/SOP
- [ ] `PTT_HUB_PG_PRIMARY=1` staging 7 ngày không regression
- [ ] Lead shadow sunset runbook reviewed (cutover sau soak)

### Ops

- [ ] `https://portal.pttads.vn` TLS valid
- [ ] Sentry `ptt-portal` nhận error test
- [ ] Regression L01–L26 critical pass
- [ ] `./scripts/playwright_portal_e2e_temporal.sh` pass

## Evidence files

```bash
cp docs/evidence/phase3-uat-signoff.template.json docs/evidence/phase3-uat-signoff.json
# Fill signoffs + commit or attach to ticket
```

## Rollback

See `docs/runbooks/vps-phase3-portal-cutover-checklist.md` § Rollback.
