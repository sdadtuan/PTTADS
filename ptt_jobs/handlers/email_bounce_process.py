"""Job handler — email_bounce_process / complaint alias (Wave 2)."""
from __future__ import annotations

from ptt_jobs.handlers.email_deliverability_scan import run_email_deliverability_scan_job

run_email_bounce_process_job = run_email_deliverability_scan_job
run_email_complaint_process_job = run_email_deliverability_scan_job
