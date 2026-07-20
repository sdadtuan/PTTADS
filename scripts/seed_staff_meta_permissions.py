#!/usr/bin/env python3
"""Seed crm_facebook_ads section permissions for media positions in PostgreSQL."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

META_CAPS: dict[str, list[str]] = {
    "MKT-01": ["view", "edit", "create", "configure"],
    "MKT-02": ["view", "edit"],
    "AM-01": ["view"],
}


def _position_ids(sqlite_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        out: dict[str, int] = {}
        for code in META_CAPS:
            row = conn.execute(
                """
                SELECT id FROM crm_positions
                WHERE lower(trim(code)) = lower(trim(?)) AND active = 1
                LIMIT 1
                """,
                (code,),
            ).fetchone()
            if row:
                out[code] = int(row["id"])
        return out
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed staff PG permissions for crm_facebook_ads")
    parser.add_argument("--sqlite", default=str(ROOT / "ptt.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        print(f"SQLite not found: {sqlite_path}", file=sys.stderr)
        return 1

    positions = _position_ids(sqlite_path)
    if not positions:
        print("No MKT/AM positions found in SQLite", file=sys.stderr)
        return 1

    rows: list[tuple[int, str, str]] = []
    for code, caps in META_CAPS.items():
        pid = positions.get(code)
        if pid is None:
            print(f"WARN  skip {code} — position not in SQLite", file=sys.stderr)
            continue
        for action in caps:
            rows.append((pid, "crm_facebook_ads", action))

    if args.dry_run:
        for pid, section, action in rows:
            print(f"would upsert position_id={pid} {section}.{action}")
        return 0

    from ptt_jobs.db import pg_available, pg_connection

    if not pg_available():
        print("PostgreSQL unavailable — set DATABASE_URL", file=sys.stderr)
        return 1

    with pg_connection() as conn:
        with conn.cursor() as cur:
            for pid, section, action in rows:
                cur.execute(
                    """
                    INSERT INTO staff_section_permissions (position_id, section_id, action)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (position_id, section_id, action) DO NOTHING
                    """,
                    (pid, section, action),
                )
        conn.commit()
    print(f"Seeded {len(rows)} crm_facebook_ads permission rows for {list(positions.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
