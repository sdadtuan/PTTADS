"""SEO/AEO cron orchestration — daily/weekly VPS timers (P3c)."""
from __future__ import annotations

import os
import secrets
from typing import Any


def seo_cron_secret_ok(auth_header: str | None) -> bool:
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return False
    got = auth_header[7:].strip()
    for key in (
        "PTT_SEO_CRON_SECRET",
        "CRM_FACEBOOK_SYNC_SECRET",
        "CRM_FINANCE_KPI_CRON_SECRET",
    ):
        exp = (os.getenv(key) or "").strip()
        if exp and secrets.compare_digest(got.encode(), exp.encode()):
            return True
    return False


def seo_cron_local_allowed(remote_addr: str | None, host: str | None) -> bool:
    if os.getenv("PTT_SEO_CRON_ALLOW_LOCAL", "1").strip().lower() in ("0", "false", "no"):
        return False
    remote = (remote_addr or "").strip().lower()
    if remote in ("127.0.0.1", "::1", "localhost") or remote.startswith("::ffff:127.0.0.1"):
        return True
    h = (host or "").split(":")[0].strip().lower()
    return h in ("127.0.0.1", "localhost")


def run_daily_cron(*, days: int = 28) -> dict[str, Any]:
    """GSC + GA4 sync all clients, due report schedules."""
    out: dict[str, Any] = {"ok": True, "jobs": {}}

    if os.getenv("PTT_GSC_SYNC_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.connectors.gsc_sync import sync_all_gsc_customers

        out["jobs"]["gsc"] = sync_all_gsc_customers(days=days)
    else:
        out["jobs"]["gsc"] = {"skipped": True}

    if os.getenv("PTT_GA4_SYNC_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.connectors.ga4_sync import sync_all_ga4_customers

        out["jobs"]["ga4"] = sync_all_ga4_customers(days=days)
    else:
        out["jobs"]["ga4"] = {"skipped": True}

    from ptt_seo.db import crm_connection, seo_write
    from ptt_seo.report_schedule import run_due_schedules

    with crm_connection() as crm, seo_write() as seo:
        out["jobs"]["report_schedules"] = run_due_schedules(seo, crm_conn=crm)

    for job in out["jobs"].values():
        if isinstance(job, dict) and job.get("ok") is False and not job.get("skipped"):
            out["ok"] = False
    return out


def run_weekly_cron() -> dict[str, Any]:
    """Freshness scan all SEO clients + SERP capture for tracked keywords."""
    out: dict[str, Any] = {"ok": True, "jobs": {}}

    if os.getenv("PTT_FRESHNESS_SCAN_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        out["jobs"]["freshness"] = {"ok": True, "skipped": True, "reason": "freshness_disabled"}
    else:
        from ptt_seo.freshness import scan_all_freshness_customers

        out["jobs"]["freshness"] = scan_all_freshness_customers()

    if os.getenv("PTT_SERP_SCHEDULE_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.db import seo_write
        from ptt_seo.serp_schedule import capture_serp_all_customers

        limit = int(os.getenv("PTT_SERP_SCHEDULE_PER_CLIENT", "5") or "5")
        max_clients = os.getenv("PTT_SERP_SCHEDULE_MAX_CLIENTS")
        with seo_write() as conn:
            out["jobs"]["serp_capture"] = capture_serp_all_customers(
                conn,
                per_customer_limit=max(1, min(limit, 20)),
                max_customers=int(max_clients) if max_clients else None,
            )
    else:
        out["jobs"]["serp_capture"] = {"ok": True, "skipped": True}

    if os.getenv("PTT_CWV_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.cwv import capture_cwv_all_customers
        from ptt_seo.db import seo_write

        limit = int(os.getenv("PTT_CWV_PER_CLIENT", "3") or "3")
        max_clients = os.getenv("PTT_CWV_MAX_CLIENTS")
        with seo_write() as conn:
            out["jobs"]["cwv_capture"] = capture_cwv_all_customers(
                conn,
                per_customer_limit=max(1, min(limit, 10)),
                max_customers=int(max_clients) if max_clients else None,
            )
    else:
        out["jobs"]["cwv_capture"] = {"ok": True, "skipped": True}

    if os.getenv("PTT_AEO_SCHEDULE_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.aeo_schedule import run_aeo_schedule_all
        from ptt_seo.db import seo_write

        max_clients = os.getenv("PTT_AEO_SCHEDULE_MAX_CLIENTS")
        with seo_write() as conn:
            out["jobs"]["aeo_schedule"] = run_aeo_schedule_all(
                conn,
                max_customers=int(max_clients) if max_clients else None,
            )
    else:
        out["jobs"]["aeo_schedule"] = {"ok": True, "skipped": True}

    crawl_days = int(os.getenv("PTT_CRAWL_REMINDER_DAYS", "30") or "30")
    if os.getenv("PTT_CRAWL_REMINDER_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.crawl_reminder import run_crawl_reminders
        from ptt_seo.db import seo_write

        with seo_write() as conn:
            out["jobs"]["crawl_reminder"] = run_crawl_reminders(conn, max_age_days=max(7, crawl_days))
    else:
        out["jobs"]["crawl_reminder"] = {"ok": True, "skipped": True}

    gate_e = run_gate_e_cron()
    out["jobs"]["gate_e"] = gate_e
    if not gate_e.get("ok", True):
        out["ok"] = False

    for job in out["jobs"].values():
        if isinstance(job, dict) and job.get("ok") is False and not job.get("skipped"):
            out["ok"] = False
    return out


def run_serp_cron() -> dict[str, Any]:
    """SERP-only scheduled capture (optional daily timer)."""
    if os.getenv("PTT_SERP_SCHEDULE_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        return {"ok": True, "skipped": True, "reason": "serp_schedule_disabled"}
    from ptt_seo.db import seo_write
    from ptt_seo.serp_schedule import capture_serp_all_customers

    limit = int(os.getenv("PTT_SERP_SCHEDULE_PER_CLIENT", "5") or "5")
    max_clients = os.getenv("PTT_SERP_SCHEDULE_MAX_CLIENTS")
    with seo_write() as conn:
        return capture_serp_all_customers(
            conn,
            per_customer_limit=max(1, min(limit, 20)),
            max_customers=int(max_clients) if max_clients else None,
        )


def run_gate_d_cron() -> dict[str, Any]:
    """Gate D bundle — CWV, AEO schedule, crawl reminders (without freshness/SERP)."""
    out: dict[str, Any] = {"ok": True, "jobs": {}}

    if os.getenv("PTT_CWV_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.cwv import capture_cwv_all_customers
        from ptt_seo.db import seo_write

        limit = int(os.getenv("PTT_CWV_PER_CLIENT", "3") or "3")
        max_clients = os.getenv("PTT_CWV_MAX_CLIENTS")
        with seo_write() as conn:
            out["jobs"]["cwv_capture"] = capture_cwv_all_customers(
                conn,
                per_customer_limit=max(1, min(limit, 10)),
                max_customers=int(max_clients) if max_clients else None,
            )
    else:
        out["jobs"]["cwv_capture"] = {"ok": True, "skipped": True, "reason": "cwv_disabled"}

    if os.getenv("PTT_AEO_SCHEDULE_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.aeo_schedule import run_aeo_schedule_all
        from ptt_seo.db import seo_write

        max_clients = os.getenv("PTT_AEO_SCHEDULE_MAX_CLIENTS")
        with seo_write() as conn:
            out["jobs"]["aeo_schedule"] = run_aeo_schedule_all(
                conn,
                max_customers=int(max_clients) if max_clients else None,
            )
    else:
        out["jobs"]["aeo_schedule"] = {"ok": True, "skipped": True, "reason": "aeo_schedule_disabled"}

    crawl_days = int(os.getenv("PTT_CRAWL_REMINDER_DAYS", "30") or "30")
    if os.getenv("PTT_CRAWL_REMINDER_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.crawl_reminder import run_crawl_reminders
        from ptt_seo.db import seo_write

        with seo_write() as conn:
            out["jobs"]["crawl_reminder"] = run_crawl_reminders(conn, max_age_days=max(7, crawl_days))
    else:
        out["jobs"]["crawl_reminder"] = {"ok": True, "skipped": True, "reason": "crawl_reminder_disabled"}

    for job in out["jobs"].values():
        if isinstance(job, dict) and job.get("ok") is False and not job.get("skipped"):
            out["ok"] = False
    return out


def run_gate_e_cron() -> dict[str, Any]:
    """Gate E bundle — crawl connector checks, live rank capture."""
    out: dict[str, Any] = {"ok": True, "jobs": {}}

    if os.getenv("PTT_CRAWL_CONNECTOR_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.crawl_connector import run_crawl_schedule_checks
        from ptt_seo.db import seo_write

        with seo_write() as conn:
            out["jobs"]["crawl_connector"] = run_crawl_schedule_checks(conn)
    else:
        out["jobs"]["crawl_connector"] = {"ok": True, "skipped": True}

    if os.getenv("PTT_RANK_LIVE_ENABLED", "1").strip().lower() not in ("0", "false", "no"):
        from ptt_seo.db import seo_write
        from ptt_seo.rank_live import capture_ranks_all_customers

        max_clients = os.getenv("PTT_RANK_LIVE_MAX_CLIENTS")
        with seo_write() as conn:
            out["jobs"]["rank_live"] = capture_ranks_all_customers(
                conn,
                max_customers=int(max_clients) if max_clients else None,
            )
    else:
        out["jobs"]["rank_live"] = {"ok": True, "skipped": True}

    for job in out["jobs"].values():
        if isinstance(job, dict) and job.get("ok") is False and not job.get("skipped"):
            out["ok"] = False
    return out
