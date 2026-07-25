"""Zalo Ads API — campaign metrics (Wave Z1)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_OAUTH_TOKEN_URL = "https://oauth.zaloapp.com/v4/access_token"
_ADS_INSIGHTS_URL = "https://business.openapi.zalo.me/ads/insights"


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def zalo_ads_stub_mode() -> bool:
    return _truthy("PTT_ZALO_ADS_STUB", "0")


def normalize_insight_row(row: dict[str, Any]) -> dict[str, Any]:
    spend = float(row.get("spend") or 0)
    impressions = int(float(row.get("impressions") or 0))
    clicks = int(float(row.get("clicks") or 0))
    return {
        "external_campaign_id": str(row.get("campaign_id") or row.get("external_campaign_id") or ""),
        "external_campaign_name": str(row.get("campaign_name") or row.get("external_campaign_name") or ""),
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "reach": row.get("reach"),
        "frequency": row.get("frequency"),
        "cpc": row.get("cpc"),
        "cpm": row.get("cpm"),
        "ctr": row.get("ctr"),
        "leads_platform": int(row.get("leads_platform") or 0),
        "raw_insights": row.get("raw_insights") or {},
    }


def stub_campaign_insights(*, since: str, until: str, account_id: str) -> list[dict[str, Any]]:
    """Deterministic stub rows for local dev without Zalo token."""
    day = since if since == until else since
    return [
        normalize_insight_row(
            {
                "campaign_id": "stub_zalo_camp_1",
                "campaign_name": f"Zalo Stub ({account_id})",
                "spend": 380000.0,
                "impressions": 9800,
                "clicks": 290,
                "leads_platform": 6,
                "raw_insights": {"date": day, "stub": True, "account_id": account_id},
            }
        )
    ]


def fetch_campaign_insights(
    *,
    account_id: str,
    access_token: str,
    since: str,
    until: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch Zalo Ads campaign insights for a date range."""
    if zalo_ads_stub_mode():
        return stub_campaign_insights(since=since, until=until, account_id=account_id), None

    params = urllib.parse.urlencode(
        {
            "account_id": account_id,
            "from_date": since,
            "to_date": until,
        }
    )
    url = f"{_ADS_INSIGHTS_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={"access_token": access_token, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        logger.warning("zalo ads insights HTTP %s: %s", exc.code, body)
        return [], f"zalo_ads_http_{exc.code}"
    except Exception as exc:
        logger.warning("zalo ads insights error: %s", exc)
        return [], str(exc)

    if payload.get("error") not in (None, 0):
        return [], str(payload.get("message") or payload.get("error") or "zalo_ads_api_error")

    rows: list[dict[str, Any]] = []
    data = payload.get("data") or payload.get("campaigns") or []
    if isinstance(data, dict):
        data = data.get("items") or data.get("campaigns") or []
    if not isinstance(data, list):
        data = []

    for item in data:
        if not isinstance(item, dict):
            continue
        rows.append(
            normalize_insight_row(
                {
                    "campaign_id": item.get("campaign_id") or item.get("id"),
                    "campaign_name": item.get("campaign_name") or item.get("name"),
                    "spend": item.get("spend") or item.get("cost") or 0,
                    "impressions": item.get("impressions") or item.get("view") or 0,
                    "clicks": item.get("clicks") or item.get("click") or 0,
                    "leads_platform": item.get("leads") or item.get("lead") or 0,
                    "raw_insights": item,
                }
            )
        )
    return rows, None
