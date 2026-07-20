"""Hub + SOP SQLite schema — extracted from Flask monolith."""
from __future__ import annotations

import sqlite3


def _ensure_crm_campaigns_hub_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(crm_campaigns)").fetchall()}
    migrations = [
        ("agency_client_id", "ALTER TABLE crm_campaigns ADD COLUMN agency_client_id TEXT NOT NULL DEFAULT ''"),
        ("target_cpl_vnd", "ALTER TABLE crm_campaigns ADD COLUMN target_cpl_vnd INTEGER NOT NULL DEFAULT 0"),
        ("hub_map_synced_at", "ALTER TABLE crm_campaigns ADD COLUMN hub_map_synced_at TEXT NOT NULL DEFAULT ''"),
        ("hub_map_last_error", "ALTER TABLE crm_campaigns ADD COLUMN hub_map_last_error TEXT NOT NULL DEFAULT ''"),
    ]
    for name, sql in migrations:
        if name not in cols:
            conn.execute(sql)


def ensure_crm_hub_schema(conn: sqlite3.Connection) -> None:
    """Chiến dịch marketing, hợp đồng, nhắc nhở; gắn campaign_id lên crm_cases."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'other',
            external_ref TEXT NOT NULL DEFAULT '',
            utm_campaign TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_campaigns_code_nn
        ON crm_campaigns(code)
        WHERE TRIM(code) != ''
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_campaigns_active ON crm_campaigns(active, name)"
    )
    _ensure_crm_campaigns_hub_columns(conn)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES crm_customers(id),
            case_id INTEGER REFERENCES crm_cases(id) ON DELETE SET NULL,
            campaign_id INTEGER REFERENCES crm_campaigns(id) ON DELETE SET NULL,
            reference_code TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            signed_on TEXT NOT NULL DEFAULT '',
            starts_on TEXT NOT NULL DEFAULT '',
            ends_on TEXT NOT NULL DEFAULT '',
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            renewal_reminder_days INTEGER NOT NULL DEFAULT 30,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_contracts_customer ON crm_contracts(customer_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_contracts_dates ON crm_contracts(status, ends_on)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            ref_id INTEGER NOT NULL DEFAULT 0,
            reminder_kind TEXT NOT NULL DEFAULT 'manual',
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            remind_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            staff_id INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            meta_json TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_reminders_due ON crm_reminders(status, remind_at)"
    )

    cc = {r[1] for r in conn.execute("PRAGMA table_info(crm_cases)")}
    if "campaign_id" not in cc:
        try:
            conn.execute(
                "ALTER TABLE crm_cases ADD COLUMN campaign_id INTEGER "
                "REFERENCES crm_campaigns(id)"
            )
        except sqlite3.Error:
            pass


def ensure_crm_sop_schema(conn: sqlite3.Connection) -> None:
    """Quy trình Marketing (SOP): templates, steps, runs, run_tasks."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sop_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'other',
            description TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sop_tpl_active ON crm_sop_templates(active, channel)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sop_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL REFERENCES crm_sop_templates(id) ON DELETE CASCADE,
            position INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            offset_days INTEGER NOT NULL DEFAULT 0,
            duration_days INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'any',
            required INTEGER NOT NULL DEFAULT 1,
            checklist_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sop_steps_tpl ON crm_sop_steps(template_id, position)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sop_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER REFERENCES crm_campaigns(id) ON DELETE SET NULL,
            template_id INTEGER REFERENCES crm_sop_templates(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            start_date TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sop_runs_status ON crm_sop_runs(status, start_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sop_runs_campaign ON crm_sop_runs(campaign_id)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sop_run_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES crm_sop_runs(id) ON DELETE CASCADE,
            step_id INTEGER REFERENCES crm_sop_steps(id) ON DELETE SET NULL,
            position INTEGER NOT NULL DEFAULT 0,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'any',
            due_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'todo',
            assigned_staff_id INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            notes TEXT NOT NULL DEFAULT '',
            checklist_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sop_rtasks_run ON crm_sop_run_tasks(run_id, position)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sop_rtasks_due ON crm_sop_run_tasks(status, due_date)"
    )
    from crm_sop_seed import seed_launch_campaign_sop_template

    seed_launch_campaign_sop_template(conn)
