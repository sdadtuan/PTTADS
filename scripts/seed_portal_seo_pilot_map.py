#!/usr/bin/env python3
"""Seed seo_portal_client_map for portal SEO pilot (Phase 5C)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ptt_jobs.db import pg_available, pg_connection
from ptt_seo.db import seo_write
from ptt_seo.portal_bridge import upsert_portal_map

DEFAULT_MAPS = [
    ("550e8400-e29b-41d4-a716-446655440000", 1),
    ("660e8400-e29b-41d4-a716-446655440001", 2),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed portal client → SEO customer map")
    parser.add_argument("--apply", action="store_true", help="Write to database")
    parser.add_argument("--client-id", action="append", dest="client_ids", default=[])
    parser.add_argument("--customer-id", type=int, action="append", dest="customer_ids", default=[])
    args = parser.parse_args()

    maps = list(DEFAULT_MAPS)
    if args.client_ids:
        if len(args.client_ids) != len(args.customer_ids):
            raise SystemExit("Provide matching --client-id and --customer-id pairs")
        maps = list(zip(args.client_ids, args.customer_ids, strict=True))

    for client_id, customer_id in maps:
        print(f"  {client_id} → customer_id={customer_id}")

    if not args.apply:
        print("Dry-run — pass --apply to write")
        return

    os.environ.setdefault("SEO_AEO_DB", "pg" if pg_available() else "sqlite")
    with seo_write() as conn:
        for client_id, customer_id in maps:
            upsert_portal_map(conn, client_id=client_id, customer_id=int(customer_id))
    print("Done.")


if __name__ == "__main__":
    main()
