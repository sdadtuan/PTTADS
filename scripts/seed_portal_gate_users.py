#!/usr/bin/env python3
"""Seed portal gate users (approver@demo.local / viewer@demo.local) for local MVP."""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"

GATE_USERS = [
    ("viewer@demo.local", "viewer"),
    ("approver@demo.local", "approver"),
]


def hash_password(plain: str) -> str:
    """Dev gate seed — plain: prefix allowed when NODE_ENV != production."""
    try:
        salt = secrets.token_bytes(16)
        key = hashlib.scrypt(plain.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
        return f"scrypt:{base64.b64encode(salt).decode()}:{base64.b64encode(key).decode()}"
    except AttributeError:
        return f"plain:{plain}"


def seed(password: str, client_id: str) -> int:
    from ptt_jobs.db import pg_connection

    pwd_hash = hash_password(password)
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (id, code, name, status)
                VALUES (%s::uuid, 'PORTAL_DEMO', 'Portal Demo Client', 'active')
                ON CONFLICT (id) DO UPDATE SET status = 'active'
                """,
                (client_id,),
            )
            for email, role in GATE_USERS:
                cur.execute(
                    """
                    INSERT INTO portal_client_users (client_id, email, password_hash, role, active)
                    VALUES (%s::uuid, LOWER(%s), %s, %s, TRUE)
                    ON CONFLICT (email) DO UPDATE SET
                        client_id = EXCLUDED.client_id,
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        active = TRUE,
                        updated_at = NOW()
                    """,
                    (client_id, email, pwd_hash, role),
                )
        conn.commit()
    return len(GATE_USERS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", default=os.environ.get("PORTAL_GATE_PASSWORD", "demo123"))
    parser.add_argument("--client-id", default=os.environ.get("PORTAL_DEMO_CLIENT_ID", DEFAULT_CLIENT))
    args = parser.parse_args()
    os.environ.setdefault("DATABASE_URL", "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency")
    n = seed(args.password, args.client_id)
    print(f"OK  Seeded {n} gate users (approver@demo.local / viewer@demo.local) password={args.password!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
