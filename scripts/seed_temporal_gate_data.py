#!/usr/bin/env python3
"""Seed PG data for Temporal workflow gate pack."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"


def ensure_gate_client(client_id: str) -> None:
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (id, code, name, status)
                VALUES (%s::uuid, 'TEMPORAL_GATE', 'Temporal Gate Client', 'onboarding')
                ON CONFLICT (id) DO UPDATE SET status = 'onboarding'
                """,
                (client_id,),
            )
            cur.execute("SELECT seed_client_onboarding(%s::uuid)", (client_id,))
            cur.execute(
                """
                UPDATE client_onboarding_items
                SET completed = FALSE, completed_at = NULL, completed_by = NULL
                WHERE client_id = %s::uuid
                """,
                (client_id,),
            )
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", default=os.environ.get("TEMPORAL_GATE_CLIENT_ID", DEFAULT_CLIENT))
    args = parser.parse_args()
    os.environ.setdefault("DATABASE_URL", "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency")
    ensure_gate_client(args.client_id)
    print(f"OK  Temporal gate client ready (onboarding reset): {args.client_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
