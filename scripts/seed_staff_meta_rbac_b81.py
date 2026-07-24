#!/usr/bin/env python3
"""Seed granular Meta RBAC caps for B8.1 (Buyer vs Tracking)."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# position code -> list of (section, action)
RBAC_SEED: dict[str, list[tuple[str, str]]] = {
    # Media Buyer — submit writes, no approve, no tracking configure
    "MKT-02": [
        ("crm_facebook_ads", "view"),
        ("crm_facebook_ads", "edit"),
        ("meta_campaign_write", "view"),
        ("crm_board", "edit"),
    ],
    # Tracking / Tech — conversion rules + pixel configure
    "TECH-01": [
        ("crm_facebook_ads", "view"),
        ("crm_agency", "configure"),
    ],
    # AM / lead — approve writes
    "MKT-01": [
        ("crm_facebook_ads", "view"),
        ("crm_facebook_ads", "edit"),
        ("crm_facebook_ads", "configure"),
        ("meta_campaign_write", "view"),
        ("meta_campaign_write", "approve"),
        ("crm_agency", "configure"),
        ("crm_board", "edit"),
    ],
}


def _position_ids(sqlite_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        out: dict[str, int] = {}
        for code in RBAC_SEED:
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
    parser = argparse.ArgumentParser(description="Seed B8.1 Meta granular RBAC permissions")
    parser.add_argument("--sqlite", default=str(ROOT / "ptt.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.is_file():
        print(f"SQLite not found: {sqlite_path}", file=sys.stderr)
        return 1

    positions = _position_ids(sqlite_path)
    rows: list[tuple[int, str, str]] = []
    for code, caps in RBAC_SEED.items():
        pid = positions.get(code)
        if pid is None:
            print(f"WARN  skip {code} — position not in SQLite", file=sys.stderr)
            continue
        for section, action in caps:
            rows.append((pid, section, action))

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
    print(f"Seeded {len(rows)} B8.1 RBAC permission rows for {list(positions.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
