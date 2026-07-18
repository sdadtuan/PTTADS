# Campaign Write Approval Workflow (Phase 4 F2)

> **Workflow:** `CampaignWriteApprovalWorkflow`  
> **Task queue:** `ptt-agency`  
> **Worker:** `ptt_temporal/worker.py`

## Trigger

AM submits budget/status change via Nest (Flask agency UI proxies):

```http
POST /api/v1/campaign-writes
X-PTT-Internal-Key: ...
Content-Type: application/json

{
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "external_campaign_id": "120210123456789",
  "change_type": "daily_budget",
  "new_value": { "daily_budget_vnd": 500000 },
  "submitted_by": "am@pttads.vn"
}
```

Nest:

1. Inserts `campaign_write_requests` (`pending_approval`)
2. Starts `CampaignWriteApprovalWorkflow` (`campaign-write-{id}`)
3. Stores `temporal_workflow_id` on row

## Admin approval (agency CRM)

```http
POST /api/v1/campaign-writes/{id}/approve
X-PTT-Internal-Key: ...

{ "approved_by": "admin@pttads.vn", "note": "ok" }
```

Reject: `POST /api/v1/campaign-writes/{id}/reject` → signal `reject_write`.

## Workflow steps

1. **Activity** `notify_am_campaign_write` → `notification_inbox` + Slack
2. **Wait** admin signal (timeout 3 days → `expired`)
3. On approve: **Activity** `execute_campaign_write` → `ptt_meta.campaign_write.apply_daily_budget`
4. **Activity** `mark_campaign_write_executed` → PG status `executed` / `execution_failed`

## Signals

| Signal | Payload |
|--------|---------|
| `approve_write` | `{ approved_by, note? }` |
| `reject_write` | `{ approved_by, note? }` |

## Dev flags

| Env | Purpose |
|-----|---------|
| `PTT_META_CAMPAIGN_WRITE_STUB=1` | Skip Meta Graph API |
| `PTT_FLASK_MONOLITH_MODE=readonly` | Flask writes blocked; Nest proxies OK |

## Local dev

```bash
./scripts/local_temporal_up.sh
./scripts/local_temporal_worker.sh
export PTT_TEMPORAL_ADDRESS=127.0.0.1:7233
./scripts/apply_pg_ddl_v5_campaign_writes.sh
./scripts/local_crm_api_up.sh
```

## Observability

- Temporal UI: http://127.0.0.1:8088
- Workflow ID: `campaign-write-{request_uuid}`
- Domain events: `CampaignWriteSubmitted`, `CampaignWriteApproved`
