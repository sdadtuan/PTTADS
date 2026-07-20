#!/usr/bin/env python3
"""Seed SQLite Hub + SOP rows for Phase 3 Track D gate (idempotent)."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CAMPAIGN_CODE = "HUB-GATE-DEMO"
DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"


def _sqlite_path() -> Path:
    raw = (os.environ.get("PTT_SQLITE_PATH") or "ptt.db").strip()
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _ensure_schemas(conn: sqlite3.Connection) -> None:
    from ptt_crm.crm_hub_sop_schema import ensure_crm_hub_schema, ensure_crm_sop_schema

    ensure_crm_hub_schema(conn)
    ensure_crm_sop_schema(conn)
    conn.commit()


def _seed_campaign(conn: sqlite3.Connection, *, client_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM crm_campaigns WHERE lower(trim(code)) = lower(trim(?))",
        (DEFAULT_CAMPAIGN_CODE,),
    ).fetchone()
    if row:
        return {"campaign_id": int(row["id"]), "created": False}

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = ts[:10]
    cur = conn.execute(
        """
        INSERT INTO crm_campaigns (
            code, name, channel, external_ref, utm_campaign, notes, active,
            agency_client_id, target_cpl_vnd, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        """,
        (
            DEFAULT_CAMPAIGN_CODE,
            "Hub PG Gate Demo",
            "meta",
            "120330123456789012",
            "hub_gate_demo",
            "Phase 3 Track D gate seed",
            client_id,
            120000,
            date,
            ts,
        ),
    )
    return {"campaign_id": int(cur.lastrowid), "created": True}


def _seed_sop_run(conn: sqlite3.Connection, *, campaign_id: int, template_id: int) -> dict:
    existing = conn.execute(
        "SELECT id FROM crm_sop_runs WHERE campaign_id = ? LIMIT 1",
        (campaign_id,),
    ).fetchone()
    if existing:
        return {"run_id": int(existing["id"]), "created": False}

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = ts[:10]
    cur = conn.execute(
        """
        INSERT INTO crm_sop_runs (
            template_id, campaign_id, name, status, start_date, notes, created_at, updated_at
        ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
        """,
        (
            template_id,
            campaign_id,
            "Hub PG Gate SOP Run",
            date,
            "Gate seed run",
            date,
            ts,
        ),
    )
    run_id = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO crm_sop_run_tasks (
            run_id, step_id, position, title, description, role, due_date, status,
            notes, checklist_json, created_at, updated_at
        ) VALUES (?, NULL, 0, ?, ?, 'any', ?, 'todo', '', '[]', ?, ?)
        """,
        (run_id, "Gate checklist task", "Verify Hub PG read path", date, date, ts),
    )
    return {"run_id": run_id, "created": True}


def bootstrap(*, client_id: str) -> dict:
    db = _sqlite_path()
    if not db.is_file():
        raise SystemExit(f"SQLite not found: {db}")

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schemas(conn)
        camp = _seed_campaign(conn, client_id=client_id)
        from crm_sop_seed import seed_launch_campaign_sop_template

        sop = seed_launch_campaign_sop_template(conn)
        run = _seed_sop_run(conn, campaign_id=camp["campaign_id"], template_id=sop["template_id"])
        conn.commit()
    finally:
        conn.close()

    return {
        "sqlite_path": str(db),
        "campaign": camp,
        "sop_template": sop,
        "sop_run": run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Hub/SOP gate data in SQLite")
    parser.add_argument("--client-id", default=os.environ.get("HUB_GATE_CLIENT_ID", DEFAULT_CLIENT))
    args = parser.parse_args()
    out = bootstrap(client_id=args.client_id)
    print(
        f"OK  campaign_id={out['campaign']['campaign_id']} "
        f"sop_template_id={out['sop_template']['template_id']} "
        f"sop_run_id={out['sop_run']['run_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
