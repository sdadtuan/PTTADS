"""Zalo Ads alerts evaluation (Z3) — reuses meta_alerts with channel=zalo."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def zalo_alerts_enabled() -> bool:
    return _truthy("PTT_ZALO_ALERTS_ENABLED", "0")


def pg_zalo_alerts_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_meta_alerts_ready

        return pg_meta_alerts_ready()
    except Exception:
        return False


def _alert_cpl_pct() -> float:
    raw = os.environ.get("PTT_ZALO_ALERT_CPL_PCT", "15").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 15.0


def _ctr_drop_pct() -> float:
    raw = os.environ.get("PTT_ZALO_ALERT_CTR_DROP_PCT", "30").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 30.0


def _dedupe_key(
    alert_type: str,
    client_id: str,
    external_campaign_id: str | None,
    performance_date: date | None,
) -> str:
    camp = (external_campaign_id or "").strip() or "_"
    day = performance_date.isoformat() if performance_date else "_"
    return f"zalo:{alert_type}:{client_id}:{camp}:{day}"


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
                    %s::uuid, 'zalo', %s, %s, %s,
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


def _notify_milestone(client_id: str, alert_type: str, message: str) -> None:
    try:
        from ptt_zalo.slack_notify import notify_zalo_alert

        notify_zalo_alert(alert_type=alert_type, message=message, client_id=client_id)
    except Exception as exc:
        logger.debug("zalo slack notify skipped: %s", exc)
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notification_inbox (recipient_id, category, title, body, link_url, meta)
                    VALUES (
                        COALESCE(
                            (SELECT owner_am_id FROM clients WHERE id = %s::uuid LIMIT 1),
                            'am@pttads.vn'
                        ),
                        'campaign_milestone',
                        %s,
                        %s,
                        '/zalo/zalo-ads',
                        %s::jsonb
                    )
                    """,
                    (
                        client_id,
                        f"[Zalo] {alert_type}",
                        message,
                        '{"channel":"zalo","milestone":"' + alert_type + '"}',
                    ),
                )
            conn.commit()
    except Exception as exc:
        logger.debug("zalo milestone inbox skipped: %s", exc)


def evaluate_zalo_alerts(
    *,
    client_id: str | None = None,
    performance_date: date | str | None = None,
) -> dict[str, Any]:
    """Evaluate Z3 alert rules into meta_alerts (channel=zalo)."""
    if not zalo_alerts_enabled():
        return {"ok": True, "skipped": True, "reason": "alerts_disabled"}
    if not pg_zalo_alerts_ready():
        return {"ok": False, "error": "meta_alerts_table_not_ready"}

    if performance_date is None:
        perf_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    elif isinstance(performance_date, date):
        perf_date = performance_date
    else:
        perf_date = date.fromisoformat(str(performance_date)[:10])

    cpl_pct = _alert_cpl_pct()
    ctr_drop_pct = _ctr_drop_pct()
    created = 0
    client_filter = ""
    cpl_params: list[Any] = [perf_date]
    if client_id:
        client_filter = "AND dp.client_id = %s::uuid"
        cpl_params.append(client_id)

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
                WHERE dp.channel = 'zalo'
                  AND dp.performance_date = %s::date
                  {client_filter}
                GROUP BY dp.client_id, dp.external_campaign_id
                HAVING SUM(dp.spend) > 0
                """,
                cpl_params,
            )
            for row in cur.fetchall():
                cid = str(row[0])
                camp_id = str(row[1] or "")
                spend = float(row[2] or 0)
                leads = int(row[3] or 0)
                target = row[4]
                if target is not None and leads > 0:
                    target_f = float(target)
                    if target_f > 0:
                        cpl = spend / leads
                        threshold = target_f * (1.0 + cpl_pct / 100.0)
                        if cpl > threshold:
                            key = _dedupe_key("cpl_high", cid, camp_id, perf_date)
                            msg = f"Zalo CPL {cpl:,.0f} VND vượt target {target_f:,.0f} (+{cpl_pct}%)"
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
                                _notify_milestone(cid, "cpl_high", msg)
                if spend > 0 and leads == 0:
                    key = _dedupe_key("zero_leads_24h", cid, camp_id, perf_date)
                    msg = f"Zalo zero leads 24h — spend {spend:,.0f} VND, campaign {camp_id or '—'}"
                    if _insert_alert(
                        client_id=cid,
                        alert_type="zero_leads_24h",
                        severity="warning",
                        message=msg,
                        dedupe_key=key,
                        external_campaign_id=camp_id or None,
                        metric_value=0,
                        threshold_value=0,
                        performance_date=perf_date,
                    ):
                        created += 1
                        _notify_milestone(cid, "zero_leads_24h", msg)

            prev_date = perf_date - timedelta(days=1)
            ctr_params: list[Any] = [prev_date, perf_date]
            ctr_filter = ""
            if client_id:
                ctr_filter = "AND today.client_id = %s::uuid"
                ctr_params.append(client_id)
            cur.execute(
                f"""
                SELECT today.client_id::text,
                       today.external_campaign_id,
                       today.ctr AS ctr_today,
                       yesterday.ctr AS ctr_yesterday
                FROM daily_performance today
                JOIN daily_performance yesterday
                  ON yesterday.client_id = today.client_id
                 AND yesterday.external_campaign_id = today.external_campaign_id
                 AND yesterday.channel = 'zalo'
                 AND yesterday.performance_date = %s::date
                WHERE today.channel = 'zalo'
                  AND today.performance_date = %s::date
                  AND today.ctr IS NOT NULL
                  AND yesterday.ctr IS NOT NULL
                  AND yesterday.ctr > 0
                  {ctr_filter}
                """,
                ctr_params,
            )
            for row in cur.fetchall():
                cid = str(row[0])
                camp_id = str(row[1] or "")
                ctr_today = float(row[2] or 0)
                ctr_yesterday = float(row[3] or 0)
                if ctr_yesterday <= 0:
                    continue
                drop_pct = ((ctr_yesterday - ctr_today) / ctr_yesterday) * 100.0
                if drop_pct < ctr_drop_pct:
                    continue
                key = _dedupe_key("ctr_drop", cid, camp_id, perf_date)
                msg = (
                    f"Zalo CTR giảm {drop_pct:.1f}% "
                    f"({ctr_yesterday:.4f} → {ctr_today:.4f}) — ngưỡng {ctr_drop_pct:.0f}%"
                )
                if _insert_alert(
                    client_id=cid,
                    alert_type="ctr_drop",
                    severity="warning",
                    message=msg,
                    dedupe_key=key,
                    external_campaign_id=camp_id or None,
                    metric_value=drop_pct,
                    threshold_value=ctr_drop_pct,
                    performance_date=perf_date,
                ):
                    created += 1
                    _notify_milestone(cid, "ctr_drop", msg)

        conn.commit()

    return {
        "ok": True,
        "channel": "zalo",
        "performance_date": perf_date.isoformat(),
        "alerts_created": created,
    }
