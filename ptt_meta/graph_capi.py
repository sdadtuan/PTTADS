"""Meta Graph Conversions API — server-side events (Phase 2 M5)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ptt_meta.graph_insights import _GRAPH_VER, graph_error

logger = logging.getLogger(__name__)


def send_pixel_events(
    *,
    pixel_id: str,
    access_token: str,
    events: list[dict[str, Any]],
    test_event_code: str = "",
) -> dict[str, Any]:
    """
    POST /{pixel_id}/events — Meta Conversions API.

    Returns Graph response dict or {_graph_error: ...}.
    """
    pid = str(pixel_id or "").strip()
    token = str(access_token or "").strip()
    if not pid:
        return {"_graph_error": "pixel_id required"}
    if not token:
        return {"_graph_error": "access_token required"}
    if not events:
        return {"_graph_error": "events required"}

    body: dict[str, Any] = {"data": events, "access_token": token}
    if test_event_code.strip():
        body["test_event_code"] = test_event_code.strip()

    url = f"https://graph.facebook.com/{_GRAPH_VER}/{pid}/events"
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            raw = json.loads(exc.read().decode())
            err = raw.get("error") if isinstance(raw, dict) else {}
            return {
                "_graph_error": str(err.get("message") or exc.reason or "CAPI HTTP error"),
                "_graph_error_code": err.get("code"),
                "_graph_response": raw,
            }
        except (json.JSONDecodeError, OSError, AttributeError):
            return {"_graph_error": f"CAPI HTTP {exc.code}: {exc.reason}"}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return {"_graph_error": str(exc) or "CAPI network error"}

    if not isinstance(data, dict):
        return {"_graph_error": "invalid CAPI response"}

    err = graph_error(data)
    if err:
        return {"_graph_error": err, "_graph_response": data}

    return data
