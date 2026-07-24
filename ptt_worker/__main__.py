"""PTT background job worker — python -m ptt_worker"""
from __future__ import annotations

import logging
import signal
import sys
import time

from ptt_observability import bind_correlation_id, init_observability

init_observability(component="ptt_worker")
logger = logging.getLogger(__name__)

_running = True


def _handle_signal(signum: int, _frame: object) -> None:
    global _running
    logger.info("signal %s — shutting down", signum)
    _running = False


def run_worker(*, poll_interval: float = 1.0, once: bool = False) -> int:
    from ptt_jobs.db import pg_available
    from ptt_jobs.handlers.ingest_lead import run_ingest_lead_job
    from ptt_jobs.store import claim_next_job

    if not pg_available():
        logger.error("PostgreSQL unavailable — set DATABASE_URL and run docker compose up")
        return 1

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("ptt-worker started poll_interval=%s", poll_interval)

    idle_ticks = 0

    while _running:
        job = claim_next_job()
        if not job:
            idle_ticks += 1
            if idle_ticks % 5 == 0:
                try:
                    from ptt_jobs.event_publisher import run_event_publisher

                    run_event_publisher()
                except Exception as exc:
                    logger.debug("event publisher idle tick: %s", exc)
            if once:
                break
            time.sleep(poll_interval)
            continue

        idle_ticks = 0

        job_type = job.get("job_type")
        cid = str(job.get("correlation_id") or job.get("id") or "")
        bind_correlation_id(cid or None)
        logger.info(
            "processing job id=%s type=%s",
            job.get("id"),
            job_type,
            extra={"correlation_id": cid, "job_type": job_type, "job_id": str(job.get("id") or "")},
        )
        try:
            if job_type == "ingest_lead":
                run_ingest_lead_job(job)
                try:
                    from ptt_jobs.event_publisher import run_event_publisher

                    run_event_publisher()
                except Exception as exc:
                    logger.debug("event publisher after ingest: %s", exc)
            elif job_type == "form_ingest":
                from ptt_jobs.handlers.form_ingest import run_form_ingest_job

                run_form_ingest_job(job)
            elif job_type == "sync_lead_replica":
                from ptt_jobs.handlers.sync_lead_replica import run_sync_lead_replica_job

                run_sync_lead_replica_job(job)
            elif job_type == "sync_lead_shadow":
                from ptt_jobs.handlers.sync_lead_shadow import run_sync_lead_shadow_job

                run_sync_lead_shadow_job(job)
            elif job_type == "meta_insights_sync":
                from ptt_jobs.handlers.meta_insights_sync import run_meta_insights_sync_job

                run_meta_insights_sync_job(job)
            elif job_type == "meta_alerts_eval":
                from ptt_jobs.handlers.meta_alerts_eval import run_meta_alerts_eval_job

                run_meta_alerts_eval_job(job)
            elif job_type == "meta_conversion_sync":
                from ptt_jobs.handlers.meta_conversion_sync import run_meta_conversion_sync_job

                run_meta_conversion_sync_job(job)
            elif job_type == "meta_conversion_eval":
                from ptt_jobs.handlers.meta_conversion_eval import run_meta_conversion_eval_job

                run_meta_conversion_eval_job(job)
            elif job_type == "meta_insights_archive":
                from ptt_jobs.handlers.meta_insights_archive import run_meta_insights_archive_job

                run_meta_insights_archive_job(job)
            elif job_type == "google_insights_sync":
                from ptt_jobs.handlers.google_insights_sync import run_google_insights_sync_job

                run_google_insights_sync_job(job)
            elif job_type == "meta_token_refresh":
                from ptt_jobs.handlers.meta_token_refresh import run_meta_token_refresh_job

                run_meta_token_refresh_job(job)
            elif job_type == "capi_dispatch":
                from ptt_jobs.handlers.capi_dispatch import run_capi_dispatch_job

                run_capi_dispatch_job(job)
            elif job_type == "seo_gsc_sync":
                from ptt_jobs.handlers.seo_gsc_sync import run_seo_gsc_sync_job

                run_seo_gsc_sync_job(job)
            elif job_type == "seo_ga4_sync":
                from ptt_jobs.handlers.seo_ga4_sync import run_seo_ga4_sync_job

                run_seo_ga4_sync_job(job)
            elif job_type == "seo_aeo_scan":
                from ptt_jobs.handlers.seo_aeo_scan import run_seo_aeo_scan_job

                run_seo_aeo_scan_job(job)
            elif job_type == "seo_freshness_scan":
                from ptt_jobs.handlers.seo_freshness_scan import run_seo_freshness_scan_job

                run_seo_freshness_scan_job(job)
            elif job_type == "seo_report_schedules":
                from ptt_jobs.handlers.seo_report_schedule import run_seo_report_schedules_job

                run_seo_report_schedules_job(job)
            elif job_type == "email_campaign_prepare":
                from ptt_jobs.handlers.email_campaign_prepare import run_email_campaign_prepare_job

                run_email_campaign_prepare_job(job)
            elif job_type == "email_campaign_schedule_due":
                from ptt_jobs.handlers.email_campaign_schedule_due import run_email_campaign_schedule_due_job

                run_email_campaign_schedule_due_job(job)
            elif job_type == "email_journey_enroll_scan":
                from ptt_jobs.handlers.email_journey_enroll_scan import run_email_journey_enroll_scan_job

                run_email_journey_enroll_scan_job(job)
            elif job_type == "email_journey_tick":
                from ptt_jobs.handlers.email_journey_tick import run_email_journey_tick_job

                run_email_journey_tick_job(job)
            elif job_type == "email_journey_trigger_events":
                from ptt_jobs.handlers.email_journey_trigger_events import run_email_journey_trigger_events_job

                run_email_journey_trigger_events_job(job)
            elif job_type == "email_experiment_rollup":
                from ptt_jobs.handlers.email_experiment_rollup import run_email_experiment_rollup_job

                run_email_experiment_rollup_job(job)
            elif job_type == "email_send_batch":
                from ptt_jobs.handlers.email_send_batch import run_email_send_batch_job

                run_email_send_batch_job(job)
            elif job_type == "email_engagement_ingest":
                from ptt_jobs.handlers.email_engagement_ingest import run_email_engagement_ingest_job

                run_email_engagement_ingest_job(job)
            elif job_type == "email_clickhouse_export":
                from ptt_jobs.handlers.email_clickhouse_export import run_email_clickhouse_export_job

                run_email_clickhouse_export_job(job)
            elif job_type == "email_attribution_rollup":
                from ptt_jobs.handlers.email_attribution_rollup import run_email_attribution_rollup_job

                run_email_attribution_rollup_job(job)
            elif job_type in ("email_deliverability_scan", "email_bounce_process", "email_complaint_process"):
                from ptt_jobs.handlers.email_deliverability_scan import run_email_deliverability_scan_job

                run_email_deliverability_scan_job(job)
            elif job_type == "email_dns_verify":
                from ptt_jobs.handlers.email_dns_verify import run_email_dns_verify_job

                run_email_dns_verify_job(job)
            elif job_type == "email_warm_up_tick":
                from ptt_jobs.handlers.email_warm_up_tick import run_email_warm_up_tick_job

                run_email_warm_up_tick_job(job)
            elif job_type == "email_report_schedules":
                from ptt_jobs.handlers.email_report_schedules import run_email_report_schedules_job

                run_email_report_schedules_job(job)
            else:
                from ptt_jobs.store import mark_job_failed

                mark_job_failed(
                    str(job["id"]),
                    f"Unknown job_type: {job_type}",
                    attempts=int(job.get("attempts") or 1),
                    max_attempts=int(job.get("max_attempts") or 5),
                )
        except Exception as exc:
            logger.exception("job handler error: %s", exc)
            from ptt_jobs.store import mark_job_failed

            mark_job_failed(
                str(job["id"]),
                str(exc),
                attempts=int(job.get("attempts") or 1),
                max_attempts=int(job.get("max_attempts") or 5),
            )

        if once:
            break

    logger.info("ptt-worker stopped")
    return 0


def main() -> None:
    once = "--once" in sys.argv
    interval = 1.0
    for arg in sys.argv:
        if arg.startswith("--interval="):
            interval = float(arg.split("=", 1)[1])
    raise SystemExit(run_worker(poll_interval=interval, once=once))


if __name__ == "__main__":
    main()
