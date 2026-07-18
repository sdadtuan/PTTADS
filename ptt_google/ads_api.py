"""Google Ads API — campaign metrics (Phase 3 G2)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
_ADS_API_VERSION = "v17"


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def google_ads_stub_mode() -> bool:
    return _truthy("PTT_GOOGLE_INSIGHTS_STUB", "0")


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


def stub_campaign_insights(*, since: str, until: str, customer_id: str) -> list[dict[str, Any]]:
    """Deterministic stub rows for local dev without Google token."""
    day = since if since == until else since
    return [
        normalize_insight_row(
            {
                "campaign_id": "stub_google_camp_1",
                "campaign_name": f"Google Stub ({customer_id})",
                "spend": 420000.0,
                "impressions": 12000,
                "clicks": 340,
                "leads_platform": 8,
                "raw_insights": {"date": day, "stub": True, "customer_id": customer_id},
            }
        )
    ]


def _exchange_refresh_token(refresh_token: str) -> tuple[str | None, str | None]:
    client_id = (os.environ.get("PTT_GOOGLE_ADS_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("PTT_GOOGLE_ADS_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return None, "missing_google_oauth_client"
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request(
        _OAUTH_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, dict) and data.get("access_token"):
            return str(data["access_token"]), None
        return None, str(data.get("error") or "oauth_token_error")
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode())
            return None, str(err.get("error_description") or err.get("error") or exc.reason)
        except (json.JSONDecodeError, OSError, AttributeError):
            return None, f"OAuth HTTP {exc.code}"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return None, str(exc) or "oauth_network_error"


def fetch_campaign_insights(
    *,
    customer_id: str,
    refresh_token: str,
    since: str,
    until: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Fetch campaign-level daily metrics via Google Ads API searchStream.
    Requires PTT_GOOGLE_ADS_DEVELOPER_TOKEN + OAuth client env.
    """
    access_token, oauth_err = _exchange_refresh_token(refresh_token)
    if oauth_err or not access_token:
        return [], oauth_err or "missing_access_token"

    dev_token = (os.environ.get("PTT_GOOGLE_ADS_DEVELOPER_TOKEN") or "").strip()
    if not dev_token:
        return [], "missing_developer_token"

    query = (
        "SELECT campaign.id, campaign.name, metrics.cost_micros, metrics.impressions, "
        "metrics.clicks, metrics.conversions, segments.date "
        f"FROM campaign WHERE segments.date BETWEEN '{since}' AND '{until}'"
    )
    url = (
        f"https://googleads.googleapis.com/{_ADS_API_VERSION}/customers/{customer_id}/googleAds:searchStream"
    )
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "developer-token": dev_token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    rows: list[dict[str, Any]] = []
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            chunks = json.loads(resp.read().decode())
        if not isinstance(chunks, list):
            chunks = [chunks]
        for chunk in chunks:
            results = chunk.get("results") if isinstance(chunk, dict) else None
            if not isinstance(results, list):
                continue
            for item in results:
                if not isinstance(item, dict):
                    continue
                campaign = item.get("campaign") or {}
                metrics = item.get("metrics") or {}
                segments = item.get("segments") or {}
                cost_micros = int(metrics.get("costMicros") or 0)
                rows.append(
                    normalize_insight_row(
                        {
                            "campaign_id": str(campaign.get("id") or ""),
                            "campaign_name": str(campaign.get("name") or ""),
                            "spend": cost_micros / 1_000_000.0,
                            "impressions": int(metrics.get("impressions") or 0),
                            "clicks": int(metrics.get("clicks") or 0),
                            "leads_platform": int(float(metrics.get("conversions") or 0)),
                            "raw_insights": {"segments": segments, "metrics": metrics},
                        }
                    )
                )
        return rows, None
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode())
            msg = err.get("error", {}).get("message") if isinstance(err, dict) else str(exc.reason)
            return [], str(msg or exc.reason)
        except (json.JSONDecodeError, OSError, AttributeError):
            return [], f"Google Ads HTTP {exc.code}"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return [], str(exc) or "google_ads_network_error"
