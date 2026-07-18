"""Meta Graph Marketing API — campaign insights (Phase 2 M2)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_GRAPH_VER = "v19.0"
_INSIGHTS_FIELDS = (
    "campaign_id,campaign_name,spend,impressions,clicks,reach,frequency,"
    "cpc,cpm,ctr,actions,date_start,date_stop"
)


def graph_error(data: dict[str, Any] | None) -> str | None:
    if not isinstance(data, dict):
        return None
    if data.get("_graph_error"):
        return str(data["_graph_error"])
    err = data.get("error")
    if isinstance(err, dict) and err.get("message"):
        return str(err["message"])
    return None


def _graph_get(path: str, *, access_token: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    q = dict(params or {})
    q["access_token"] = access_token
    url = f"https://graph.facebook.com/{_GRAPH_VER}/{path.lstrip('/')}?{urllib.parse.urlencode(q)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
            err = body.get("error") if isinstance(body, dict) else {}
            msg = str(err.get("message") or exc.reason or "Graph API HTTP error")
            code = err.get("code")
            return {"_graph_error": msg, "_graph_error_code": code}
        except (json.JSONDecodeError, OSError, AttributeError):
            return {"_graph_error": f"Graph API HTTP {exc.code}: {exc.reason}"}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return {"_graph_error": str(exc) or "Graph API network error"}
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            return {"_graph_error": str(err.get("message") or "Graph API error"), "_graph_error_code": err.get("code")}
    return data if isinstance(data, dict) else {"data": data}


def _parse_actions(actions: Any) -> int:
    if not isinstance(actions, list):
        return 0
    total = 0
    for item in actions:
        if not isinstance(item, dict):
            continue
        action_type = str(item.get("action_type") or "").lower()
        if "lead" in action_type:
            try:
                total += int(float(item.get("value") or 0))
            except (TypeError, ValueError):
                continue
    return total


def normalize_insight_row(row: dict[str, Any]) -> dict[str, Any]:
    spend = float(row.get("spend") or 0)
    impressions = int(float(row.get("impressions") or 0))
    clicks = int(float(row.get("clicks") or 0))
    reach = row.get("reach")
    frequency = row.get("frequency")
    return {
        "external_campaign_id": str(row.get("campaign_id") or ""),
        "external_campaign_name": str(row.get("campaign_name") or ""),
        "performance_date": str(row.get("date_start") or row.get("date_stop") or ""),
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "reach": int(float(reach)) if reach not in (None, "") else None,
        "frequency": float(frequency) if frequency not in (None, "") else None,
        "cpc": float(row["cpc"]) if row.get("cpc") not in (None, "") else None,
        "cpm": float(row["cpm"]) if row.get("cpm") not in (None, "") else None,
        "ctr": float(row["ctr"]) if row.get("ctr") not in (None, "") else None,
        "leads_platform": _parse_actions(row.get("actions")),
        "raw_insights": row,
    }


def fetch_campaign_insights(
    *,
    ad_account_id: str,
    access_token: str,
    since: str,
    until: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch campaign-level daily insights for a date range (inclusive)."""
    account = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    params = {
        "fields": _INSIGHTS_FIELDS,
        "level": "campaign",
        "time_range": json.dumps({"since": since, "until": until}),
        "time_increment": "1",
        "limit": "500",
    }
    rows: list[dict[str, Any]] = []
    path = f"{account}/insights"
    while path:
        if path.startswith("http"):
            url = path
            data = _graph_get_url(url)
        else:
            data = _graph_get(path, access_token=access_token, params=params)
            params = {}  # only first request uses query params

        err = graph_error(data)
        if err:
            return rows, err

        batch = data.get("data") or []
        if isinstance(batch, list):
            for item in batch:
                if isinstance(item, dict) and item.get("campaign_id"):
                    rows.append(normalize_insight_row(item))

        next_url = (data.get("paging") or {}).get("next")
        path = next_url if next_url else ""
    return rows, None


def _graph_get_url(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data if isinstance(data, dict) else {"data": data}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
            err = body.get("error") if isinstance(body, dict) else {}
            return {"_graph_error": str(err.get("message") or exc.reason)}
        except (json.JSONDecodeError, OSError, AttributeError):
            return {"_graph_error": f"Graph API HTTP {exc.code}"}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return {"_graph_error": str(exc)}


def stub_campaign_insights(*, since: str, until: str, ad_account_id: str) -> list[dict[str, Any]]:
    """Deterministic stub rows for local dev without Meta token."""
    day = since if since == until else since
    return [
        normalize_insight_row(
            {
                "campaign_id": "stub_campaign_1",
                "campaign_name": f"Stub Campaign ({ad_account_id})",
                "date_start": day,
                "date_stop": day,
                "spend": "150000",
                "impressions": "12000",
                "clicks": "240",
                "reach": "9000",
                "frequency": "1.33",
                "cpc": "625",
                "cpm": "12500",
                "ctr": "0.02",
                "actions": [{"action_type": "lead", "value": "3"}],
            }
        )
    ]
