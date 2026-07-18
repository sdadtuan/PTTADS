# crm_svc_tasks.py
"""Workflow tasks per-customer cho 12 dịch vụ PTTP."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

SERVICE_LABELS: dict[str, str] = {
    "dich-vu-aeo": "Dịch vụ AEO",
    "dich-vu-seo-tong-the": "SEO Tổng thể",
    "dich-vu-seo-local": "SEO Local",
    "dich-vu-seo-audit": "SEO Audit",
    "dich-vu-quan-tri-website": "Quản trị Website",
    "thiet-ke-website": "Thiết kế Website",
    "thiet-ke-website-tron-goi": "Website Trọn gói",
    "thiet-ke-landing-page": "Landing Page",
    "quang-cao-facebook": "Quảng cáo Facebook",
    "quang-cao-google": "Quảng cáo Google",
    "thue-tai-khoan-quang-cao": "Thuê Tài khoản Ads",
    "tiep-thi-noi-dung": "Tiếp thị Nội dung",
    "_common": "Form chung (chưa xác định DV)",
}

# Dịch vụ retainer — Triển khai có task theo tháng
RECURRING_DELIVER_SLUGS: frozenset[str] = frozenset({
    "dich-vu-aeo",
    "dich-vu-seo-tong-the",
    "dich-vu-seo-local",
    "dich-vu-quan-tri-website",
    "quang-cao-facebook",
    "quang-cao-google",
    "tiep-thi-noi-dung",
})
RECURRING_DELIVER_MONTHS = 12

logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_tasks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id  INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            stage         TEXT NOT NULL DEFAULT '',
            step_index    INTEGER NOT NULL DEFAULT 0,
            title         TEXT NOT NULL DEFAULT '',
            description   TEXT NOT NULL DEFAULT '',
            form_fields   TEXT NOT NULL DEFAULT '[]',
            form_data     TEXT NOT NULL DEFAULT '{}',
            ai_output     TEXT NOT NULL DEFAULT '',
            ai_prompt_key TEXT NOT NULL DEFAULT '',
            is_done       INTEGER NOT NULL DEFAULT 0,
            done_at       TEXT NOT NULL DEFAULT '',
            done_by       INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            notes         TEXT NOT NULL DEFAULT '',
            is_custom     INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT '',
            updated_at    TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_tasks_lifecycle "
        "ON crm_svc_tasks(lifecycle_id, stage)"
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_svc_tasks)").fetchall()}
    if "due_on" not in cols:
        conn.execute(
            "ALTER TABLE crm_svc_tasks ADD COLUMN due_on TEXT NOT NULL DEFAULT ''"
        )
    conn.commit()


def is_stage_complete(
    conn: sqlite3.Connection, lifecycle_id: int, stage: str
) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total, COALESCE(SUM(is_done), 0) AS done
        FROM crm_svc_tasks
        WHERE lifecycle_id = ? AND stage = ?
        """,
        (lifecycle_id, stage),
    ).fetchone()
    total = int(row["total"] or 0)
    if total == 0:
        return True
    return int(row["done"] or 0) >= total


def complete_all_stage_tasks(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    stage: str,
    *,
    done_by: int | None = None,
) -> int:
    ts = _ts()
    cur = conn.execute(
        """
        UPDATE crm_svc_tasks
        SET is_done = 1, done_at = ?, updated_at = ?,
            done_by = COALESCE(?, done_by)
        WHERE lifecycle_id = ? AND stage = ? AND is_done = 0
        """,
        (ts, ts, done_by, lifecycle_id, stage),
    )
    conn.commit()
    return int(cur.rowcount or 0)


def _insert_task(
    conn: sqlite3.Connection,
    *,
    lifecycle_id: int,
    stage: str,
    step_index: int,
    step: dict[str, Any],
    ts: str,
    is_custom: int = 0,
) -> None:
    conn.execute(
        """
        INSERT INTO crm_svc_tasks
            (lifecycle_id, stage, step_index, title, description,
             ai_prompt_key, form_fields, form_data, is_done, is_custom,
             created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 0, ?, ?, ?)
        """,
        (
            lifecycle_id,
            stage,
            step_index,
            step["title"],
            step.get("description", ""),
            step.get("ai_prompt_key", ""),
            json.dumps(step.get("form_fields", []), ensure_ascii=False),
            is_custom,
            ts,
            ts,
        ),
    )


