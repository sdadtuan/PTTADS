"""Webhook Zalo / Facebook → Lead CRM."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from typing import Any

from crm_lead_store import create_lead, normalize_email, normalize_phone


def _clean_env(val: str) -> str:
    """Bỏ khoảng trắng, quote, xuống dòng — hay gây APP_SECRET 'đúng' nhưng verify fail."""
    s = str(val or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return re.sub(r"[\r\n\t]+", "", s)


def facebook_verify_token() -> str:
    return _clean_env(
        os.getenv("CRM_FACEBOOK_VERIFY_TOKEN") or os.getenv("FACEBOOK_VERIFY_TOKEN") or ""
    )


def facebook_app_secret() -> str:
    return _clean_env(
        os.getenv("CRM_FACEBOOK_APP_SECRET") or os.getenv("FACEBOOK_APP_SECRET") or ""
    )


def facebook_app_secrets() -> list[str]:
    out: list[str] = []
    for val in (
        os.getenv("CRM_FACEBOOK_APP_SECRET"),
        os.getenv("FACEBOOK_APP_SECRET"),
    ):
        s = _clean_env(val or "")
        if s and s not in out:
            out.append(s)
    return out


def facebook_app_id() -> str:
    return _clean_env(os.getenv("CRM_FACEBOOK_APP_ID") or os.getenv("FACEBOOK_APP_ID") or "")


def facebook_webhook_callback_url() -> str:
    return _clean_env(
        os.getenv("CRM_FACEBOOK_WEBHOOK_URL")
        or os.getenv("FACEBOOK_WEBHOOK_URL")
        or "https://pttads.vn/api/crm/integration/webhooks/facebook"
    ).rstrip("/")


def facebook_page_access_token() -> str:
    return _clean_env(
        os.getenv("CRM_FACEBOOK_PAGE_ACCESS_TOKEN") or os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or ""
    )


def zalo_webhook_secret() -> str:
    return _clean_env(os.getenv("CRM_ZALO_WEBHOOK_SECRET") or os.getenv("ZALO_OA_SECRET") or "")


def zalo_webhook_callback_url() -> str:
    return _clean_env(
        os.getenv("CRM_ZALO_WEBHOOK_URL")
        or os.getenv("ZALO_WEBHOOK_URL")
        or "https://pttads.vn/api/crm/integration/webhooks/zalo"
    ).rstrip("/")


def facebook_signature_hex(raw_body: bytes, *, secret: str | None = None) -> str:
    """HMAC-SHA256 hex — dùng test webhook trên VPS."""
    sec = _clean_env(secret or "") or facebook_app_secret()
    if not sec:
        return ""
    return hmac.new(sec.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def facebook_signature_headers(raw_body: bytes) -> dict[str, str]:
    sec = facebook_app_secret()
    if not sec:
        return {}
    digest = facebook_signature_hex(raw_body, secret=sec)
    return {
        "X-Hub-Signature-256": f"sha256={digest}",
        "X-Hub-Signature": f"sha1={hmac.new(sec.encode('utf-8'), raw_body, hashlib.sha1).hexdigest()}",
    }


def _signature_candidates(signature_header: str | None) -> list[tuple[str, str]]:
    """Trả (algo, hex_digest) từ header Meta."""
    sig = str(signature_header or "").strip()
    out: list[tuple[str, str]] = []
    if not sig:
        return out
    low = sig.lower()
    if low.startswith("sha256="):
        out.append(("sha256", sig.split("=", 1)[1].strip()))
    elif low.startswith("sha1="):
        out.append(("sha1", sig.split("=", 1)[1].strip()))
    return out


def verify_facebook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secrets = facebook_app_secrets()
    if not secrets:
        return True  # dev: chưa cấu hình secret
    cands = _signature_candidates(signature_header)
    if not cands:
        return False
    body = raw_body if isinstance(raw_body, (bytes, bytearray)) else b""
    for secret in secrets:
        for algo, got in cands:
            if algo == "sha256":
                expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            else:
                expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha1).hexdigest()
            if hmac.compare_digest(expected, got):
                return True
    return False


def parse_facebook_webhook_json(raw_body: bytes) -> dict[str, Any]:
    if not raw_body:
        return {}
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def verify_zalo_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secret = zalo_webhook_secret()
    if not secret:
        return True
    if not signature_header:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), signature_header.strip().lower())


def _fetch_facebook_lead(leadgen_id: str) -> dict[str, Any]:
    token = facebook_page_access_token()
    if not token:
        return {}
    url = (
        f"https://graph.facebook.com/v19.0/{leadgen_id}"
        f"?fields=id,created_time,field_data&access_token={token}"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return {}
    fields: dict[str, str] = {}
    for item in data.get("field_data") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        vals = item.get("values") or []
        if name and vals:
            fields[name] = str(vals[0])
    return {
        "full_name": fields.get("full_name") or fields.get("name") or fields.get("ho_ten") or "",
        "phone": fields.get("phone_number") or fields.get("phone") or fields.get("sdt") or "",
        "email": fields.get("email") or "",
        "need": fields.get("message") or fields.get("notes") or "",
        "product_interest": fields.get("product") or fields.get("san_pham") or "",
        "region": fields.get("city") or fields.get("region") or "",
        "utm_campaign": fields.get("campaign_id") or "",
        "meta": {"facebook_leadgen_id": leadgen_id, "raw_field_data": fields},
    }


def parse_facebook_webhook(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Trích lead từ Facebook Lead Ads webhook hoặc payload chuẩn hóa."""
    out: list[dict[str, Any]] = []

    if payload.get("full_name") or payload.get("name") or payload.get("phone") or payload.get("email"):
        out.append(
            {
                "full_name": str(payload.get("full_name") or payload.get("name") or ""),
                "phone": str(payload.get("phone") or payload.get("phone_number") or ""),
                "email": str(payload.get("email") or ""),
                "need": str(payload.get("need") or payload.get("message") or ""),
                "product_interest": str(payload.get("product_interest") or payload.get("product") or ""),
                "region": str(payload.get("region") or ""),
                "utm_campaign": str(payload.get("utm_campaign") or payload.get("campaign_id") or ""),
                "source": "facebook",
                "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {"webhook": "facebook"},
            }
        )
        return out

    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            if change.get("field") != "leadgen":
                continue
            val = change.get("value") or {}
            if not isinstance(val, dict):
                continue
            leadgen_id = str(val.get("leadgen_id") or "")
            if not leadgen_id:
                continue
            parsed = _fetch_facebook_lead_detail(leadgen_id)
            if not parsed.get("full_name") and not parsed.get("phone") and not parsed.get("email"):
                parsed = {
                    "full_name": "",
                    "phone": "",
                    "email": "",
                    "meta": {"facebook_leadgen_id": leadgen_id, "fetch": "pending_token"},
                }
            parsed["source"] = "facebook"
            parsed.setdefault("meta", {})["facebook_page_id"] = val.get("page_id")
            parsed.setdefault("meta", {})["facebook_form_id"] = val.get("form_id")
            out.append(parsed)
    return out


