#!/usr/bin/env python3
"""Seed SEO pilot data for ops-web §12 handoff Playwright E2E."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ptt_jobs.db import pg_available
from ptt_seo.client_settings import upsert_settings
from ptt_seo.db import seo_write

DEFAULT_CUSTOMER_ID = 1
DEFAULT_DOMAIN = "handoff-e2e.example.com"


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ops-web SEO handoff E2E pilot")
    parser.add_argument("--apply", action="store_true", help="Write to database")
    parser.add_argument("--customer-id", type=int, default=DEFAULT_CUSTOMER_ID)
    parser.add_argument("--domain", default=os.environ.get("OPS_SEO_HANDOFF_DOMAIN", DEFAULT_DOMAIN))
    args = parser.parse_args()

    payload = {
        "customer_id": args.customer_id,
        "domain": args.domain,
        "markets": ["VN"],
        "industry": "Handoff E2E",
        "contract_tier": "standard",
        "notes": "ops-web §12 handoff Playwright seed",
    }
    print(json.dumps(payload, ensure_ascii=False))

    if not args.apply:
        print("Dry-run — pass --apply to write", file=sys.stderr)
        return

    os.environ.setdefault("SEO_AEO_DB", "pg" if pg_available() else "sqlite")
    with seo_write() as conn:
        upsert_settings(
            conn,
            int(args.customer_id),
            {
                "domains": [args.domain],
                "markets": payload["markets"],
                "languages": ["vi"],
                "industry": payload["industry"],
                "contract_tier": payload["contract_tier"],
                "notes": payload["notes"],
            },
        )
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
