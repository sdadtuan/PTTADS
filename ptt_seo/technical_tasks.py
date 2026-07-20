"""Bridge SEO technical issues → CRM service delivery tasks (P2 F3)."""
from __future__ import annotations

import os
import sqlite3
from typing import Any

from ptt_seo.constants import SEO_AEO_SERVICE_SLUGS


def tech_auto_task_enabled() -> bool:
    return os.environ.get("PTT_SEO_TECH_AUTO_TASK", "1").strip().lower() not in {"0", "false", "no"}


def _auto_severities() -> frozenset[str]:
    raw = os.environ.get("PTT_SEO_TECH_AUTO_TASK_SEVERITIES", "critical,high")
    return frozenset(s.strip().lower() for s in raw.split(",") if s.strip())


def pick_seo_lifecycle(crm_conn: Any, customer_id: int) -> dict[str, Any] | None:
    placeholders = ",".join("?" for _ in SEO_AEO_SERVICE_SLUGS)
    row = crm_conn.execute(
        f"""
        SELECT id, service_slug, stage, status
        FROM crm_service_lifecycle
        WHERE customer_id = ?
          AND service_slug IN ({placeholders})
          AND COALESCE(status, 'active') != 'cancelled'
        ORDER BY id DESC
        LIMIT 1
        """,
        (customer_id, *SEO_AEO_SERVICE_SLUGS),
    ).fetchone()
    return dict(row) if row else None


def task_workflow_url(lifecycle_id: int, task_id: int) -> str:
    return f"/crm/service-delivery/{lifecycle_id}#task-card-{task_id}"


def _lifecycle_for_task(crm_conn: Any, task_id: int) -> int | None:
    trow = crm_conn.execute(
        "SELECT lifecycle_id FROM crm_svc_tasks WHERE id = ?",
        (int(task_id),),
    ).fetchone()
    return int(trow["lifecycle_id"]) if trow else None


def create_task_for_issue(
    crm_conn: Any,
    seo_conn: Any,
    issue_id: int,
    *,
    assignee_id: int | None = None,
    auto: bool = False,
) -> dict[str, Any]:
    row = seo_conn.execute(
        "SELECT * FROM seo_technical_issues WHERE id = ?", (issue_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Issue không tồn tại")
    issue = dict(row)
    existing_task = issue.get("crm_task_id")
    if existing_task:
        lc_id = issue.get("lifecycle_id")
        if not lc_id:
            lc_id = _lifecycle_for_task(crm_conn, int(existing_task))
            if lc_id:
                seo_conn.execute(
                    "UPDATE seo_technical_issues SET lifecycle_id = ? WHERE id = ?",
                    (int(lc_id), issue_id),
                )
                seo_conn.commit()
        return {
            "ok": True,
            "task_id": int(existing_task),
            "issue_id": issue_id,
            "lifecycle_id": int(lc_id) if lc_id else None,
            "task_url": task_workflow_url(int(lc_id), int(existing_task)) if lc_id else None,
            "existing": True,
        }

    lifecycle = pick_seo_lifecycle(crm_conn, int(issue["customer_id"]))
    if lifecycle is None:
        raise ValueError("Client chưa có lifecycle SEO/AEO — không thể tạo task")

    from crm_svc_tasks import create_custom_task, ensure_schema

    ensure_schema(crm_conn)
    url = str(issue.get("url") or "")
    issue_type = str(issue.get("issue_type") or "issue")
    severity = str(issue.get("severity") or "medium")
    title = f"[SEO Tech] {issue_type} ({severity})"
    if len(title) > 120:
        title = title[:117] + "..."
    description = "\n".join(
        [
            f"URL: {url}",
            f"Severity: {severity}",
            f"Type: {issue_type}",
            str(issue.get("description") or "").strip(),
            str(issue.get("impact_notes") or "").strip(),
            f"Issue ID: {issue_id}",
        ]
    ).strip()

    task_id = create_custom_task(
        crm_conn,
        int(lifecycle["id"]),
        "deliver",
        title,
        description[:2000],
    )

    new_status = issue.get("status") or "detected"
    if new_status in ("detected", "triaged"):
        new_status = "assigned"
    resolved_assignee = assignee_id if assignee_id is not None else issue.get("assignee_id")
    seo_conn.execute(
        """
        UPDATE seo_technical_issues
        SET crm_task_id = ?, lifecycle_id = ?, status = ?,
            assignee_id = COALESCE(?, assignee_id)
        WHERE id = ?
        """,
        (task_id, int(lifecycle["id"]), new_status, resolved_assignee, issue_id),
    )
    seo_conn.commit()

    return {
        "ok": True,
        "task_id": task_id,
        "issue_id": issue_id,
        "lifecycle_id": int(lifecycle["id"]),
        "task_url": task_workflow_url(int(lifecycle["id"]), task_id),
        "auto": auto,
        "existing": False,
    }


def enrich_issues(crm_conn: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach lifecycle_id, task_url, assignee_name for UI."""
    if not rows:
        return rows
    staff_ids = {int(r["assignee_id"]) for r in rows if r.get("assignee_id")}
    staff_map: dict[int, str] = {}
    if staff_ids:
        placeholders = ",".join("?" for _ in staff_ids)
        for srow in crm_conn.execute(
            f"SELECT id, name FROM crm_staff WHERE id IN ({placeholders})",
            tuple(staff_ids),
        ).fetchall():
            staff_map[int(srow["id"])] = str(srow["name"] or "")
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        lc_id = item.get("lifecycle_id")
        task_id = item.get("crm_task_id")
        if task_id and lc_id:
            item["task_url"] = task_workflow_url(int(lc_id), int(task_id))
        elif task_id and not lc_id:
            lc_id = _lifecycle_for_task(crm_conn, int(task_id))
            if lc_id:
                item["lifecycle_id"] = lc_id
                item["task_url"] = task_workflow_url(lc_id, int(task_id))
        if item.get("assignee_id"):
            item["assignee_name"] = staff_map.get(int(item["assignee_id"]), "")
        out.append(item)
    return out


def list_assignee_staff(crm_conn: Any) -> list[dict[str, Any]]:
    rows = crm_conn.execute(
        """
        SELECT id, name, job_title, department
        FROM crm_staff
        WHERE active = 1
        ORDER BY name
        """
    ).fetchall()
    return [dict(r) for r in rows]


def maybe_auto_create_task(
    crm_conn: Any,
    seo_conn: Any,
    issue_id: int,
    *,
    severity: str,
) -> dict[str, Any] | None:
    if not tech_auto_task_enabled():
        return None
    if severity.lower() not in _auto_severities():
        return None
    try:
        return create_task_for_issue(crm_conn, seo_conn, issue_id, auto=True)
    except ValueError:
        return None
