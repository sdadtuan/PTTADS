"""Google Search Console API client (Phase 4)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from ptt_seo.connectors.gsc_oauth import _client_config, resolve_gsc_refresh_token

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
_SEARCH_ANALYTICS = "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"


def gsc_stub_mode() -> bool:
    return os.environ.get("PTT_GSC_SYNC_STUB", "0").strip().lower() in {"1", "true", "yes", "on"}


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


def list_sites(access_token: str) -> list[str]:
    if gsc_stub_mode():
        return ["https://example.com/"]
    req = urllib.request.Request(
        _SITES_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    entries = data.get("siteEntry") or []
    return [str(e.get("siteUrl") or "") for e in entries if e.get("siteUrl")]


def fetch_search_analytics(
    access_token: str,
    site_url: str,
    *,
    start_date: date,
    end_date: date,
    row_limit: int = 5000,
) -> list[dict[str, Any]]:
    if gsc_stub_mode():
        return _stub_rows(start_date, end_date)
    encoded_site = urllib.parse.quote(site_url, safe="")
    url = _SEARCH_ANALYTICS.format(site=encoded_site)
    payload = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": ["query", "page", "date"],
        "rowLimit": row_limit,
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
    rows = data.get("rows") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        keys = row.get("keys") or []
        query = keys[0] if len(keys) > 0 else ""
        page = keys[1] if len(keys) > 1 else ""
        stat_date = keys[2] if len(keys) > 2 else end_date.isoformat()
        out.append(
            {
                "query": query,
                "page": page,
                "stat_date": str(stat_date)[:10],
                "clicks": int(row.get("clicks") or 0),
                "impressions": int(row.get("impressions") or 0),
                "ctr": float(row.get("ctr") or 0),
                "position": float(row.get("position") or 0),
            }
        )
    return out


def _stub_rows(start_date: date, end_date: date) -> list[dict[str, Any]]:
    d = end_date
    return [
        {
            "query": "seo agency",
            "page": "https://example.com/services",
            "stat_date": d.isoformat(),
            "clicks": 12,
            "impressions": 120,
            "ctr": 0.1,
            "position": 4.2,
        },
        {
            "query": "aeo marketing",
            "page": "https://example.com/blog/aeo",
            "stat_date": d.isoformat(),
            "clicks": 5,
            "impressions": 80,
            "ctr": 0.0625,
            "position": 6.1,
        },
    ]


def default_date_range(days: int = 28) -> tuple[date, date]:
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=max(1, days) - 1)
    return start, end
