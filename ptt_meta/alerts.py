"""Meta alerts evaluation (B8) — PG meta_alerts."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_alerts_enabled() -> bool:
    return _truthy("PTT_META_ALERTS_ENABLED", "0")


def pg_meta_alerts_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_meta_alerts_ready as _ready

        return _ready()
    except Exception:
        return False


def _alert_cpl_pct() -> float:
    raw = os.environ.get("PTT_META_ALERT_CPL_PCT", "15").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 15.0


def _unmapped_spend_pct_threshold() -> float:
    raw = os.environ.get("PTT_META_ALERT_UNMAPPED_SPEND_PCT", "15").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 15.0


def _dedupe_key(
    alert_type: str,
    client_id: str,
    external_campaign_id: str | None,
    performance_date: date | None,
) -> str:
    camp = (external_campaign_id or "").strip() or "_"
    day = performance_date.isoformat() if performance_date else "_"
    return f"{alert_type}:{client_id}:{camp}:{day}"


def _insert_alert(
    *,
    client_id: str,
    alert_type: str,
    severity: str,
    message: str,
    dedupe_key: str,
    external_campaign_id: str | None = None,
    metric_value: float | None = None,
    threshold_value: float | None = None,
    performance_date: date | None = None,
) -> bool:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO meta_alerts (
                    client_id, channel, external_campaign_id, alert_type, severity,
                    metric_value, threshold_value, message, performance_date, dedupe_key
                ) VALUES (
                    %s::uuid, 'meta', %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (dedupe_key) DO NOTHING
                RETURNING id
                """,
                (
                    client_id,
                    external_campaign_id,
                    alert_type,
                    severity,
                    metric_value,
                    threshold_value,
                    message,
                    performance_date,
                    dedupe_key,
                ),
            )
            return cur.fetchone() is not None


