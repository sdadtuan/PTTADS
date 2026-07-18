#!/usr/bin/env python3
"""Bootstrap Google Ads pilot client — channel account + hub map (Phase 3 G1/G3)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"
STUB_CAMPAIGN_ID = "stub_google_camp_1"
STUB_CUSTOMER_ID = "1234567890"


def bootstrap(client_id: str, *, client_code: str = "PORTAL_DEMO") -> dict:
    from ptt_agency.clients import add_channel_account, fetch_client_by_code
    from ptt_agency.hub_campaign_sync import upsert_hub_campaign_map
    from ptt_google.insights_sync import sync_google_insights

    row = fetch_client_by_code(client_code)
    if row:
        client_id = str(row["id"])

    os.environ.setdefault("PTT_GOOGLE_INSIGHTS_SYNC", "1")
    os.environ.setdefault("PTT_GOOGLE_INSIGHTS_STUB", "1")

    try:
        add_channel_account(
            client_id,
            channel="google",
            external_account_id=STUB_CUSTOMER_ID,
            display_name="Google Ads Pilot (stub)",
            access_token=os.environ.get("PTT_GOOGLE_ADS_REFRESH_TOKEN", "stub_google_refresh"),
            credential_ref=os.environ.get("PTT_GOOGLE_PILOT_CREDENTIAL_REF", ""),
        )
    except Exception as exc:
        if "duplicate" not in str(exc).lower() and "unique" not in str(exc).lower():
            raise

    upsert_hub_campaign_map(
        {
            "client_id": client_id,
            "hub_campaign_id": 9201,
            "channel": "google",
            "external_campaign_id": STUB_CAMPAIGN_ID,
            "external_campaign_name": "Google Stub Campaign",
            "external_account_id": STUB_CUSTOMER_ID,
            "target_cpl_vnd": 180000.0,
            "active": True,
            "meta": {"stub": True, "bootstrap": "google_pilot"},
        }
    )

    sync = sync_google_insights(client_id=client_id, compute_metrics=True)
    return {
        "client_id": client_id,
        "customer_id": STUB_CUSTOMER_ID,
        "campaign_id": STUB_CAMPAIGN_ID,
        "sync": sync,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Google Ads pilot (G1+G3)")
    parser.add_argument("--client-id", default=os.environ.get("GOOGLE_PILOT_CLIENT_ID", DEFAULT_CLIENT))
    parser.add_argument("--client-code", default=os.environ.get("GOOGLE_PILOT_CLIENT_CODE", "PORTAL_DEMO"))
    args = parser.parse_args()
    os.environ.setdefault("DATABASE_URL", "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency")
    out = bootstrap(args.client_id, client_code=args.client_code)
    print(
        f"OK  Google pilot client={out['client_id']} "
        f"sync_ok={out['sync'].get('ok')} rows={out['sync'].get('rows_upserted', 0)}"
    )
    return 0 if out["sync"].get("ok") or out["sync"].get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
