"""Client workspace tasks — CRM service tasks + SEO technical issues (Gate B S-03)."""
from __future__ import annotations

from typing import Any

from ptt_seo.constants import SEO_AEO_SERVICE_SLUGS


def list_client_tasks(crm_conn: Any, seo_conn: Any, customer_id: int) -> dict[str, Any]:
    """Aggregate open CRM svc tasks and SEO technical issues linked to tasks."""
    from crm_svc_tasks import list_tasks
    from ptt_seo.technical import list_issues

    lifecycles = [
        dict(r)
        for r in crm_conn.execute(
            f"""
            SELECT id, service_slug, stage, status
            FROM crm_service_lifecycle
            WHERE customer_id = ? AND service_slug IN ({",".join("?" * len(SEO_AEO_SERVICE_SLUGS))})
            ORDER BY id DESC
            """,
            (customer_id, *SEO_AEO_SERVICE_SLUGS),
        ).fetchall()
    ]

    service_tasks: list[dict[str, Any]] = []
    for lc in lifecycles:
        lid = int(lc["id"])
        by_stage = list_tasks(crm_conn, lid)
        for stage, rows in by_stage.items():
            for t in rows:
                if int(t.get("is_done") or 0) == 1:
                    continue
                service_tasks.append(
                    {
                        "kind": "service",
                        "task_id": int(t["id"]),
                        "lifecycle_id": lid,
                        "service_slug": lc.get("service_slug") or "",
                        "stage": stage,
                        "title": t.get("title") or t.get("step_name") or f"Task #{t['id']}",
                        "due_on": t.get("due_on") or "",
                        "url": f"/crm/service-delivery/{lid}#task-card-{t['id']}",
                    }
                )

    technical: list[dict[str, Any]] = []
    for issue in list_issues(seo_conn, customer_id):
        task_id = issue.get("crm_task_id")
        lifecycle_id = issue.get("lifecycle_id")
        url = "/crm/seo/technical"
        if task_id and lifecycle_id:
            url = f"/crm/service-delivery/{lifecycle_id}#task-card-{task_id}"
        elif issue.get("id"):
            url = f"/crm/seo/technical?customer_id={customer_id}"
        technical.append(
            {
                "kind": "technical",
                "issue_id": int(issue["id"]),
                "crm_task_id": int(task_id) if task_id else None,
                "lifecycle_id": int(lifecycle_id) if lifecycle_id else None,
                "title": f"{issue.get('issue_type') or 'issue'} — {issue.get('url') or ''}"[:120],
                "severity": issue.get("severity") or "",
                "status": issue.get("status") or "",
                "url": url,
            }
        )

    return {
        "service_tasks": service_tasks,
        "technical_issues": technical,
        "open_count": len(service_tasks) + len(technical),
    }