def _fetch_facebook_lead_detail(leadgen_id: str) -> dict[str, Any]:
    try:
        from crm_facebook_leads import fetch_facebook_lead_from_graph

        return fetch_facebook_lead_from_graph(leadgen_id)
    except Exception:
        return _fetch_facebook_lead(leadgen_id)


def _zalo_campaign_from_payload(payload: dict[str, Any], info: dict[str, Any] | str) -> str:
    if isinstance(info, dict):
        for key in ("campaign_id", "zalo_campaign_id", "ads_campaign_id", "campaign"):
            val = str(info.get(key) or "").strip()
            if val:
                return val
    for key in ("campaign_id", "zalo_campaign_id", "utm_campaign", "campaign"):
        val = str(payload.get(key) or "").strip()
        if val:
            return val
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("campaign_id", "zalo_campaign_id", "campaign"):
            val = str(meta.get(key) or "").strip()
            if val:
                return val
    return ""


def parse_zalo_webhook(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Trích lead từ Zalo OA webhook (user_submit_info, message, payload chuẩn hóa)."""
    out: list[dict[str, Any]] = []

    if payload.get("full_name") or payload.get("name") or payload.get("phone"):
        campaign_id = _zalo_campaign_from_payload(payload, {})
        out.append(
            {
                "full_name": str(payload.get("full_name") or payload.get("name") or ""),
                "phone": str(payload.get("phone") or ""),
                "email": str(payload.get("email") or ""),
                "need": str(payload.get("need") or payload.get("message") or ""),
                "product_interest": str(payload.get("product_interest") or ""),
                "region": str(payload.get("region") or ""),
                "utm_campaign": str(payload.get("utm_campaign") or campaign_id or ""),
                "campaign_id": campaign_id,
                "oa_id": str(payload.get("oa_id") or payload.get("app_id") or ""),
                "source": "zalo",
                "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {"webhook": "zalo"},
            }
        )
        return out

    event = str(payload.get("event_name") or payload.get("event") or "").lower()
    if event in ("user_submit_info", "oa_send_text", "user_send_text", "follow"):
        info = payload.get("info") or payload.get("data") or payload.get("message") or {}
        if isinstance(info, dict):
            campaign_id = _zalo_campaign_from_payload(payload, info)
            oa_id = str(payload.get("oa_id") or payload.get("app_id") or info.get("oa_id") or "").strip()
            meta = {
                "zalo_event": event,
                "oa_id": oa_id or None,
                "user_id": (payload.get("follower") or {}).get("id")
                if isinstance(payload.get("follower"), dict)
                else payload.get("user_id"),
            }
            if campaign_id:
                meta["campaign_id"] = campaign_id
            out.append(
                {
                    "full_name": str(info.get("name") or info.get("full_name") or payload.get("sender_name") or ""),
                    "phone": str(info.get("phone") or info.get("phone_number") or ""),
                    "email": str(info.get("email") or ""),
                    "need": str(info.get("message") or info.get("note") or info.get("text") or ""),
                    "utm_campaign": str(info.get("utm_campaign") or campaign_id or ""),
                    "campaign_id": campaign_id,
                    "oa_id": oa_id,
                    "source": "zalo",
                    "meta": meta,
                }
            )
        elif isinstance(info, str) and info.strip():
            out.append(
                {
                    "full_name": str(payload.get("sender_name") or "Zalo user"),
                    "phone": "",
                    "email": "",
                    "need": info.strip(),
                    "source": "zalo",
                    "meta": {"zalo_event": event, "raw_message": info[:500]},
                }
            )

    for item in payload.get("events") or []:
        if isinstance(item, dict):
            out.extend(parse_zalo_webhook(item))
    return out


def process_zalo_lead_item(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    *,
    created_by: str,
    ts: str,
    auto_assign: bool | None = None,
    re_project_id: int | None = None,
    webhook_slug: str | None = None,
) -> dict[str, Any]:
    meta_pre = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    campaign_id = str(
        item.get("campaign_id")
        or item.get("utm_campaign")
        or meta_pre.get("campaign_id")
        or meta_pre.get("zalo_campaign_id")
        or ""
    ).strip()
    oa_id = str(item.get("oa_id") or meta_pre.get("oa_id") or meta_pre.get("app_id") or "").strip()

    if re_project_id is None:
        from crm_project_webhooks import resolve_project_from_zalo_webhook

        re_project_id = resolve_project_from_zalo_webhook(
            conn,
            webhook_slug=webhook_slug,
            campaign_id=campaign_id,
            oa_id=oa_id,
        )

    project_auto_assign: bool | None = None
    if re_project_id is not None:
        from crm_project_webhooks import get_project_lead_config, project_webhook_ingest_allowed

        ok_proj, proj_reason = project_webhook_ingest_allowed(conn, int(re_project_id))
        if not ok_proj:
            return {
                "status": "filtered_out",
                "message": proj_reason,
                "re_project_id": int(re_project_id),
                "zalo_campaign_id": campaign_id or None,
            }
        pcfg = get_project_lead_config(conn, int(re_project_id))
        project_auto_assign = bool(pcfg.get("auto_assign", True))

    name = str(item.get("full_name") or "").strip()
    phone = str(item.get("phone") or "").strip()
    email = str(item.get("email") or "").strip()
    if not name:
        name = phone or email or "Lead Zalo"
    if not normalize_phone(phone) and not normalize_email(email):
        return {
            "status": "skipped",
            "message": "Thiếu SĐT hoặc email hợp lệ.",
            "full_name": name,
            "zalo_campaign_id": campaign_id or None,
        }

    meta_obj = dict(meta_pre)
    meta_obj.setdefault("ingest_channel", "zalo_ads")
    meta_obj["ingested_at"] = ts
    if campaign_id:
        meta_obj.setdefault("campaign_id", campaign_id)
    if oa_id:
        meta_obj.setdefault("oa_id", oa_id)

    do_assign = True if auto_assign is None else bool(auto_assign)
    if project_auto_assign is not None and auto_assign is None:
        do_assign = project_auto_assign

    try:
        row, dups, _dup_matches = create_lead(
            conn,
            full_name=name,
            phone=phone,
            email=email,
            source="zalo",
            region=str(item.get("region") or ""),
            product_interest=str(item.get("product_interest") or ""),
            need=str(item.get("need") or ""),
            utm_campaign=str(item.get("utm_campaign") or campaign_id or ""),
            meta=meta_obj,
            auto_assign=do_assign,
            duplicate_policy=None,
            created_by=created_by,
            ts=ts,
            re_project_id=re_project_id,
        )
    except ValueError as exc:
        return {
            "status": "error",
            "message": str(exc),
            "full_name": name,
            "zalo_campaign_id": campaign_id or None,
        }

    lead_id = int(row["id"])
    owner_id = int(row["owner_id"]) if row["owner_id"] else None
    result: dict[str, Any] = {
        "lead_id": lead_id,
        "full_name": name,
        "owner_id": owner_id,
        "zalo_campaign_id": campaign_id or None,
    }
    if re_project_id is not None:
        result["re_project_id"] = int(re_project_id)
    if dups:
        result["status"] = "duplicate_linked"
        result["message"] = f"Trùng phone/email — liên kết lead #{dups[0]['id'] if dups else ''}."
    elif owner_id:
        result["status"] = "created_assigned"
        result["message"] = f"Lead Zalo → gán NV #{owner_id}."
    else:
        result["status"] = "created_unassigned"
        result["message"] = "Lead Zalo — chưa gán NV."
    return result


def ingest_webhook_leads(
    conn: sqlite3.Connection,
    items: list[dict[str, Any]],
    *,
    default_source: str,
    created_by: str,
    ts: str,
    webhook_slug: str | None = None,
    re_project_id: int | None = None,
) -> dict[str, Any]:
    """Webhook chung — Facebook/Zalo dùng pipeline đầy đủ theo dự án."""
    if default_source == "facebook":
        from crm_facebook_leads import process_facebook_lead_item

        results: list[dict[str, Any]] = []
        for item in items:
            results.append(
                process_facebook_lead_item(
                    conn,
                    item,
                    created_by=created_by,
                    ts=ts,
                    auto_assign=True,
                    re_project_id=re_project_id,
                    webhook_slug=webhook_slug,
                )
            )
        created = [
            r for r in results if r.get("status") in ("created_assigned", "created_unassigned")
        ]
        return {
            "created_ids": [int(r["lead_id"]) for r in created if r.get("lead_id")],
            "created_count": len(created),
            "skipped": [r for r in results if r.get("status") not in ("created_assigned", "created_unassigned")],
            "results": results,
        }

    if default_source == "zalo":
        results: list[dict[str, Any]] = []
        for item in items:
            results.append(
                process_zalo_lead_item(
                    conn,
                    item,
                    created_by=created_by,
                    ts=ts,
                    auto_assign=True,
                    re_project_id=re_project_id,
                    webhook_slug=webhook_slug,
                )
            )
        created = [
            r for r in results if r.get("status") in ("created_assigned", "created_unassigned", "duplicate_linked")
        ]
        return {
            "created_ids": [int(r["lead_id"]) for r in created if r.get("lead_id")],
            "created_count": len(created),
            "skipped": [r for r in results if r.get("status") not in ("created_assigned", "created_unassigned", "duplicate_linked")],
            "results": results,
        }

    created: list[int] = []
    skipped: list[dict[str, str]] = []
    for item in items:
        name = str(item.get("full_name") or "").strip()
        phone = str(item.get("phone") or "").strip()
        email = str(item.get("email") or "").strip()
        if not name:
            name = phone or email or "Lead webhook"
        if not normalize_phone(phone) and not normalize_email(email):
            skipped.append({"reason": "Thiếu phone/email", "item": name})
            continue
        try:
            row, _dups, _dup_matches = create_lead(
                conn,
                full_name=name,
                phone=phone,
                email=email,
                source=str(item.get("source") or default_source),
                region=str(item.get("region") or ""),
                product_interest=str(item.get("product_interest") or ""),
                need=str(item.get("need") or ""),
                utm_campaign=str(item.get("utm_campaign") or ""),
                meta=item.get("meta") if isinstance(item.get("meta"), dict) else None,
                auto_assign=True,
                duplicate_policy=None,
                created_by=created_by,
                ts=ts,
            )
            created.append(int(row["id"]))
        except ValueError as exc:
            skipped.append({"reason": str(exc), "item": name})
    return {"created_ids": created, "created_count": len(created), "skipped": skipped}
