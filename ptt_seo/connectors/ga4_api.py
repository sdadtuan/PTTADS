"""Google Analytics 4 Data API client (Phase 4)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from ptt_seo.connectors.ga4_oauth import _client_config

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_RUN_REPORT = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
_ACCOUNT_SUMMARIES = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries"


def ga4_stub_mode() -> bool:
    return os.environ.get("PTT_GA4_SYNC_STUB", "0").strip().lower() in {"1", "true", "yes", "on"}


def refresh_access_token(refresh_token: str) -> str:
    cid, secret, _ = _client_config()
    body = urllib.parse.urlencode(
        {
            "client_id": cid,
            "client_secret": secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request(
        _TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    token = str(data.get("access_token") or "")
    if not token:
        raise ValueError("missing_access_token")
    return token


def list_properties(access_token: str) -> list[str]:
    """Return GA4 property IDs (numeric) accessible to the token."""
    if ga4_stub_mode():
        return ["123456789"]
    req = urllib.request.Request(
        _ACCOUNT_SUMMARIES,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    out: list[str] = []
    for acct in data.get("accountSummaries") or []:
        for prop in acct.get("propertySummaries") or []:
            raw = str(prop.get("property") or "")
            if raw.startswith("properties/"):
                out.append(raw.split("/", 1)[1])
            elif raw.isdigit():
                out.append(raw)
    return out


def fetch_daily_metrics(
    access_token: str,
    property_id: str,
    *,
    start_date: date,
    end_date: date,
    row_limit: int = 5000,
) -> list[dict[str, Any]]:
    if ga4_stub_mode():
        return _stub_rows(start_date, end_date)
    pid = property_id.replace("properties/", "").strip()
    url = _RUN_REPORT.format(property_id=urllib.parse.quote(pid, safe=""))
    payload = {
        "dateRanges": [
            {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()},
        ],
        "dimensions": [
            {"name": "date"},
            {"name": "landingPage"},
            {"name": "sessionSourceMedium"},
        ],
        "metrics": [
            {"name": "sessions"},
            {"name": "totalUsers"},
            {"name": "screenPageViews"},
            {"name": "bounceRate"},
            {"name": "averageSessionDuration"},
            {"name": "conversions"},
            {"name": "totalRevenue"},
        ],
        "limit": row_limit,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode())
            msg = err.get("error", {}).get("message") or str(err)
        except Exception:
            msg = f"HTTP {exc.code}"
        raise ValueError(msg) from exc

    dim_headers = [h.get("name") for h in data.get("dimensionHeaders") or []]
    metric_headers = [h.get("name") for h in data.get("metricHeaders") or []]
    out: list[dict[str, Any]] = []
    for row in data.get("rows") or []:
        dims = row.get("dimensionValues") or []
        mets = row.get("metricValues") or []
        dim_map = {
            dim_headers[i]: str(dims[i].get("value") or "")
            for i in range(min(len(dim_headers), len(dims)))
        }
        met_map = {
            metric_headers[i]: str(mets[i].get("value") or "0")
            for i in range(min(len(metric_headers), len(mets)))
        }
        stat_date = dim_map.get("date", end_date.isoformat())
        if len(stat_date) == 8 and stat_date.isdigit():
            stat_date = f"{stat_date[:4]}-{stat_date[4:6]}-{stat_date[6:8]}"
        out.append(
            {
                "stat_date": stat_date[:10],
                "landing_page": dim_map.get("landingPage") or "",
                "source_medium": dim_map.get("sessionSourceMedium") or "",
                "sessions": int(float(met_map.get("sessions") or 0)),
                "users": int(float(met_map.get("totalUsers") or 0)),
                "pageviews": int(float(met_map.get("screenPageViews") or 0)),
                "bounce_rate": float(met_map.get("bounceRate") or 0),
                "avg_session_duration": float(met_map.get("averageSessionDuration") or 0),
                "conversions": float(met_map.get("conversions") or 0),
                "revenue": float(met_map.get("totalRevenue") or 0),
            }
        )
    return out


def _stub_rows(start_date: date, end_date: date) -> list[dict[str, Any]]:
    d = end_date
    return [
        {
            "stat_date": d.isoformat(),
            "landing_page": "/services",
            "source_medium": "google / organic",
            "sessions": 120,
            "users": 95,
            "pageviews": 340,
            "bounce_rate": 0.42,
            "avg_session_duration": 145.5,
            "conversions": 8.0,
            "revenue": 2450.0,
        },
        {
            "stat_date": d.isoformat(),
            "landing_page": "/blog/aeo",
            "source_medium": "google / organic",
            "sessions": 45,
            "users": 38,
            "pageviews": 88,
            "bounce_rate": 0.35,
            "avg_session_duration": 210.0,
            "conversions": 3.0,
            "revenue": 890.5,
        },
        {
            "stat_date": d.isoformat(),
            "landing_page": "/",
            "source_medium": "(direct) / (none)",
            "sessions": 200,
            "users": 180,
            "pageviews": 420,
            "bounce_rate": 0.55,
            "avg_session_duration": 90.0,
            "conversions": 2.0,
            "revenue": 500.0,
        },
    ]


def default_date_range(days: int = 28) -> tuple[date, date]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=max(1, days) - 1)
    return start, end
