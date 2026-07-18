#!/usr/bin/env python3
"""Seed Meta ad account + encrypted token for a client (Phase 2 M1).

Usage:
  export PTT_TOKEN_VAULT_KEY="$(python3 -c 'import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  export DATABASE_URL=postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency
  CLIENT_CODE=DEMO META_AD_ACCOUNT_ID=act_1234567890 META_ACCESS_TOKEN=EAAx... \\
    .venv/bin/python scripts/seed_meta_channel_account.py

Optional:
  TOKEN_EXPIRES=2026-12-31  DISPLAY_NAME="Demo Meta"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    client_code = (os.environ.get("CLIENT_CODE") or os.environ.get("PTT_CLIENT_CODE") or "").strip()
    ad_account = (os.environ.get("META_AD_ACCOUNT_ID") or os.environ.get("META_ACT_ID") or "").strip()
    token = (os.environ.get("META_ACCESS_TOKEN") or os.environ.get("PTT_META_ACCESS_TOKEN") or "").strip()
    expires = (os.environ.get("TOKEN_EXPIRES") or os.environ.get("META_TOKEN_EXPIRES") or "").strip() or None
    display = (os.environ.get("DISPLAY_NAME") or f"Meta {client_code}").strip()

    if not client_code:
        print("FAIL thiếu CLIENT_CODE", file=sys.stderr)
        return 1
    if not ad_account:
        print("FAIL thiếu META_AD_ACCOUNT_ID", file=sys.stderr)
        return 1
    if not token:
        print("FAIL thiếu META_ACCESS_TOKEN", file=sys.stderr)
        return 1

    from ptt_agency.channel_vault import vault_columns_ready
    from ptt_agency.clients import add_channel_account
    from ptt_jobs.db import pg_available

    if not pg_available():
        print("FAIL PostgreSQL unavailable", file=sys.stderr)
        return 1
    if not vault_columns_ready():
        print("FAIL DDL v3 chưa apply — ./scripts/apply_pg_ddl_v3.sh", file=sys.stderr)
        return 1
    if not os.environ.get("PTT_TOKEN_VAULT_KEY"):
        print("FAIL thiếu PTT_TOKEN_VAULT_KEY", file=sys.stderr)
        return 1

    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM clients WHERE code = %s LIMIT 1", (client_code.upper(),))
            row = cur.fetchone()
            if not row:
                print(f"FAIL client code {client_code} not found", file=sys.stderr)
                return 1
            client_id = str(row[0])

    out = add_channel_account(
        client_id,
        channel="meta",
        external_account_id=ad_account,
        display_name=display,
        access_token=token,
        token_expires_at=expires,
        pixel_id=(os.environ.get("META_PIXEL_ID") or os.environ.get("PTT_META_PIXEL_ID") or "").strip(),
    )
    print(f"OK  seeded meta account client={client_code} id={out.get('id')} status={out.get('token_status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
