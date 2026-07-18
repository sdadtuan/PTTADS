#!/usr/bin/env python3
"""One-way SQLite Hub + SOP → PostgreSQL (Phase 3 Track D2/D3)."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ptt_crm.pg_schema import apply_ddl_v4_hub_sop, pg_hub_sop_ready, pg_v3_ready
from ptt_jobs.db import pg_connection


def _sqlite_path() -> Path:
    raw = (os.environ.get("PTT_SQLITE_PATH") or "ptt.db").strip()
    p = Path(raw)
    return p if p.is_absolute() else Path(__file__).resolve().parents[1] / p


def _now() -> datetime:
    return datetime.now(timezone.utc)


def migrate_hub_campaigns(conn: sqlite3.Connection) -> int:
    rows = conn.execute("SELECT * FROM crm_campaigns ORDER BY id").fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM crm_campaigns LIMIT 0").description]
    count = 0
    with pg_connection() as pg:
        with pg.cursor() as cur:
            for row in rows:
                rec = dict(zip(cols, row))
                cur.execute(
                    """
                    INSERT INTO hub_campaigns (
                        sqlite_campaign_id, code, name, channel, external_ref,
                        utm_campaign, notes, active, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (sqlite_campaign_id) DO UPDATE SET
                        code = EXCLUDED.code,
                        name = EXCLUDED.name,
                        channel = EXCLUDED.channel,
                        external_ref = EXCLUDED.external_ref,
                        utm_campaign = EXCLUDED.utm_campaign,
                        notes = EXCLUDED.notes,
                        active = EXCLUDED.active,
                        updated_at = NOW()
                    """,
                    (
                        int(rec["id"]),
                        rec.get("code") or "",
                        rec.get("name") or "",
                        rec.get("channel") or "other",
                        rec.get("external_ref") or "",
                        rec.get("utm_campaign") or "",
                        rec.get("notes") or "",
                        bool(int(rec.get("active") or 0)),
                    ),
                )
                count += 1
        pg.commit()
    return count


def migrate_sop(conn: sqlite3.Connection) -> dict[str, int]:
    stats = {"templates": 0, "steps": 0, "runs": 0, "tasks": 0}
    tpl_cols = [d[0] for d in conn.execute("SELECT * FROM crm_sop_templates LIMIT 0").description]
    tpl_pg: dict[int, int] = {}
    with pg_connection() as pg:
        with pg.cursor() as cur:
            for row in conn.execute("SELECT * FROM crm_sop_templates ORDER BY id"):
                rec = dict(zip(tpl_cols, row))
                cur.execute(
                    """
                    INSERT INTO sop_templates (
                        sqlite_template_id, code, name, channel, description, notes, active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sqlite_template_id) DO UPDATE SET
                        name = EXCLUDED.name, active = EXCLUDED.active, updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        int(rec["id"]),
                        rec.get("code") or "",
                        rec.get("name") or "",
                        rec.get("channel") or "other",
                        rec.get("description") or "",
                        rec.get("notes") or "",
                        bool(int(rec.get("active") or 1)),
                    ),
                )
                tpl_pg[int(rec["id"])] = int(cur.fetchone()[0])
                stats["templates"] += 1

            step_cols = [d[0] for d in conn.execute("SELECT * FROM crm_sop_steps LIMIT 0").description]
            for row in conn.execute("SELECT * FROM crm_sop_steps ORDER BY template_id, position"):
                rec = dict(zip(step_cols, row))
                tpl_id = tpl_pg.get(int(rec["template_id"]))
                if not tpl_id:
                    continue
                checklist = rec.get("checklist_json") or "[]"
                try:
                    checklist_obj = json.loads(checklist) if isinstance(checklist, str) else checklist
                except json.JSONDecodeError:
                    checklist_obj = []
                cur.execute(
                    """
                    INSERT INTO sop_steps (
                        sqlite_step_id, template_id, position, title, description,
                        offset_days, duration_days, role, required, checklist_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (sqlite_step_id) DO NOTHING
                    """,
                    (
                        int(rec["id"]),
                        tpl_id,
                        int(rec.get("position") or 0),
                        rec.get("title") or "",
                        rec.get("description") or "",
                        int(rec.get("offset_days") or 0),
                        int(rec.get("duration_days") or 1),
                        rec.get("role") or "any",
                        bool(int(rec.get("required") or 1)),
                        json.dumps(checklist_obj),
                    ),
                )
                stats["steps"] += 1

            run_cols = [d[0] for d in conn.execute("SELECT * FROM crm_sop_runs LIMIT 0").description]
            run_pg: dict[int, int] = {}
            for row in conn.execute("SELECT * FROM crm_sop_runs ORDER BY id"):
                rec = dict(zip(run_cols, row))
                hub_pg_id = None
                camp = rec.get("campaign_id")
                if camp:
                    cur.execute(
                        "SELECT id FROM hub_campaigns WHERE sqlite_campaign_id = %s LIMIT 1",
                        (int(camp),),
                    )
                    hub_row = cur.fetchone()
                    hub_pg_id = int(hub_row[0]) if hub_row else None
                tpl_pg_id = tpl_pg.get(int(rec["template_id"])) if rec.get("template_id") else None
                start = (rec.get("start_date") or "")[:10] or None
                cur.execute(
                    """
                    INSERT INTO sop_runs (
                        sqlite_run_id, hub_campaign_id, template_id, name, status, start_date, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s::date, %s)
                    ON CONFLICT (sqlite_run_id) DO UPDATE SET status = EXCLUDED.status, updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        int(rec["id"]),
                        hub_pg_id,
                        tpl_pg_id,
                        rec.get("name") or "",
                        rec.get("status") or "active",
                        start,
                        rec.get("notes") or "",
                    ),
                )
                run_pg[int(rec["id"])] = int(cur.fetchone()[0])
                stats["runs"] += 1

            task_cols = [d[0] for d in conn.execute("SELECT * FROM crm_sop_run_tasks LIMIT 0").description]
            for row in conn.execute("SELECT * FROM crm_sop_run_tasks ORDER BY run_id, position"):
                rec = dict(zip(task_cols, row))
                run_id = run_pg.get(int(rec["run_id"]))
                if not run_id:
                    continue
                checklist = rec.get("checklist_json") or "[]"
                try:
                    checklist_obj = json.loads(checklist) if isinstance(checklist, str) else checklist
                except json.JSONDecodeError:
                    checklist_obj = []
                due = (rec.get("due_date") or "")[:10] or None
                cur.execute(
                    """
                    INSERT INTO sop_run_tasks (
                        sqlite_task_id, run_id, step_id, position, title, description,
                        status, due_date, completed_at, assignee, checklist_json, notes
                    ) VALUES (%s, %s, NULL, %s, %s, %s, %s, %s::date, NULL, %s, %s::jsonb, %s)
                    ON CONFLICT (sqlite_task_id) DO NOTHING
                    """,
                    (
                        int(rec["id"]),
                        run_id,
                        int(rec.get("position") or 0),
                        rec.get("title") or "",
                        rec.get("description") or "",
                        rec.get("status") or "pending",
                        due,
                        rec.get("assignee") or "",
                        json.dumps(checklist_obj),
                        rec.get("notes") or "",
                    ),
                )
                stats["tasks"] += 1
        pg.commit()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite Hub/SOP → PostgreSQL")
    parser.add_argument("--apply-ddl", action="store_true", help="Apply DDL v4 before migrate")
    args = parser.parse_args()

    if args.apply_ddl:
        assert pg_v3_ready(), "Apply PG v3 first"
        apply_ddl_v4_hub_sop()
    assert pg_hub_sop_ready(), "DDL v4 not ready — run ./scripts/apply_pg_ddl_v4_hub_sop.sh"

    db = _sqlite_path()
    if not db.is_file():
        raise SystemExit(f"SQLite not found: {db}")

    conn = sqlite3.connect(str(db))
    try:
        hub_n = migrate_hub_campaigns(conn)
        sop_stats = migrate_sop(conn)
    finally:
        conn.close()

    print(json.dumps({"ok": True, "hub_campaigns": hub_n, **sop_stats}, indent=2))


if __name__ == "__main__":
    main()
