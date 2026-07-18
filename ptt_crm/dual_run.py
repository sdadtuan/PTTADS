"""Dual-run compare Flask CRM read vs NestJS (Phase 1b Bước 4)."""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any

from ptt_crm.config import (
    dual_run_async,
    dual_run_enabled,
    dual_run_timeout_sec,
    nest_internal_key,
    nest_leads_base_url,
)
from ptt_crm.contracts import LEAD_V1_FIELDS, LIST_RESPONSE_FIELDS

logger = logging.getLogger(__name__)


@dataclass
class FieldDiff:
    field: str
    flask: Any
    nest: Any


@dataclass
class DualRunResult:
    endpoint: str
    matched: bool
    flask_status: int | None = None
    nest_status: int | None = None
    diffs: list[FieldDiff] = field(default_factory=list)
    error: str | None = None
    query: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["diffs"] = [asdict(d) for d in self.diffs]
        return out


_TS_COMPARE_FIELDS = frozenset(
    {"created_at", "received_at", "updated_at", "status_entered_at", "synced_at"}
)


def _normalize_dual_run_value(field: str, value: Any) -> Any:
    """Normalize timestamp strings so ISO Z and SQLite space formats compare equal."""
    if field not in _TS_COMPARE_FIELDS or value is None:
        return value
    text = str(value).strip()
    if not text:
        return value
    text = text.replace("T", " ").replace("Z", "").replace("+00:00", "")[:19]
    return text


def diff_lead_v1(flask_lead: dict[str, Any], nest_lead: dict[str, Any]) -> list[FieldDiff]:
    diffs: list[FieldDiff] = []
    for key in LEAD_V1_FIELDS:
        fv = _normalize_dual_run_value(key, flask_lead.get(key))
        nv = _normalize_dual_run_value(key, nest_lead.get(key))
        if fv != nv:
            diffs.append(FieldDiff(field=key, flask=flask_lead.get(key), nest=nest_lead.get(key)))
    extra_flask = set(flask_lead) - set(LEAD_V1_FIELDS)
    extra_nest = set(nest_lead) - set(LEAD_V1_FIELDS)
    for key in sorted(extra_flask | extra_nest):
        fv = _normalize_dual_run_value(key, flask_lead.get(key))
        nv = _normalize_dual_run_value(key, nest_lead.get(key))
        if fv != nv:
            diffs.append(FieldDiff(field=key, flask=flask_lead.get(key), nest=nest_lead.get(key)))
    return diffs


def diff_list_response(flask_body: dict[str, Any], nest_body: dict[str, Any]) -> list[FieldDiff]:
    diffs: list[FieldDiff] = []
    for key in LIST_RESPONSE_FIELDS:
        if key == "leads":
            continue
        fv = flask_body.get(key)
        nv = nest_body.get(key)
        if fv != nv:
            diffs.append(FieldDiff(field=key, flask=fv, nest=nv))

    flask_leads = flask_body.get("leads") or []
    nest_leads = nest_body.get("leads") or []
    if len(flask_leads) != len(nest_leads):
        diffs.append(FieldDiff(field="leads.length", flask=len(flask_leads), nest=len(nest_leads)))
        return diffs

    for idx, (fl, nl) in enumerate(zip(flask_leads, nest_leads)):
        for fd in diff_lead_v1(fl, nl):
            diffs.append(FieldDiff(field=f"leads[{idx}].{fd.field}", flask=fd.flask, nest=fd.nest))
    return diffs


def request_nest_json(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    query: str = "",
    actor: str | None = None,
) -> tuple[int, dict[str, Any] | None, str | None]:
    base = nest_leads_base_url()
    url = f"{base}{path}"
    if query:
        url = f"{url}?{query}" if "?" not in path else f"{url}&{query}"

    headers = {"Accept": "application/json"}
    key = nest_internal_key()
    if key:
        headers["X-PTT-Internal-Key"] = key
    if actor:
        headers["X-PTT-Actor"] = actor[:120]

    data: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, headers=headers, method=method.upper(), data=data)
    try:
        with urllib.request.urlopen(req, timeout=dual_run_timeout_sec()) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return int(resp.status), parsed if isinstance(parsed, dict) else None, None
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"error": str(exc)}
        return int(exc.code), parsed if isinstance(parsed, dict) else None, None
    except Exception as exc:
        return 0, None, str(exc)


def fetch_nest_json(path: str, *, query: str = "") -> tuple[int, dict[str, Any] | None, str | None]:
    return request_nest_json(path, method="GET", query=query)


