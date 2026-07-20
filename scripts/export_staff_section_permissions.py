#!/usr/bin/env python3
"""Export SQLite crm_position_section_permissions → PG staff_section_permissions."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Export staff section permissions to PG SQL")
    parser.add_argument("--sqlite", default=str(ROOT / "ptt.db"), help="SQLite path")
    parser.add_argument("--apply", action="store_true", help="Upsert into PostgreSQL")
    args = parser.parse_args()

    db_path = Path(args.sqlite)
    if not db_path.is_file():
        print(f"SQLite not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT position_id, section_id, action
            FROM crm_position_section_permissions
            ORDER BY position_id, section_id, action
            """
        ).fetchall()
    except sqlite3.OperationalError as exc:
        print(f"Table missing: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    if not rows:
        print("No rows to export")
        return 0

    statements = [
        "BEGIN;",
        "DELETE FROM staff_section_permissions;",
    ]
    for row in rows:
        pid = int(row["position_id"])
        section = str(row["section_id"]).replace("'", "''")
        action = str(row["action"] or "view").replace("'", "''")
        statements.append(
            f"INSERT INTO staff_section_permissions (position_id, section_id, action) "
            f"VALUES ({pid}, '{section}', '{action}') "
            f"ON CONFLICT (position_id, section_id, action) DO NOTHING;"
        )
    statements.append("COMMIT;")
    sql = "\n".join(statements)

    if args.apply:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            print("PostgreSQL unavailable — set DATABASE_URL", file=sys.stderr)
            return 1
        with pg_connection() as pg:
            with pg.cursor() as cur:
                for stmt in statements:
                    if stmt in {"BEGIN;", "COMMIT;"}:
                        continue
                    cur.execute(stmt)
            pg.commit()
        print(f"Applied {len(rows)} permission rows to PG")
        return 0

    print(sql)
    print(f"-- total rows: {len(rows)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
