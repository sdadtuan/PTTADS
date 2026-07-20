#!/usr/bin/env python3
"""Verify SEO/AEO PG cutover readiness + GSC/GA4 OAuth env (UAT helper)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def _fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def check_env() -> list[str]:
    errors: list[str] = []
    seo_db = (os.environ.get("SEO_AEO_DB") or "sqlite").strip().lower()
    print(f"\n==> SEO_AEO_DB={seo_db}")
    if seo_db not in {"pg", "dual", "sqlite"}:
        errors.append(f"invalid SEO_AEO_DB={seo_db}")

    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if seo_db in {"pg", "dual"} and not db_url:
        errors.append("DATABASE_URL required when SEO_AEO_DB=pg|dual")
        _fail("DATABASE_URL missing")
    elif db_url:
        _ok(f"DATABASE_URL set ({db_url[:40]}...)")

    gsc_vars = ["PTT_GSC_OAUTH_CLIENT_ID", "PTT_GSC_OAUTH_CLIENT_SECRET", "PTT_GSC_OAUTH_REDIRECT_URI"]
    ga4_vars = ["PTT_GA4_OAUTH_CLIENT_ID", "PTT_GA4_OAUTH_CLIENT_SECRET", "PTT_GA4_OAUTH_REDIRECT_URI"]
    for name in gsc_vars:
        if os.environ.get(name) or (name.endswith("_ID") and os.environ.get("PTT_GOOGLE_ADS_CLIENT_ID")):
            _ok(f"{name} (or fallback)")
        else:
            _warn(f"{name} not set — GSC OAuth will fail")
    for name in ga4_vars:
        if os.environ.get(name) or os.environ.get("PTT_GSC_OAUTH_CLIENT_ID"):
            _ok(f"{name} (or GSC/Google fallback)")
        else:
            _warn(f"{name} not set — GA4 OAuth may fail")

    for flag, label in [
        ("PTT_GSC_SYNC_ENABLED", "GSC daily sync"),
        ("PTT_GA4_SYNC_ENABLED", "GA4 daily sync"),
        ("PTT_TOKEN_VAULT_KEY", "token vault"),
    ]:
        val = os.environ.get(flag, "")
        if val:
            _ok(f"{flag}=1")
        else:
            _warn(f"{flag} not set ({label})")

    return errors


def check_pg_schema() -> list[str]:
    errors: list[str] = []
    print("\n==> PostgreSQL schema")
    try:
        from ptt_jobs.db import pg_available, pg_connection
        from ptt_seo.pg_schema import ensure_pg_schema, pg_seo_ready
    except ImportError as exc:
        errors.append(str(exc))
        _fail(f"import error: {exc}")
        return errors

    if not pg_available():
        errors.append("pg unavailable")
        _fail("PostgreSQL unavailable")
        return errors

    required_tables = (
        "seo_client_settings",
        "seo_gsc_daily_stats",
        "seo_ga4_daily_stats",
        "seo_ai_mentions",
        "seo_content_freshness",
        "seo_authority_signals",
    )
    with pg_connection() as pg:
        ensure_pg_schema(pg)
        if not pg_seo_ready(pg):
            errors.append("pg_seo_ready false")
            _fail("seo_aeo schema not ready")
            return errors
        with pg.cursor() as cur:
            cur.execute("SET search_path TO seo_aeo, public")
            for table in required_tables:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'seo_aeo' AND table_name = %s
                    """,
                    (table,),
                )
                if cur.fetchone():
                    _ok(f"table seo_aeo.{table}")
                else:
                    errors.append(f"missing table {table}")
                    _fail(f"missing seo_aeo.{table}")
    return errors


def check_row_counts() -> list[str]:
    errors: list[str] = []
    print("\n==> SQLite → PG row counts")
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migrate_sqlite_seo_aeo_to_pg",
        root / "scripts" / "migrate_sqlite_seo_aeo_to_pg.py",
    )
    if spec is None or spec.loader is None:
        _fail("cannot load migrate script")
        return ["migrate script load failed"]
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    import sqlite3

    sp = mod._sqlite_path()
    if not sp.is_file():
        _warn(f"SQLite not found: {sp} — skip count verify")
        return errors

    conn = sqlite3.connect(str(sp))
    conn.row_factory = sqlite3.Row
    try:
        counts = mod.verify_counts(conn)
        for table, c in counts.items():
            sq, pg = c["sqlite"], c["postgres"]
            if sq == pg:
                _ok(f"{table}: {pg}")
            elif sq == 0 and pg >= 0:
                _ok(f"{table}: sqlite=0 pg={pg} (PG-only data OK)")
            else:
                _warn(f"{table}: sqlite={sq} pg={pg} MISMATCH")
    except Exception as exc:
        errors.append(str(exc))
        _fail(str(exc))
    finally:
        conn.close()
    return errors


def check_oauth_urls(customer_id: int) -> list[str]:
    errors: list[str] = []
    print(f"\n==> OAuth URL smoke (customer_id={customer_id})")
    try:
        from ptt_seo.connectors.gsc_oauth import authorization_url as gsc_url
        from ptt_seo.connectors.ga4_oauth import authorization_url as ga4_url

        gsc = gsc_url(customer_id=customer_id, site_url="https://example.com/")
        ga4 = ga4_url(customer_id=customer_id, property_id="123456789")
        if gsc.startswith("https://accounts.google.com"):
            _ok("GSC authorization_url generated")
        else:
            errors.append("invalid gsc url")
            _fail("GSC URL invalid")
        if ga4.startswith("https://accounts.google.com"):
            _ok("GA4 authorization_url generated")
        else:
            errors.append("invalid ga4 url")
            _fail("GA4 URL invalid")
        if os.environ.get("VERBOSE"):
            print(json.dumps({"gsc_url": gsc[:120] + "...", "ga4_url": ga4[:120] + "..."}, indent=2))
    except ValueError as exc:
        _fail(f"OAuth env: {exc}")
        errors.append(str(exc))
    except Exception as exc:
        _fail(str(exc))
        errors.append(str(exc))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="SEO/AEO PG + OAuth UAT verification")
    parser.add_argument("--customer-id", type=int, default=1, help="Pilot customer for OAuth URL test")
    parser.add_argument("--skip-counts", action="store_true")
    parser.add_argument("--skip-oauth", action="store_true")
    args = parser.parse_args()

    print("SEO/AEO production cutover + OAuth UAT verification")
    all_errors: list[str] = []
    all_errors.extend(check_env())
    all_errors.extend(check_pg_schema())
    if not args.skip_counts:
        all_errors.extend(check_row_counts())
    if not args.skip_oauth:
        all_errors.extend(check_oauth_urls(args.customer_id))

    print("\n==> Summary")
    if all_errors:
        print(f"FAILED — {len(all_errors)} issue(s)")
        sys.exit(1)
    print("PASSED — ready for cutover UAT (manual OAuth browser flow still required)")
    sys.exit(0)


if __name__ == "__main__":
    main()