def _seed_deliver_steps(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    service_slug: str,
    deliver_steps: list[dict[str, Any]],
    ts: str,
) -> int:
    if not deliver_steps:
        return 0
    count = 0
    if service_slug in RECURRING_DELIVER_SLUGS:
        base = deliver_steps[0]
        for month in range(1, RECURRING_DELIVER_MONTHS + 1):
            step = dict(base)
            base_title = str(base.get("title") or "Triển khai").strip()
            step["title"] = f"{base_title} — Tháng {month}"
            fields = []
            for field in base.get("form_fields") or []:
                f = dict(field)
                if f.get("key") == "report_period":
                    f["label"] = f"Kỳ báo cáo (tháng {month})"
                fields.append(f)
            step["form_fields"] = fields
            _insert_task(
                conn,
                lifecycle_id=lifecycle_id,
                stage="deliver",
                step_index=month - 1,
                step=step,
                ts=ts,
            )
            count += 1
    else:
        for idx, step in enumerate(deliver_steps):
            _insert_task(
                conn,
                lifecycle_id=lifecycle_id,
                stage="deliver",
                step_index=idx,
                step=step,
                ts=ts,
            )
            count += 1
    return count


def ensure_recurring_deliver_tasks(
    conn: sqlite3.Connection, lifecycle_id: int, service_slug: str
) -> int:
    """Lifecycle cũ chỉ có 1 task deliver — mở rộng thành 12 tháng nếu là dịch vụ retainer."""
    if service_slug not in RECURRING_DELIVER_SLUGS:
        return 0
    total = conn.execute(
        """
        SELECT COUNT(*) FROM crm_svc_tasks
        WHERE lifecycle_id = ? AND stage = 'deliver' AND is_custom = 0
        """,
        (lifecycle_id,),
    ).fetchone()[0]
    if int(total or 0) >= RECURRING_DELIVER_MONTHS:
        return 0
    from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS

    deliver_steps = SERVICE_WORKFLOW_STEPS.get(service_slug, {}).get("deliver") or []
    if not deliver_steps:
        return 0
    conn.execute(
        """
        DELETE FROM crm_svc_tasks
        WHERE lifecycle_id = ? AND stage = 'deliver' AND is_custom = 0
        """,
        (lifecycle_id,),
    )
    ts = _ts()
    added = _seed_deliver_steps(conn, lifecycle_id, service_slug, deliver_steps, ts)
    conn.commit()
    return added


def seed_tasks(
    conn: sqlite3.Connection, lifecycle_id: int, service_slug: str
) -> int:
    from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS
    existing = conn.execute(
        "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = ? AND is_custom = 0",
        (lifecycle_id,),
    ).fetchone()[0]
    if existing > 0:
        return 0
    steps = SERVICE_WORKFLOW_STEPS.get(service_slug, {})
    ts = _ts()
    count = 0
    for stage, stage_steps in steps.items():
        if stage == "deliver":
            count += _seed_deliver_steps(
                conn, lifecycle_id, service_slug, stage_steps, ts
            )
            continue
        for idx, step in enumerate(stage_steps):
            _insert_task(
                conn,
                lifecycle_id=lifecycle_id,
                stage=stage,
                step_index=idx,
                step=step,
                ts=ts,
            )
            count += 1
    conn.commit()
    return count


