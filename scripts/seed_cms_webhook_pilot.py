#!/usr/bin/env python3
"""Seed CMS webhook pilot target for a CRM customer."""
from __future__ import annotations

import argparse
import json
import sys

from ptt_seo.cms_pilot import default_pilot_webhook_url, pilot_target_payload, pilot_webhook_secret
from ptt_seo.cms_publish import get_cms_target, upsert_cms_target
from ptt_seo.db import seo_write


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure SEO CMS webhook pilot for a client")
    parser.add_argument("--customer-id", type=int, required=True)
    parser.add_argument("--webhook-url", default="", help="Override webhook URL")
    parser.add_argument("--secret", default="", help="Override bearer secret")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = pilot_target_payload(
        base_url=args.webhook_url or None,
        bearer_token=args.secret or None,
    )
    payload["auth"]["send_pilot_secret_header"] = True

    if args.dry_run:
        print(json.dumps({"customer_id": args.customer_id, "target": payload}, indent=2, ensure_ascii=False))
        return 0

    with seo_write() as conn:
        upsert_cms_target(conn, args.customer_id, payload)
        saved = get_cms_target(conn, args.customer_id)

    print(
        json.dumps(
            {
                "ok": True,
                "customer_id": args.customer_id,
                "webhook_url": saved.get("base_url") if saved else payload["base_url"],
                "secret_hint": pilot_webhook_secret()[:4] + "…",
                "defaults_url": default_pilot_webhook_url(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
