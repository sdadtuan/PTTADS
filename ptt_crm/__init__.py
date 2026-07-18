"""CRM read layer — normalized DTOs for /api/v1/leads (NestJS dual-run compatible)."""
from ptt_crm.contracts import LEAD_V1_FIELDS, LIST_RESPONSE_FIELDS
from ptt_crm.dual_run import (
    compare_lead_get,
    compare_leads_list,
    diff_lead_v1,
    diff_list_response,
    maybe_dual_run_get,
    maybe_dual_run_list,
    run_batch_dual_run_check,
)
from ptt_crm.leads_read import get_lead_v1, lead_row_to_v1, list_leads_v1

__all__ = [
    "LEAD_V1_FIELDS",
    "LIST_RESPONSE_FIELDS",
    "compare_lead_get",
    "compare_leads_list",
    "diff_lead_v1",
    "diff_list_response",
    "get_lead_v1",
    "lead_row_to_v1",
    "list_leads_v1",
    "maybe_dual_run_get",
    "maybe_dual_run_list",
    "run_batch_dual_run_check",
]
