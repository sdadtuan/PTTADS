# Creative Approval Workflow (Phase 3 T4)

> **Workflow:** `CreativeApprovalWorkflow`  
> **Task queue:** `ptt-agency`  
> **Worker:** `ptt_temporal/worker.py`

## Trigger

AM / internal tools submit creative via Nest:

```http
POST /api/v1/creatives
X-PTT-Internal-Key: ...
Content-Type: application/json

{
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Banner Meta T7",
  "version": 1,
  "asset_url": "https://...",
  "submitted_by": "am@pttads.vn"
}
```

Nest:

1. Inserts `creative_submissions` (`pending_client`)
2. Starts `CreativeApprovalWorkflow` (`creative-approval-{id}`)
3. Stores `temporal_workflow_id` on row

## Client decision (portal P4)

```http
POST /api/v1/creatives/{id}/approve
Authorization: Bearer {portal_jwt}
```

Nest updates PG status + emits `CreativeApproved` + signals workflow `approve_creative`.

Reject: `POST /api/v1/creatives/{id}/reject` → signal `reject_creative`.

## Workflow steps

1. **Activity** `notify_am_creative_pending` → `notification_inbox`
2. **Wait** client signal (timeout 7 days → `expired`)
3. **Activity** `notify_am_creative_decision` → AM notified

## Signals

| Signal | Payload |
|--------|---------|
| `approve_creative` | `{ reviewed_by, note? }` |
| `reject_creative` | `{ reviewed_by, note? }` |

## Local dev

```bash
./scripts/local_temporal_up.sh          # Docker :7233, UI :8088
./scripts/local_temporal_worker.sh      # Python worker
export PTT_TEMPORAL_ADDRESS=127.0.0.1:7233
./scripts/local_crm_api_up.sh
```

## Observability

- Temporal UI: http://127.0.0.1:8088
- Workflow ID: `creative-approval-{creative_submission_uuid}`
