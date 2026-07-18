#!/usr/bin/env python3
"""Seed portal pilot users with scrypt password hashes (Phase 3 prod cutover)."""
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

from ptt_jobs.db import pg_connection


def hash_password(plain: str, *, allow_plain_fallback: bool = False) -> str:
    try:
        salt = secrets.token_bytes(16)
        key = hashlib.scrypt(plain.encode(), salt=salt, n=16384, r=8, p=1, dklen=64)
        return f"scrypt:{base64.b64encode(salt).decode()}:{base64.b64encode(key).decode()}"
    except AttributeError:
        if not allow_plain_fallback:
            raise SystemExit(
                "hashlib.scrypt unavailable — use Python 3.11+ on VPS for prod pilot users, "
                "or set PTT_PILOT_SEED_ALLOW_PLAIN=1 for local dry-run only"
            )
        return f"plain:{plain}"


PILOT_USERS = [
    {
        "email": "viewer.pilot1@pttads.vn",
        "client_id": "550e8400-e29b-41d4-a716-446655440000",
        "role": "viewer",
    },
    {
        "email": "approver.pilot1@pttads.vn",
        "client_id": "550e8400-e29b-41d4-a716-446655440000",
        "role": "approver",
    },
    {
        "email": "viewer.pilot2@pttads.vn",
        "client_id": "660e8400-e29b-41d4-a716-446655440001",
        "role": "viewer",
    },
    {
        "email": "approver.pilot2@pttads.vn",
        "client_id": "660e8400-e29b-41d4-a716-446655440001",
        "role": "approver",
    },
    {
        "email": "approver.pilot3@pttads.vn",
        "client_id": "770e8400-e29b-41d4-a716-446655440002",
        "role": "approver",
    },
]


def ensure_pilot_clients() -> None:
    pilots = [
        ("550e8400-e29b-41d4-a716-446655440000", "PILOT1", "Pilot Client 1"),
        ("660e8400-e29b-41d4-a716-446655440001", "PILOT2", "Pilot Client 2"),
        ("770e8400-e29b-41d4-a716-446655440002", "PILOT3", "Pilot Client 3"),
    ]
    with pg_connection() as conn:
        with conn.cursor() as cur:
            for cid, code, name in pilots:
                cur.execute(
                    """
                    INSERT INTO clients (id, code, name, status)
                    VALUES (%s::uuid, %s, %s, 'active')
                    ON CONFLICT (id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name
                    """,
                    (cid, code, name),
                )
        conn.commit()


def seed_users(password: str, *, allow_plain_fallback: bool = False) -> int:
    ensure_pilot_clients()
    count = 0
    pwd_hash = hash_password(password, allow_plain_fallback=allow_plain_fallback)
    with pg_connection() as conn:
        with conn.cursor() as cur:
            for u in PILOT_USERS:
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
                    (u["client_id"], u["email"], pwd_hash, u["role"]),
                )
                count += 1
        conn.commit()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Phase 3 portal pilot users (scrypt)")
    parser.add_argument(
        "--password",
        default=os.environ.get("PORTAL_PILOT_PASSWORD", ""),
        help="Shared initial password (rotate after first login)",
    )
    args = parser.parse_args()
    if not args.password or len(args.password) < 8:
        raise SystemExit("Provide --password (min 8 chars) or PORTAL_PILOT_PASSWORD")

    allow_plain = os.environ.get("PTT_PILOT_SEED_ALLOW_PLAIN", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    n = seed_users(args.password, allow_plain_fallback=allow_plain)
    print(
        f"OK  Seeded {n} portal pilot users. Disable PTT_PORTAL_STUB_USERS on prod."
        + (" (plain fallback — VPS prod needs Python 3.11+ scrypt)" if allow_plain else "")
    )


if __name__ == "__main__":
    main()