def list_tasks(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT * FROM crm_svc_tasks
        WHERE lifecycle_id = ?
        ORDER BY stage, step_index, id
        """,
        (lifecycle_id,),
    ).fetchall()
    result: dict[str, list[dict]] = {}
    for row in rows:
        d = dict(row)
        d["form_data"] = json.loads(d.get("form_data") or "{}")
        d["form_fields"] = json.loads(d.get("form_fields") or "[]")
        stage = d["stage"]
        result.setdefault(stage, []).append(d)
    return result


def update_task(
    conn: sqlite3.Connection,
    task_id: int,
    *,
    is_done: bool | None = None,
    notes: str | None = None,
    form_data: dict | None = None,
    done_by: int | None = None,
) -> None:
    ts = _ts()
    sets = ["updated_at = ?"]
    params: list[Any] = [ts]
    if is_done is not None:
        sets.append("is_done = ?")
        params.append(1 if is_done else 0)
        if is_done:
            sets.append("done_at = ?")
            params.append(ts)
        else:
            sets.append("done_at = ''")
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes[:4000])
    if form_data is not None:
        sets.append("form_data = ?")
        params.append(json.dumps(form_data, ensure_ascii=False))
    if done_by is not None:
        sets.append("done_by = ?")
        params.append(done_by)
    params.append(task_id)
    conn.execute(
        f"UPDATE crm_svc_tasks SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()


def create_custom_task(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    stage: str,
    title: str,
    description: str = "",
) -> int:
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_svc_tasks
            (lifecycle_id, stage, step_index, title, description, form_fields,
             form_data, is_done, is_custom, created_at, updated_at)
        VALUES (?, ?, 999, ?, ?, '[]', '{}', 0, 1, ?, ?)
        """,
        (lifecycle_id, stage, title[:500], description[:2000], ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def delete_task(conn: sqlite3.Connection, task_id: int) -> bool:
    row = conn.execute(
        "SELECT is_custom FROM crm_svc_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if row is None or not row["is_custom"]:
        return False
    conn.execute("DELETE FROM crm_svc_tasks WHERE id = ?", (task_id,))
    conn.commit()
    return True


_AI_CTX_KEYS: tuple[str, ...] = (
    "service_name", "customer_name", "niche", "budget", "need", "goal",
    "current_status", "timeline", "start_date", "report_period",
    "completed_tasks", "metrics", "kpi_target", "kpi_actual",
    "months_active", "kpi_summary",
    "bant_total", "decision", "intake_summary", "lead_form_json",
    "red_flags", "consult_brief_json",
)


def _prompt_context(customer_context: dict) -> dict[str, str]:
    ctx: dict[str, str] = {}
    for key in _AI_CTX_KEYS:
        val = customer_context.get(key, "")
        if key in ("bant_total",) and val not in (None, ""):
            ctx[key] = str(val)
        else:
            text = str(val or "").replace("{", "{{").replace("}", "}}")
            ctx[key] = text
    for key, val in customer_context.items():
        if key not in ctx:
            ctx[key] = str(val or "").replace("{", "{{").replace("}", "}}")
    return ctx


def run_ai_assist(
    conn: sqlite3.Connection,
    task_id: int,
    customer_context: dict,
) -> str:
    from crm_svc_workflow_steps import AI_PROMPT_TEMPLATES
    task = conn.execute(
        "SELECT * FROM crm_svc_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if task is None:
        return ""
    template = AI_PROMPT_TEMPLATES.get(task["ai_prompt_key"], "")
    if not template:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    try:
        import anthropic
        ctx = _prompt_context(customer_context)
        prompt = template.format(**ctx)
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        output = response.content[0].text.strip()
        conn.execute(
            "UPDATE crm_svc_tasks SET ai_output = ?, updated_at = ? WHERE id = ?",
            (output, _ts(), task_id),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_assist lỗi task_id=%s: %s", task_id, exc)
        return ""


def get_progress(
    conn: sqlite3.Connection, lifecycle_id: int
) -> dict[str, dict[str, Any]]:
    from crm_service_lifecycle import VALID_STAGES
    rows = conn.execute(
        """
        SELECT stage, COUNT(*) as total, SUM(is_done) as done
        FROM crm_svc_tasks
        WHERE lifecycle_id = ?
        GROUP BY stage
        """,
        (lifecycle_id,),
    ).fetchall()
    result: dict[str, dict] = {
        s: {"total": 0, "done": 0, "pct": 0} for s in VALID_STAGES
    }
    for row in rows:
        total = row["total"]
        done = row["done"] or 0
        pct = int(done / total * 100) if total > 0 else 0
        result[row["stage"]] = {"total": total, "done": done, "pct": pct}
    return result
