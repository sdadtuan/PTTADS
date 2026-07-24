"""Suggest hub_campaign_map rows from unmapped Meta campaigns (B8)."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def _normalize_name(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def suggest_hub_campaign_maps(
    *,
    client_id: str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Match unmapped daily_performance campaigns to hub_campaigns and insert maps."""
    today = datetime.now(timezone.utc).date()
    d_to = date.fromisoformat(str(date_to)[:10]) if date_to else today - timedelta(days=1)
    d_from = date.fromisoformat(str(date_from)[:10]) if date_from else d_to - timedelta(days=6)

    client_filter = ""
    params: list[Any] = [d_from, d_to]
    if client_id:
        client_filter = "AND dp.client_id = %s::uuid"
        params.append(client_id)

    inserted: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.client_id::text,
                       dp.external_campaign_id,
                       MAX(dp.external_campaign_name) AS external_campaign_name,
                       SUM(dp.spend) AS spend
                FROM daily_performance dp
                LEFT JOIN hub_campaign_map hcm
                  ON hcm.client_id = dp.client_id
                 AND hcm.channel = 'meta'
                 AND hcm.external_campaign_id = dp.external_campaign_id
                 AND hcm.active IS TRUE
                WHERE dp.channel = 'meta'
                  AND dp.performance_date BETWEEN %s::date AND %s::date
                  AND hcm.id IS NULL
                  {client_filter}
                GROUP BY dp.client_id, dp.external_campaign_id
                HAVING SUM(dp.spend) > 0
                ORDER BY SUM(dp.spend) DESC
                LIMIT 200
                """,
                params,
            )
            unmapped = cur.fetchall()

            for row in unmapped:
                cid = str(row[0])
                ext_id = str(row[1] or "")
                ext_name = str(row[2] or "")
                spend = float(row[3] or 0)
                norm_name = _normalize_name(ext_name)

                cur.execute(
                    """
                    SELECT hc.id, hc.code, hc.name, hc.utm_campaign
                    FROM hub_campaigns hc
                    WHERE hc.active IS TRUE
                      AND hc.channel IN ('meta', 'other')
                    ORDER BY hc.id ASC
                    LIMIT 500
                    """
                )
                best: tuple[int, str, str, str] | None = None
                best_score = 0
                for hc in cur.fetchall():
                    hc_id = int(hc[0])
                    code = str(hc[1] or "")
                    name = str(hc[2] or "")
                    utm = str(hc[3] or "")
                    score = 0
                    if utm and utm.lower() in ext_name.lower():
                        score = 100
                    elif code and code.lower() in ext_name.lower():
                        score = 80
                    else:
                        hc_norm = _normalize_name(name)
                        if norm_name and hc_norm and (norm_name in hc_norm or hc_norm in norm_name):
                            score = 60
                    if score > best_score:
                        best_score = score
                        best = (hc_id, code, name, utm)

                if not best or best_score < 60:
                    continue

                hub_campaign_id, code, name, utm = best
                item = {
                    "client_id": cid,
                    "external_campaign_id": ext_id,
                    "external_campaign_name": ext_name or None,
                    "hub_campaign_id": hub_campaign_id,
                    "hub_campaign_code": code,
                    "hub_campaign_name": name,
                    "utm_campaign": utm,
                    "match_score": best_score,
                    "spend_vnd": round(spend, 2),
                }
                suggestions.append(item)

                if dry_run:
                    continue

                cur.execute(
                    """
                    INSERT INTO hub_campaign_map (
                        client_id, hub_campaign_id, channel,
                        external_campaign_id, external_campaign_name, active, meta
                    ) VALUES (
                        %s::uuid, %s, 'meta',
                        %s, %s, TRUE, '{"source":"b8_suggest"}'::jsonb
                    )
                    ON CONFLICT (client_id, channel, external_campaign_id) DO NOTHING
                    RETURNING id::text
                    """,
                    (cid, hub_campaign_id, ext_id, ext_name or None),
                )
                map_row = cur.fetchone()
                if map_row:
                    item["map_id"] = str(map_row[0])
                    inserted.append(item)

    return {
        "ok": True,
        "date_from": d_from.isoformat(),
        "date_to": d_to.isoformat(),
        "suggestions": suggestions,
        "inserted": inserted,
        "inserted_count": len(inserted),
        "dry_run": dry_run,
    }
