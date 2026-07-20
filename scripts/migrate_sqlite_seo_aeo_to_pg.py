#!/usr/bin/env python3
"""One-way SQLite seo_* → PostgreSQL seo_aeo.* (Phase 3.5 cutover)."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from ptt_jobs.db import pg_available, pg_connection
from ptt_seo.pg_schema import ensure_pg_schema, pg_seo_ready


SEO_TABLES: tuple[str, ...] = (
    "seo_client_settings",
    "seo_projects",
    "seo_initiatives",
    "seo_keywords",
    "seo_questions",
    "seo_content",
    "seo_content_versions",
    "seo_content_approvals",
    "seo_audit_log",
    "seo_technical_issues",
    "seo_sync_runs",
    "seo_gsc_daily_stats",
    "seo_ga4_daily_stats",
    "seo_ai_mentions",
    "seo_content_freshness",
    "seo_authority_signals",
    "seo_alerts",
)

JSON_COLUMNS: dict[str, frozenset[str]] = {
    "seo_client_settings": frozenset(
        {
            "domains_json",
            "markets_json",
            "languages_json",
            "brand_guidelines_json",
            "seo_guidelines_json",
            "aeo_guidelines_json",
            "integrations_json",
        }
    ),
    "seo_content": frozenset({"brief_json", "outline_json"}),
    "seo_audit_log": frozenset({"payload_json"}),
    "seo_sync_runs": frozenset({"payload_json"}),
    "seo_ai_mentions": frozenset(),
    "seo_content_freshness": frozenset({"signals_json"}),
    "seo_authority_signals": frozenset(),
}


def _sqlite_path() -> Path:
    raw = (os.environ.get("PTT_SQLITE_PATH") or "ptt.db").strip()
    p = Path(raw)
    return p if p.is_absolute() else Path(__file__).resolve().parents[1] / p


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _row_to_pg(table: str, rec: dict[str, Any]) -> dict[str, Any]:
    out = dict(rec)
    for col in JSON_COLUMNS.get(table, frozenset()):
        if col not in out or out[col] is None:
            continue
        val = out[col]
        if isinstance(val, (dict, list)):
            out[col] = json.dumps(val, ensure_ascii=False)
        elif not isinstance(val, str):
            out[col] = json.dumps(val, ensure_ascii=False)
        else:
            try:
                json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def migrate_table(sqlite: sqlite3.Connection, table: str, *, dry_run: bool = False) -> int:
    if not _table_exists(sqlite, table):
        return 0
    cols = [d[0] for d in sqlite.execute(f"SELECT * FROM {table} LIMIT 0").description]
    rows = sqlite.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    if not rows or dry_run:
        return len(rows)

    count = 0
    with pg_connection() as pg:
        with pg.cursor() as cur:
            cur.execute("SET search_path TO seo_aeo, public")
            for row in rows:
                rec = _row_to_pg(table, dict(zip(cols, row)))
                keys = list(rec.keys())
                placeholders = ", ".join(f"%({k})s" for k in keys)
                col_list = ", ".join(keys)
                updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in keys if k != "id")
                sql = f"""
                    INSERT INTO {table} ({col_list})
                    VALUES ({placeholders})
                    ON CONFLICT (id) DO UPDATE SET {updates}
                """
                if table == "seo_client_settings":
                    sql = f"""
                        INSERT INTO {table} ({col_list})
                        VALUES ({placeholders})
                        ON CONFLICT (customer_id) DO UPDATE SET {updates}
                    """
                elif table == "seo_gsc_daily_stats":
                    sql = f"""
                        INSERT INTO {table} ({col_list})
                        VALUES ({placeholders})
                        ON CONFLICT (customer_id, stat_date, query, page) DO UPDATE SET {updates}
                    """
                elif table == "seo_ga4_daily_stats":
                    sql = f"""
                        INSERT INTO {table} ({col_list})
                        VALUES ({placeholders})
                        ON CONFLICT (customer_id, stat_date, landing_page, source_medium) DO UPDATE SET {updates}
                    """
                elif table == "seo_content_freshness":
                    sql = f"""
                        INSERT INTO {table} ({col_list})
                        VALUES ({placeholders})
                        ON CONFLICT (customer_id, content_id) DO UPDATE SET {updates}
                    """
                elif table == "seo_authority_signals":
                    sql = f"""
                        INSERT INTO {table} ({col_list})
                        VALUES ({placeholders})
                        ON CONFLICT (customer_id, signal_type, source_url, target_url) DO UPDATE SET {updates}
                    """
                cur.execute(sql, rec)
                count += 1
            if table != "seo_client_settings" and count:
                cur.execute(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence('seo_aeo.{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM seo_aeo.{table}), 1)
                    )
                    """
                )
        pg.commit()
    return count


def verify_counts(sqlite: sqlite3.Connection) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    with pg_connection() as pg:
        with pg.cursor() as cur:
            cur.execute("SET search_path TO seo_aeo, public")
            for table in SEO_TABLES:
                sq = 0
                if _table_exists(sqlite, table):
                    sq = sqlite.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()[0]
                cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
                pg_count = int(cur.fetchone()[0])
                report[table] = {"sqlite": int(sq), "postgres": pg_count}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite SEO/AEO tables to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Count rows only")
    parser.add_argument("--verify-only", action="store_true", help="Compare row counts")
    args = parser.parse_args()

    if not pg_available():
        raise SystemExit("PostgreSQL unavailable — set DATABASE_URL and ensure psycopg2")

    sqlite_path = _sqlite_path()
    if not sqlite_path.is_file():
        raise SystemExit(f"SQLite not found: {sqlite_path}")

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        with pg_connection() as pg:
            ensure_pg_schema(pg)
            if not pg_seo_ready(pg):
                raise SystemExit("PG schema apply failed")

        if args.verify_only:
            counts = verify_counts(conn)
            for table, c in counts.items():
                ok = "OK" if c["sqlite"] == c["postgres"] else "MISMATCH"
                print(f"{table}: sqlite={c['sqlite']} pg={c['postgres']} [{ok}]")
            return

        total = 0
        for table in SEO_TABLES:
            n = migrate_table(conn, table, dry_run=args.dry_run)
            total += n
            print(f"{table}: {n} rows{' (dry-run)' if args.dry_run else ''}")

        if not args.dry_run:
            counts = verify_counts(conn)
            mismatches = [t for t, c in counts.items() if c["sqlite"] != c["postgres"]]
            if mismatches:
                print("WARNING: count mismatch:", ", ".join(mismatches))
            else:
                print("Verify OK — all table counts match")
        print(f"Done — {total} rows processed")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
