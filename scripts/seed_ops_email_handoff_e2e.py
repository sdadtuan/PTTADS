#!/usr/bin/env python3
"""Seed Email pilot data for ops-web §13 handoff Playwright E2E."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DOMAIN = "handoff-email.example.com"
DEFAULT_CONTACT = "handoff-email@example.com"


def _first_client_id(conn) -> str:
    cur = conn.cursor()
    cur.execute("SELECT id::text FROM clients ORDER BY created_at ASC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    if not row:
        raise RuntimeError("No clients row — seed agency client first")
    return str(row[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ops-web Email handoff E2E pilot")
    parser.add_argument("--apply", action="store_true", help="Write to database")
    parser.add_argument("--client-id", default=os.environ.get("OPS_EMAIL_HANDOFF_CLIENT_ID", ""))
    parser.add_argument("--domain", default=os.environ.get("OPS_EMAIL_HANDOFF_DOMAIN", DEFAULT_DOMAIN))
    parser.add_argument("--contact-email", default=DEFAULT_CONTACT)
    args = parser.parse_args()

    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        print("DATABASE_URL missing", file=sys.stderr)
        sys.exit(1)

    import psycopg2

    conn = psycopg2.connect(db_url)
    client_id = args.client_id.strip() or _first_client_id(conn)
    from_email = f"noreply@{args.domain}"
    payload = {
        "client_id": client_id,
        "domain": args.domain,
        "from_email": from_email,
        "contact_email": args.contact_email,
        "workspace_name": "Handoff E2E Workspace",
    }
    print(json.dumps(payload, ensure_ascii=False))

    if not args.apply:
        print("Dry-run — pass --apply to write", file=sys.stderr)
        conn.close()
        return

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO email_mkt.workspaces (
            client_id, name, default_from_name, default_from_email,
            default_reply_to, esp_provider, timezone, status
        ) VALUES (
            %s::uuid, %s, %s, %s, %s, 'sendgrid', 'Asia/Ho_Chi_Minh', 'active'
        )
        ON CONFLICT (client_id) DO UPDATE SET
            default_from_email = EXCLUDED.default_from_email,
            default_from_name = EXCLUDED.default_from_name,
            updated_at = NOW()
        RETURNING id::text
        """,
        (client_id, payload["workspace_name"], "Handoff E2E", from_email, from_email),
    )
    workspace_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO email_mkt.contacts (
            client_id, email, email_normalized, first_name, lifecycle_stage
        ) VALUES (%s::uuid, %s, lower(%s), %s, 'subscriber')
        ON CONFLICT (client_id, email_normalized) DO UPDATE SET
            first_name = EXCLUDED.first_name,
            updated_at = NOW()
        RETURNING id::text
        """,
        (client_id, args.contact_email, args.contact_email, "Handoff"),
    )
    contact_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO email_mkt.consent_records (
            client_id, contact_id, email, status, source, legal_basis, recorded_at
        )
        SELECT %s::uuid, %s::uuid, %s, 'opted_in', 'handoff_e2e', 'consent', NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM email_mkt.consent_records
            WHERE client_id = %s::uuid AND email = %s AND status = 'opted_in'
        )
        """,
        (client_id, contact_id, args.contact_email, client_id, args.contact_email),
    )
    conn.commit()
    cur.close()
    conn.close()

    payload["workspace_id"] = workspace_id
    payload["contact_id"] = contact_id
    print(json.dumps({"ok": True, **payload}, ensure_ascii=False), file=sys.stderr)
    print(f"OPS_EMAIL_HANDOFF_CLIENT_ID={client_id}", file=sys.stderr)


if __name__ == "__main__":
    main()