def evaluate_meta_alerts(
    *,
    client_id: str | None = None,
    performance_date: date | str | None = None,
) -> dict[str, Any]:
    """Evaluate B8 alert rules and insert deduped rows into meta_alerts."""
    if not meta_alerts_enabled():
        return {"ok": True, "skipped": True, "reason": "alerts_disabled"}
    if not pg_meta_alerts_ready():
        return {"ok": False, "error": "meta_alerts_table_not_ready"}

    if performance_date is None:
        perf_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    elif isinstance(performance_date, date):
        perf_date = performance_date
    else:
        perf_date = date.fromisoformat(str(performance_date)[:10])

    cpl_pct = _alert_cpl_pct()
    unmapped_threshold = _unmapped_spend_pct_threshold()
    created = 0

    client_filter = ""
    params: list[Any] = [perf_date, perf_date]
    if client_id:
        client_filter = "AND dp.client_id = %s::uuid"
        params.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.client_id::text,
                       dp.external_campaign_id,
                       SUM(dp.spend) AS spend,
                       SUM(dp.leads_crm) AS leads_crm,
                       MAX(hcm.target_cpl_vnd) AS target_cpl_vnd
                FROM daily_performance dp
                LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
                WHERE dp.channel = 'meta'
                  AND dp.performance_date = %s::date
                  {client_filter}
                GROUP BY dp.client_id, dp.external_campaign_id
                HAVING SUM(dp.spend) > 0
                """,
                params,
            )
            cpl_rows = cur.fetchall()

            for row in cpl_rows:
                cid = str(row[0])
                camp_id = str(row[1] or "")
                spend = float(row[2] or 0)
                leads = int(row[3] or 0)
                target = row[4]
                if target is None or leads <= 0:
                    continue
                target_f = float(target)
                if target_f <= 0:
                    continue
                cpl = spend / leads
                threshold = target_f * (1.0 + cpl_pct / 100.0)
                if cpl <= threshold:
                    continue
                key = _dedupe_key("cpl_high", cid, camp_id, perf_date)
                msg = f"CPL CRM {cpl:,.0f} VND vượt target {target_f:,.0f} (+{cpl_pct}%)"
                if _insert_alert(
                    client_id=cid,
                    alert_type="cpl_high",
                    severity="warning",
                    message=msg,
                    dedupe_key=key,
                    external_campaign_id=camp_id or None,
                    metric_value=cpl,
                    threshold_value=threshold,
                    performance_date=perf_date,
                ):
                    created += 1

            cur.execute(
                f"""
                SELECT dp.client_id::text,
                       SUM(dp.spend) FILTER (WHERE dp.hub_campaign_map_id IS NULL) AS unmapped_spend,
                       SUM(dp.spend) AS total_spend
                FROM daily_performance dp
                WHERE dp.channel = 'meta'
                  AND dp.performance_date BETWEEN (%s::date - INTERVAL '6 days') AND %s::date
                  {client_filter}
                GROUP BY dp.client_id
                HAVING SUM(dp.spend) > 0
                """,
                params,
            )
            for row in cur.fetchall():
                cid = str(row[0])
                unmapped = float(row[1] or 0)
                total = float(row[2] or 0)
                if total <= 0:
                    continue
                pct = (unmapped / total) * 100.0
                if pct < unmapped_threshold:
                    continue
                key = _dedupe_key("unmapped_spend_high", cid, None, perf_date)
                msg = f"Chi tiêu chưa map {pct:.1f}% (ngưỡng {unmapped_threshold:.0f}%)"
                if _insert_alert(
                    client_id=cid,
                    alert_type="unmapped_spend_high",
                    severity="warning",
                    message=msg,
                    dedupe_key=key,
                    metric_value=pct,
                    threshold_value=unmapped_threshold,
                    performance_date=perf_date,
                ):
                    created += 1

            sync_params: list[Any] = []
            sync_filter = ""
            if client_id:
                sync_filter = "AND cca.client_id = %s::uuid"
                sync_params.append(client_id)
            cur.execute(
                f"""
                SELECT cca.client_id::text, cca.external_account_id, cca.token_status
                FROM client_channel_accounts cca
                WHERE cca.channel = 'meta'
                  AND cca.status = 'active'
                  AND (
                    cca.token_status IN ('expired', 'revoked')
                    OR (cca.access_token_encrypted IS NULL AND cca.token_status != 'revoked')
                  )
                  {sync_filter}
                """,
                sync_params,
            )
            for row in cur.fetchall():
                cid = str(row[0])
                acct = str(row[1] or "")
                status = str(row[2] or "error")
                key = _dedupe_key("sync_failed", cid, acct, perf_date)
                msg = f"Token Meta lỗi ({status}) — account {acct}"
                if _insert_alert(
                    client_id=cid,
                    alert_type="sync_failed",
                    severity="danger",
                    message=msg,
                    dedupe_key=key,
                    external_campaign_id=None,
                    performance_date=perf_date,
                ):
                    created += 1

    anomaly_out: dict[str, Any] = {"ok": True, "skipped": True}
    try:
        from ptt_meta.anomaly import evaluate_anomaly_alerts

        anomaly_out = evaluate_anomaly_alerts(client_id=client_id, performance_date=perf_date)
        if anomaly_out.get("ok") and not anomaly_out.get("skipped"):
            created += int(anomaly_out.get("alerts_created") or 0)
    except Exception as exc:
        logger.warning("B10 anomaly eval failed: %s", exc)
        anomaly_out = {"ok": False, "error": str(exc)}

    stat_out: dict[str, Any] = {"ok": True, "skipped": True}
    try:
        from ptt_meta.anomaly_stat import evaluate_stat_anomaly_alerts

        stat_out = evaluate_stat_anomaly_alerts(client_id=client_id, performance_date=perf_date)
        if stat_out.get("ok") and not stat_out.get("skipped"):
            created += int(stat_out.get("inserted") or 0)
    except Exception as exc:
        logger.warning("B11 stat anomaly eval failed: %s", exc)
        stat_out = {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "performance_date": perf_date.isoformat(),
        "client_id": client_id,
        "alerts_created": created,
        "anomaly_eval": anomaly_out,
        "stat_anomaly_eval": stat_out,
    }
