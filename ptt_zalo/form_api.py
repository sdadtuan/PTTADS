"""Zalo OA form/get API (Wave Z2)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ptt_zalo.ads_api import zalo_ads_stub_mode

logger = logging.getLogger(__name__)

_FORM_GET_URL = "https://openapi.zalo.me/v2.0/oa/form/get"


def normalize_form_lead_row(row: dict[str, Any], *, form_id: str, oa_id: str) -> dict[str, Any]:
    answers = row.get("answers") or row.get("fields") or row.get("data") or []
    phone = str(row.get("phone") or "").strip()
    email = str(row.get("email") or "").strip()
    name = str(row.get("full_name") or row.get("name") or "").strip()
    if isinstance(answers, list):
        for ans in answers:
            if not isinstance(ans, dict):
                continue
            key = str(ans.get("key") or ans.get("name") or ans.get("question") or "").lower()
            val = str(ans.get("value") or ans.get("answer") or "").strip()
            if not val:
                continue
            if "phone" in key or "sdt" in key or "mobile" in key:
                phone = phone or val
            elif "email" in key or "mail" in key:
                email = email or val
            elif "name" in key or "ten" in key or "họ" in key:
                name = name or val
    form_data_id = str(row.get("form_data_id") or row.get("id") or row.get("submit_id") or "").strip()
    return {
        "form_data_id": form_data_id,
        "form_id": str(row.get("form_id") or form_id),
        "oa_id": str(row.get("oa_id") or oa_id),
        "full_name": name,
        "phone": phone,
        "email": email,
        "submitted_at": row.get("submit_time") or row.get("created_time") or row.get("timestamp"),
        "raw": row,
    }


def stub_form_leads(*, oa_id: str, form_id: str, after_id: str | None = None) -> list[dict[str, Any]]:
    seed = f"{oa_id}:{form_id}:{after_id or 'start'}"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:8]
    base_id = f"stub_{form_id}_{digest}"
    if after_id and after_id >= base_id:
        return []
    return [
        normalize_form_lead_row(
            {
                "form_data_id": base_id,
                "form_id": form_id,
                "oa_id": oa_id,
                "full_name": "Lead Zalo Stub",
                "phone": "0901234567",
                "email": "zalo.stub@example.com",
                "submit_time": "2026-07-25T10:00:00Z",
                "answers": [],
            },
            form_id=form_id,
            oa_id=oa_id,
        )
    ]


def fetch_form_leads(
    *,
    oa_id: str,
    form_id: str,
    access_token: str,
    after_form_data_id: str | None = None,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], str | None]:
    if zalo_ads_stub_mode():
        return stub_form_leads(oa_id=oa_id, form_id=form_id, after_id=after_form_data_id), None

    params: dict[str, str | int] = {
        "form_id": form_id,
        "oa_id": oa_id,
        "limit": limit,
    }
    if after_form_data_id:
        params["after"] = after_form_data_id
    url = f"{_FORM_GET_URL}?{urllib.parse.urlencode(params)}"
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
        logger.warning("zalo form/get HTTP %s: %s", exc.code, body)
        return [], f"zalo_form_http_{exc.code}"
    except Exception as exc:
        logger.warning("zalo form/get error: %s", exc)
        return [], str(exc)

    if payload.get("error") not in (None, 0):
        return [], str(payload.get("message") or payload.get("error") or "zalo_form_api_error")

    data = payload.get("data") or payload.get("forms") or payload.get("items") or []
    if isinstance(data, dict):
        data = data.get("items") or data.get("data") or []
    if not isinstance(data, list):
        data = []

    rows: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rows.append(normalize_form_lead_row(item, form_id=form_id, oa_id=oa_id))
    return rows, None


def form_lead_poll_enabled() -> bool:
    return os.environ.get("PTT_ZALO_FORM_POLL", "0").strip().lower() in {"1", "true", "yes", "on"}
