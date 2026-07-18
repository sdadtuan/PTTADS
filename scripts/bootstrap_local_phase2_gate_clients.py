#!/usr/bin/env python3
"""Bootstrap ≥3 PG clients for local staging_phase2_gate_pack (dev only).

Usage:
  export DATABASE_URL=postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency
  export PTT_TOKEN_VAULT_KEY="$(python3 -c 'import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  export PTT_META_INSIGHTS_SYNC=1 PTT_META_INSIGHTS_STUB=1
  .venv/bin/python scripts/bootstrap_local_phase2_gate_clients.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CODES = ["DEMO", "CLIENT_B", "CLIENT_C"]


def main() -> int:
    codes_raw = (os.environ.get("PTT_CLOSED_LOOP_CLIENT_CODES") or "").strip()
    codes = [c.strip().upper() for c in codes_raw.split(",") if c.strip()] if codes_raw else DEFAULT_CODES
    if len(codes) < 3:
        print(f"WARN need ≥3 codes, got {len(codes)}", file=sys.stderr)

    if not os.environ.get("PTT_TOKEN_VAULT_KEY"):
        print("FAIL thiếu PTT_TOKEN_VAULT_KEY", file=sys.stderr)
        return 1

    from ptt_agency.clients import activate_client, add_channel_account, create_client, fetch_client_by_code
    from ptt_agency.hub_campaign_sync import upsert_hub_campaign_map
    from ptt_meta.insights_sync import sync_meta_insights

    for idx, code in enumerate(codes):
        row = fetch_client_by_code(code)
        if not row:
            row = create_client(code=code, name=f"Gate Pack {code}", industry_slug="demo")
            activate_client(str(row["id"]), force=True)
            print(f"OK  created client {code}")
        cid = str(row["id"])
        try:
            add_channel_account(
                cid,
                channel="meta",
                external_account_id=f"act_{code.lower()}",
                display_name=f"Meta {code}",
                access_token="EAAstub_local_gate_pack_token",
                token_expires_at="2026-12-31",
                pixel_id=os.environ.get("META_PIXEL_ID") or "123456789012345",
            )
        except Exception as exc:
            print(f"WARN channel {code}: {exc}", file=sys.stderr)
        upsert_hub_campaign_map(
            {
                "client_id": cid,
                "hub_campaign_id": 9000 + idx,
                "channel": "meta",
                "external_campaign_id": "12345678901",
                "external_campaign_name": f"Stub {code}",
                "external_account_id": f"act_{code.lower()}",
                "target_cpl_vnd": 150000.0,
                "active": True,
                "meta": {"stub": True, "bootstrap": "local_gate_pack"},
            }
        )
        sync = sync_meta_insights(client_id=cid, compute_metrics=True)
        print(f"OK  {code} insights_sync={sync.get('ok')} rows={sync.get('rows_upserted', 0)}")

    print(f"OK  bootstrap complete for {len(codes)} clients")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
