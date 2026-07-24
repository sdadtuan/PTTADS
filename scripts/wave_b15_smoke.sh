#!/usr/bin/env bash
# Wave B15 — smoke: launch templates + creative upload stub + edit snapshot
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

python3 - <<'PY'
from ptt_meta.ads_edit import build_edit_diff, build_edit_snapshot, validate_edit_submit
from ptt_meta.ads_ops import build_create_campaign_payload, list_launch_templates, validate_launch_payload
from ptt_meta.creative_upload import upload_creative_link

templates = list_launch_templates()
assert len(templates) >= 2
payload = build_create_campaign_payload(
    client_id="00000000-0000-0000-0000-000000000001",
    external_account_id="act_123",
    template_id="re_lead_default",
    campaign_name="Test",
    adset_name="Adset",
    ad_name="Ad",
    daily_budget_vnd=500_000,
    creative_submission_id="00000000-0000-0000-0000-000000000099",
)
assert not validate_launch_payload(payload)

upload = upload_creative_link(
    client_id="00000000-0000-0000-0000-000000000001",
    creative_submission_id="00000000-0000-0000-0000-000000000099",
    stub=True,
)
assert upload["ok"] and upload["stub"]

snap = build_edit_snapshot(client_id="c1", external_ad_id="ad_999")
diff = build_edit_diff(
    old_value={"headline": snap["headline"]},
    new_value={"headline": "New headline"},
)
assert diff["change_count"] == 1
assert not validate_edit_submit(
    action="update_ad_copy",
    client_id="c1",
    external_ad_id="ad_999",
    new_value={"headline": "New", "primary_text": "Body"},
)

print("B15 smoke OK: templates=", len(templates), "upload=", upload.get("external_creative_id"))
PY
