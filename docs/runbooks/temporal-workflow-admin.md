# Temporal workflow ops (Phase 3 Track T)

## Worker health

```bash
sudo systemctl status ptt-temporal-worker
journalctl -u ptt-temporal-worker -f
```

Temporal UI (restrict VPN): `http://127.0.0.1:8088`

## Workflow IDs

| Type | ID pattern |
|------|------------|
| Creative approval | `creative-approval-{uuid}` |
| Client onboarding | `client-onboarding-{client_id}` |
| Launch QA | `launch-qa-{run_id}` |

## Cancel workflow (AM escalation)

```bash
temporal workflow cancel \
  --address 127.0.0.1:7233 \
  --namespace default \
  --workflow-id creative-approval-<UUID>
```

## Signal retry (creative stuck pending)

Nest approve already signals Temporal. If worker was down:

1. Start worker
2. Re-approve via Nest (idempotent if already approved in PG) or manual signal:

```bash
temporal workflow signal \
  --address 127.0.0.1:7233 \
  --namespace default \
  --workflow-id creative-approval-<UUID> \
  --name approve_creative \
  --input '{"approver_email":"ops@pttads.vn","note":"manual retry"}'
```

## Replay / history

Use Temporal UI → Workflow → Event History. Export for QA sign-off.

## Rollback

`systemctl stop ptt-temporal-worker` — PG state remains; Nest returns `temporal_signal: stub` when `PTT_TEMPORAL_ADDRESS` unset.
