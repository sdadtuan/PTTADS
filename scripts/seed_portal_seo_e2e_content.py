#!/usr/bin/env python3
"""Seed portal SEO E2E / pilot UAT data (map + client_review content)."""
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
from ptt_seo.db import seo_write
from ptt_seo.portal_bridge import seed_e2e_client_review_content, upsert_portal_map

DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"
DEFAULT_CUSTOMER = 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed portal SEO E2E client_review content")
    parser.add_argument("--apply", action="store_true", help="Write to database")
    parser.add_argument("--client-id", default=DEFAULT_CLIENT)
    parser.add_argument("--customer-id", type=int, default=DEFAULT_CUSTOMER)
    parser.add_argument("--title", default="", help="Optional fixed title for E2E")
    args = parser.parse_args()

    if not args.apply:
        print(json.dumps({"client_id": args.client_id, "customer_id": args.customer_id, "title": args.title or None}, indent=2))
        print("Dry-run — pass --apply to write")
        return

    os.environ.setdefault("SEO_AEO_DB", "pg" if pg_available() else "sqlite")
    with seo_write() as conn:
        upsert_portal_map(conn, client_id=args.client_id, customer_id=args.customer_id)
        item = seed_e2e_client_review_content(
            conn,
            customer_id=args.customer_id,
            title=args.title or None,
        )
    print(json.dumps({"ok": True, **item}, indent=2))


if __name__ == "__main__":
    main()