def compare_lead_get(lead_id: int, flask_lead: dict[str, Any] | None) -> DualRunResult:
    nest_status, nest_body, err = fetch_nest_json(f"/api/v1/leads/{lead_id}")
    if err:
        return DualRunResult(
            endpoint=f"GET /api/v1/leads/{lead_id}",
            matched=False,
            error=err,
        )

    if flask_lead is None:
        flask_status = 404
        flask_body: dict[str, Any] = {"error": "Not found"}
    else:
        flask_status = 200
        flask_body = flask_lead

    if nest_body is None:
        nest_body = {}

    if flask_status != nest_status:
        return DualRunResult(
            endpoint=f"GET /api/v1/leads/{lead_id}",
            matched=False,
            flask_status=flask_status,
            nest_status=nest_status,
            diffs=[FieldDiff(field="http_status", flask=flask_status, nest=nest_status)],
        )

    if flask_status == 404:
        matched = flask_body == nest_body
        diffs = [] if matched else [FieldDiff(field="body", flask=flask_body, nest=nest_body)]
        return DualRunResult(
            endpoint=f"GET /api/v1/leads/{lead_id}",
            matched=matched,
            flask_status=flask_status,
            nest_status=nest_status,
            diffs=diffs,
        )

    diffs = diff_lead_v1(flask_body, nest_body)
    return DualRunResult(
        endpoint=f"GET /api/v1/leads/{lead_id}",
        matched=len(diffs) == 0,
        flask_status=flask_status,
        nest_status=nest_status,
        diffs=diffs,
    )


def compare_leads_list(flask_body: dict[str, Any], *, query: str = "") -> DualRunResult:
    q = query.lstrip("?")
    nest_status, nest_body, err = fetch_nest_json("/api/v1/leads", query=q)
    if err:
        return DualRunResult(endpoint="GET /api/v1/leads", matched=False, error=err, query=q)

    if nest_body is None:
        nest_body = {}

    if nest_status != 200:
        return DualRunResult(
            endpoint="GET /api/v1/leads",
            matched=False,
            flask_status=200,
            nest_status=nest_status,
            query=q,
            diffs=[FieldDiff(field="http_status", flask=200, nest=nest_status)],
        )

    diffs = diff_list_response(flask_body, nest_body)
    return DualRunResult(
        endpoint="GET /api/v1/leads",
        matched=len(diffs) == 0,
        flask_status=200,
        nest_status=nest_status,
        diffs=diffs,
        query=q,
    )


def report_dual_run_mismatch(result: DualRunResult) -> None:
    payload = result.to_dict()
    logger.warning(
        "dual_run mismatch endpoint=%s diffs=%d",
        result.endpoint,
        len(result.diffs),
        extra={"dual_run": payload, "dual_run_mismatch": True},
    )
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("dual_run_mismatch", "true")
            scope.set_tag("dual_run_endpoint", result.endpoint)
            scope.set_context("dual_run", payload)
            sentry_sdk.capture_message(
                f"dual_run mismatch: {result.endpoint}",
                level="warning",
            )
    except Exception:
        logger.debug("sentry dual_run report skipped", exc_info=True)


def run_dual_run_check(result: DualRunResult) -> DualRunResult:
    if not result.matched:
        report_dual_run_mismatch(result)
    return result


def maybe_dual_run_list(flask_body: dict[str, Any], *, query: str = "") -> None:
    if not dual_run_enabled():
        return

    def _job() -> None:
        try:
            run_dual_run_check(compare_leads_list(flask_body, query=query))
        except Exception as exc:
            logger.exception("dual_run list failed: %s", exc)

    _dispatch(_job)


def maybe_dual_run_get(lead_id: int, flask_lead: dict[str, Any] | None) -> None:
    if not dual_run_enabled():
        return

    def _job() -> None:
        try:
            run_dual_run_check(compare_lead_get(lead_id, flask_lead))
        except Exception as exc:
            logger.exception("dual_run get failed: %s", exc)

    _dispatch(_job)


def _dispatch(job: Any) -> None:
    if dual_run_async():
        threading.Thread(target=job, daemon=True).start()
    else:
        job()


def sample_lead_ids(*, limit: int = 50, sqlite_path: str | None = None) -> list[int]:
    import sqlite3

    from ptt_jobs.config import sqlite_db_path

    db_path = sqlite_path or sqlite_db_path()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id FROM crm_leads
            WHERE COALESCE(is_duplicate, 0) = 0
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        ).fetchall()
        return [int(r[0]) for r in rows]
    finally:
        conn.close()


def run_batch_dual_run_check(
    *,
    sample_size: int = 50,
    sqlite_path: str | None = None,
    include_list: bool = True,
) -> dict[str, Any]:
    """CLI / cron batch compare — Flask read layer vs Nest."""
    from ptt_crm.leads_read import get_lead_v1, list_leads_v1

    ids = sample_lead_ids(limit=sample_size, sqlite_path=sqlite_path)
    results: list[dict[str, Any]] = []
    mismatches = 0

    if include_list and ids:
        limit = min(len(ids), 200)
        leads, total = list_leads_v1(limit=limit, offset=0)
        list_body = {"leads": leads, "total": total, "limit": limit, "offset": 0}
        list_result = run_dual_run_check(compare_leads_list(list_body, query=f"limit={limit}&offset=0"))
        results.append(list_result.to_dict())
        if not list_result.matched:
            mismatches += 1

    for lead_id in ids:
        flask_lead = get_lead_v1(lead_id)
        item = run_dual_run_check(compare_lead_get(lead_id, flask_lead))
        results.append(item.to_dict())
        if not item.matched:
            mismatches += 1

    return {
        "ok": mismatches == 0,
        "sample_size": len(ids),
        "mismatch_count": mismatches,
        "nest_url": nest_leads_base_url(),
        "results": results,
    }
