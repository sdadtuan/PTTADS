#!/usr/bin/env python3
"""Seed seo_client_settings (+ optional portal map) for SEO/AEO B1 pilot."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ptt_jobs.db import pg_available
from ptt_seo.client_settings import upsert_settings
from ptt_seo.db import seo_write
from ptt_seo.portal_bridge import upsert_portal_map

DEFAULT_PILOTS = [
    {
        "customer_id": 1,
        "client_id": "550e8400-e29b-41d4-a716-446655440000",
        "domains": ["pilot-client-1.example.com"],
        "markets": ["VN"],
        "industry": "Bất động sản",
        "contract_tier": "standard",
        "notes": "B1 pilot — seed via seed_seo_pilot_client_settings.py",
    },
    {
        "customer_id": 2,
        "client_id": "660e8400-e29b-41d4-a716-446655440001",
        "domains": ["pilot-client-2.example.com"],
        "markets": ["VN"],
        "industry": "Dịch vụ",
        "contract_tier": "premium",
        "notes": "B1 pilot #2",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed SEO client settings for ops-web pilot")
    parser.add_argument("--apply", action="store_true", help="Write to database")
    parser.add_argument("--customer-id", type=int, default=0, help="Single customer_id (0 = defaults)")
    parser.add_argument("--domain", action="append", dest="domains", default=[])
    parser.add_argument("--market", default="VN")
    parser.add_argument("--industry", default="")
    parser.add_argument("--portal-map", action="store_true", help="Also upsert seo_portal_client_map")
    args = parser.parse_args()

    pilots = list(DEFAULT_PILOTS)
    if args.customer_id:
        pilots = [
            {
                "customer_id": args.customer_id,
                "client_id": f"pilot-{args.customer_id:04d}",
                "domains": args.domains or [f"client-{args.customer_id}.example.com"],
                "markets": [args.market],
                "industry": args.industry or "Pilot",
                "contract_tier": "standard",
                "notes": "Custom B1 pilot seed",
            }
        ]

    for row in pilots:
        print(
            f"  customer_id={row['customer_id']} domains={row['domains']} "
            f"markets={row['markets']} industry={row['industry']!r}"
        )
        if args.portal_map:
            print(f"    portal map → {row['client_id']}")

    if not args.apply:
        print("Dry-run — pass --apply to write")
        return

    os.environ.setdefault("SEO_AEO_DB", "pg" if pg_available() else "sqlite")
    with seo_write() as conn:
        for row in pilots:
            upsert_settings(
                conn,
                int(row["customer_id"]),
                {
                    "domains": row["domains"],
                    "markets": row["markets"],
                    "languages": ["vi"],
                    "industry": row["industry"],
                    "contract_tier": row["contract_tier"],
                    "notes": row["notes"],
                },
            )
            if args.portal_map and row.get("client_id"):
                upsert_portal_map(
                    conn,
                    client_id=str(row["client_id"]),
                    customer_id=int(row["customer_id"]),
                )
    print("Done.")


if __name__ == "__main__":
    main()
