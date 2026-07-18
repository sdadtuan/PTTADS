"""Nghiệp vụ Facebook Lead Ads → tối ưu → chấm điểm → phân hạng → phân công."""
from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from crm_facebook_config import (
    DEFAULT_FACEBOOK_CONFIG,
    fetch_facebook_config,
    matches_facebook_source,
    merge_facebook_config,
)
from crm_lead_store import create_lead, lead_row_to_dict, normalize_email, normalize_phone
from crm_lead_webhooks import facebook_page_access_token, parse_facebook_webhook

_GRAPH_VER = "v19.0"
_RATE_LIMIT_CODES = frozenset({80005, 80006})
_DEFAULT_RATE_LIMIT_BACKOFF_MIN = 15
_rate_limit_mono: float = 0.0


def graph_error_is_rate_limit(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    code = data.get("_graph_error_code")
    try:
        if int(code) in _RATE_LIMIT_CODES:
            return True
    except (TypeError, ValueError):
        pass
    msg = str(data.get("_graph_error") or "").lower()
    return "80005" in msg or "80006" in msg or "too many leadgen" in msg


def is_graph_rate_limited(conn: sqlite3.Connection | None = None) -> tuple[bool, str]:
    """True nếu đang trong thời gian backoff sau lỗi rate limit Leadgen API."""
    global _rate_limit_mono
    if time.monotonic() < _rate_limit_mono:
        remain_min = max(1, int((_rate_limit_mono - time.monotonic()) / 60))
        return True, f"Facebook Leadgen API bị giới hạn. Thử lại sau ~{remain_min} phút."
    if conn is None:
        return False, ""
    fb_cfg = fetch_facebook_config(conn)
    until_raw = str(fb_cfg.get("graph_rate_limited_until") or "").strip()
    if not until_raw:
        return False, ""
    try:
        until = datetime.strptime(until_raw[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False, ""
    if datetime.now() >= until:
        return False, ""
    _rate_limit_mono = max(
        _rate_limit_mono,
        time.monotonic() + max(0.0, (until - datetime.now()).total_seconds()),
    )
    msg = str(fb_cfg.get("graph_rate_limited_message") or "").strip()
    return True, msg or f"Facebook Leadgen API bị giới hạn đến {until_raw}."


def record_graph_rate_limit(
    conn: sqlite3.Connection | None,
    message: str,
    *,
    minutes: int = _DEFAULT_RATE_LIMIT_BACKOFF_MIN,
    updated_by: str = "graph_rate_limit",
) -> None:
    global _rate_limit_mono
    mins = max(5, min(360, int(minutes)))
    _rate_limit_mono = time.monotonic() + mins * 60
    if conn is None:
        return
    from crm_lead_rules import fetch_lead_config, save_lead_config

    until = datetime.now() + timedelta(minutes=mins)
    until_s = until.strftime("%Y-%m-%d %H:%M:%S")
    cfg = fetch_lead_config(conn)
    fb = merge_facebook_config(cfg.get("facebook_config"))
    fb["graph_rate_limited_until"] = until_s
    fb["graph_rate_limited_message"] = str(message or "Leadgen API rate limit (#80005).")[:500]
    cfg["facebook_config"] = fb
    save_lead_config(conn, config=cfg, updated_by=updated_by, ts=until_s)


def clear_graph_rate_limit(conn: sqlite3.Connection | None) -> None:
    global _rate_limit_mono
    _rate_limit_mono = 0.0
    if conn is None:
        return
    from crm_lead_rules import fetch_lead_config, save_lead_config

    cfg = fetch_lead_config(conn)
    fb = merge_facebook_config(cfg.get("facebook_config"))
    if not fb.get("graph_rate_limited_until"):
        return
    fb["graph_rate_limited_until"] = ""
    fb["graph_rate_limited_message"] = ""
    cfg["facebook_config"] = fb
    save_lead_config(conn, config=cfg, updated_by="graph_rate_limit", ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def _since_to_unix(since: str) -> int:
    """Chuyển last_sync_at CRM → Unix timestamp cho Graph API filtering."""
    raw = str(since or "").strip()
    if not raw:
        return 0
    if raw.isdigit():
        return int(raw)
    normalized = raw[:19].replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return int(datetime.strptime(normalized, fmt).timestamp())
        except ValueError:
            continue
    return 0


def _graph_get(path: str, *, token: str | None = None, params: dict[str, str] | None = None) -> dict[str, Any]:
    tok = (token or facebook_page_access_token() or "").strip()
    if not tok:
        return {"_graph_error": "Thiếu Page Access Token."}
    q = dict(params or {})
    q["access_token"] = tok
    url = f"https://graph.facebook.com/{_GRAPH_VER}/{path.lstrip('/')}?{urllib.parse.urlencode(q)}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
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
        return {"_graph_error": str(exc) or "Graph API lỗi mạng."}
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            out = {
                **{k: v for k, v in data.items() if k != "error"},
                "_graph_error": str(err.get("message") or "Graph API error"),
                "_graph_error_code": err.get("code"),
            }
            return out
    return data if isinstance(data, dict) else {}


def _graph_post(path: str, *, token: str | None = None, params: dict[str, str] | None = None) -> dict[str, Any]:
    tok = (token or facebook_page_access_token() or "").strip()
    if not tok:
        return {"_graph_error": "Thiếu Page Access Token."}
    form = dict(params or {})
    url = f"https://graph.facebook.com/{_GRAPH_VER}/{path.lstrip('/')}?{urllib.parse.urlencode({'access_token': tok})}"
    body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body_text = exc.read().decode()
            body = json.loads(body_text)
            err = body.get("error") if isinstance(body, dict) else {}
            msg = str(err.get("message") or exc.reason or "Graph API HTTP error")
            code = err.get("code")
            return {"_graph_error": msg, "_graph_error_code": code, "_graph_error_body": body_text[:500]}
        except (json.JSONDecodeError, OSError, AttributeError):
            return {"_graph_error": f"Graph API HTTP {exc.code}: {exc.reason}"}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return {"_graph_error": str(exc) or "Graph API lỗi mạng."}
    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            return {
                **{k: v for k, v in data.items() if k != "error"},
                "_graph_error": str(err.get("message") or "Graph API error"),
                "_graph_error_code": err.get("code"),
            }
    return data if isinstance(data, dict) else {}


def _graph_delete(path: str, *, token: str | None = None, params: dict[str, str] | None = None) -> dict[str, Any]:
    tok = (token or facebook_page_access_token() or "").strip()
    if not tok:
        return {"_graph_error": "Thiếu access token."}
    q = dict(params or {})
    q["access_token"] = tok
    url = f"https://graph.facebook.com/{_GRAPH_VER}/{path.lstrip('/')}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
            err = body.get("error") if isinstance(body, dict) else {}
            return {"_graph_error": str(err.get("message") or exc.reason), "_graph_error_code": err.get("code")}
        except (json.JSONDecodeError, OSError, AttributeError):
            return {"_graph_error": f"Graph API HTTP {exc.code}: {exc.reason}"}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return {"_graph_error": str(exc) or "Graph API lỗi mạng."}
    return data if isinstance(data, dict) else {"success": True}


def subscribe_page_to_leadgen(*, page_id: str) -> dict[str, Any]:
    """Subscribe Page vào App hiện tại với field leadgen (webhook)."""
    pid = str(page_id or "").strip()
    if not pid:
        return {"ok": False, "message": "Thiếu Page ID."}
    data = _graph_post(f"{pid}/subscribed_apps", params={"subscribed_fields": "leadgen"})
    if data.get("_graph_error"):
        return {"ok": False, "message": data["_graph_error"], "graph": data}
    return {"ok": True, "message": "Page đã subscribe leadgen.", "graph": data}


def resolve_facebook_app_id() -> str:
    """Lấy App ID từ env hoặc debug_token của Page Access Token."""
    from crm_lead_webhooks import facebook_app_id, facebook_page_access_token

    explicit = facebook_app_id()
    if explicit:
        return explicit
    page_token = facebook_page_access_token()
    if not page_token:
        return ""
    data = _graph_get("debug_token", params={"input_token": page_token}, token=page_token)
    app_id = str((data.get("data") or {}).get("app_id") or "").strip()
    return app_id


def facebook_app_access_token() -> str:
    from crm_lead_webhooks import facebook_app_id, facebook_app_secret

    aid = facebook_app_id() or resolve_facebook_app_id()
    secret = facebook_app_secret()
    if aid and secret:
        return f"{aid}|{secret}"
    return ""


def fetch_app_webhook_subscriptions(*, app_id: str = "") -> dict[str, Any]:
    """GET /{app-id}/subscriptions — webhook cấp App (bắt buộc có leadgen)."""
    aid = str(app_id or resolve_facebook_app_id()).strip()
    app_token = facebook_app_access_token()
    if not aid:
        return {"_graph_error": "Không xác định được App ID (đặt CRM_FACEBOOK_APP_ID hoặc kiểm tra Page token)."}
    if not app_token:
        return {"_graph_error": "Thiếu App Secret để gọi /subscriptions."}
    return _graph_get(f"{aid}/subscriptions", token=app_token)


def _subscription_has_leadgen(sub: dict[str, Any]) -> bool:
    if str(sub.get("object") or "").lower() != "page":
        return False
    fields = sub.get("fields") or sub.get("subscribed_fields") or []
    names: list[str] = []
    if isinstance(fields, list):
        for f in fields:
            if isinstance(f, dict):
                names.append(str(f.get("name") or f.get("field") or "").lower())
            else:
                names.append(str(f).lower())
    elif isinstance(fields, str):
        names = [x.strip().lower() for x in fields.split(",") if x.strip()]
    return "leadgen" in names


def ensure_app_webhook_leadgen(
    *,
    callback_url: str = "",
    verify_token: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Đăng ký webhook leadgen ở cấp App — hay thiếu → webhooks.delivery.rejected."""
    from crm_lead_webhooks import facebook_verify_token, facebook_webhook_callback_url

    aid = resolve_facebook_app_id()
    app_token = facebook_app_access_token()
    cb = str(callback_url or facebook_webhook_callback_url()).strip().rstrip("/")
    vtok = str(verify_token or facebook_verify_token()).strip()
    if not aid:
        return {"ok": False, "message": "Không xác định App ID."}
    if not app_token:
        return {"ok": False, "message": "Thiếu CRM_FACEBOOK_APP_SECRET."}
    if not cb or not vtok:
        return {"ok": False, "message": "Thiếu callback URL hoặc CRM_FACEBOOK_VERIFY_TOKEN."}

    subs = fetch_app_webhook_subscriptions(app_id=aid)
    if subs.get("_graph_error"):
        return {"ok": False, "message": subs["_graph_error"], "graph": subs}

    cb_norm = cb.rstrip("/")
    matched = False
    wrong_urls: list[str] = []
    for row in subs.get("data") or []:
        if not isinstance(row, dict) or not _subscription_has_leadgen(row):
            continue
        row_url = str(row.get("callback_url") or "").rstrip("/")
        if row_url == cb_norm:
            matched = True
        elif row_url:
            wrong_urls.append(row_url)

    if matched and not force:
        return {
            "ok": True,
            "message": "App đã subscribe leadgen đúng callback URL.",
            "already": True,
        }

    # Chỉ xóa subscription cũ khi --force
    if force and (matched or wrong_urls):
        _graph_delete(f"{aid}/subscriptions", token=app_token, params={"object": "page"})

    data = _graph_post(
        f"{aid}/subscriptions",
        token=app_token,
        params={
            "object": "page",
            "callback_url": cb,
            "verify_token": vtok,
            "fields": "leadgen",
        },
    )
    if data.get("_graph_error"):
        return {"ok": False, "message": data["_graph_error"], "graph": data}
    msg = "App đã đăng ký webhook leadgen."
    if wrong_urls and not force:
        msg += f" (Callback cũ trên Meta: {wrong_urls[0]} — đã gửi POST cập nhật {cb})"
    return {"ok": True, "message": msg, "graph": data, "callback_mismatch": bool(wrong_urls)}


def repair_facebook_webhook_delivery(*, page_id: str = "", force: bool = False) -> dict[str, Any]:
    """Sửa webhooks.delivery.rejected — đăng ký lại App + Page subscriptions."""
    pid = str(page_id or "").strip()
    app_r = ensure_app_webhook_leadgen(force=force)
    page_r = subscribe_page_to_leadgen(page_id=pid) if pid else {"ok": False, "message": "Thiếu Page ID."}
    inspect = inspect_webhook_subscriptions(page_id=pid)
    ok = bool(app_r.get("ok") and page_r.get("ok") and inspect.get("ready"))
    return {
        "ok": ok,
        "app": app_r,
        "page": page_r,
        "inspect": inspect,
        "message": "Webhook sẵn sàng." if ok else "Webhook chưa sẵn sàng — xem app/page/inspect.",
    }


def validate_facebook_app_credentials() -> dict[str, Any]:
    """Page token và APP_SECRET phải cùng một Meta App."""
    from crm_lead_webhooks import facebook_app_id, facebook_app_secret, facebook_page_access_token

    page_token = facebook_page_access_token()
    secret = facebook_app_secret()
    env_app = facebook_app_id()
    token_app = resolve_facebook_app_id()
    issues: list[str] = []
    if not secret:
        issues.append("Thiếu CRM_FACEBOOK_APP_SECRET.")
    if not page_token:
        issues.append("Thiếu CRM_FACEBOOK_PAGE_ACCESS_TOKEN.")
    if env_app and token_app and env_app != token_app:
        issues.append(
            f"CRM_FACEBOOK_APP_ID ({env_app}) khác App của Page token ({token_app}) — dùng secret của App {token_app}."
        )
    return {
        "ok": not issues,
        "env_app_id": env_app,
        "token_app_id": token_app,
        "secret_len": len(secret),
        "issues": issues,
    }


def inspect_webhook_subscriptions(*, page_id: str = "") -> dict[str, Any]:
    """Tổng hợp trạng thái webhook App + Page (chẩn đoán delivery.rejected)."""
    from crm_lead_webhooks import facebook_webhook_callback_url

    pid = str(page_id or "").strip()
    aid = resolve_facebook_app_id()
    app_subs = fetch_app_webhook_subscriptions(app_id=aid) if aid else {"_graph_error": "no app id"}
    app_rows = app_subs.get("data") or []
    app_leadgen = [r for r in app_rows if isinstance(r, dict) and _subscription_has_leadgen(r)]
    page_apps: list[dict[str, Any]] = []
    page_leadgen = False
    page_err = ""
    if pid:
        pdata = _graph_get(f"{pid}/subscribed_apps", params={"fields": "id,name,subscribed_fields"})
        page_err = str(pdata.get("_graph_error") or "")
        page_apps = pdata.get("data") or []
        for a in page_apps:
            if not isinstance(a, dict):
                continue
            fields = a.get("subscribed_fields") or []
            if isinstance(fields, list) and "leadgen" in [str(x).lower() for x in fields]:
                page_leadgen = True
                break
            if isinstance(fields, str) and "leadgen" in fields.lower():
                page_leadgen = True
                break
    callback = facebook_webhook_callback_url()
    cb_norm = callback.rstrip("/")
    app_urls = [str(r.get("callback_url") or "") for r in app_leadgen]
    callback_match = any(str(u).rstrip("/") == cb_norm for u in app_urls)
    return {
        "app_id": aid,
        "callback_url": callback,
        "callback_url_match": callback_match,
        "app_callback_urls": app_urls,
        "app_leadgen_subscribed": bool(app_leadgen),
        "app_subscriptions": app_rows,
        "page_leadgen_subscribed": page_leadgen,
        "page_subscribed_apps": page_apps,
        "page_error": page_err,
        "app_error": str(app_subs.get("_graph_error") or ""),
        "ready": bool(
            app_leadgen and page_leadgen and callback_match and not page_err and not app_subs.get("_graph_error")
        ),
    }


def facebook_integration_status(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    from crm_lead_webhooks import facebook_app_secret, facebook_verify_token

    fb_cfg = merge_facebook_config(None)
    if conn is not None:
        fb_cfg = fetch_facebook_config(conn)
    token_ok = bool(facebook_page_access_token())
    forms: list[dict[str, str]] = []
    graph_error = ""
    rate_limited, rate_msg = is_graph_rate_limited(conn)
    page_id = str(fb_cfg.get("page_id") or "").strip()
    if rate_limited:
        graph_error = rate_msg
    elif token_ok and page_id:
        data = _graph_get(f"{page_id}/leadgen_forms", params={"fields": "id,name,status", "limit": "50"})
        graph_error = str(data.get("_graph_error") or "")
        if graph_error_is_rate_limit(data) and conn is not None:
            record_graph_rate_limit(conn, graph_error)
            graph_error = is_graph_rate_limited(conn)[1] or graph_error
        for row in data.get("data") or []:
            if isinstance(row, dict):
                forms.append(
                    {
                        "id": str(row.get("id") or ""),
                        "name": str(row.get("name") or ""),
                        "status": str(row.get("status") or ""),
                    }
                )
    pending_count = 0
    crm_facebook_leads = 0
    cred = validate_facebook_app_credentials()
    if conn is not None:
        try:
            from crm_facebook_pending import ensure_facebook_pending_schema, list_pending_facebook_leadgens

            ensure_facebook_pending_schema(conn)
            pending_count = len(list_pending_facebook_leadgens(conn, limit=100))
        except Exception:
            pending_count = 0
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM crm_leads
                WHERE source = 'facebook'
                   OR COALESCE(json_extract(meta_json, '$.facebook_leadgen_id'), '') != ''
                """
            ).fetchone()
            crm_facebook_leads = int(row["c"] or 0) if row else 0
        except Exception:
            crm_facebook_leads = 0
    return {
        "verify_token_configured": bool(facebook_verify_token()),
        "app_secret_configured": bool(facebook_app_secret()),
        "page_access_token_configured": token_ok,
        "webhook_url_hint": "/api/crm/integration/webhooks/facebook",
        "ready": token_ok and fb_cfg.get("enabled"),
        "auto_sync_enabled": bool(fb_cfg.get("enabled") and fb_cfg.get("auto_sync", True)),
        "auto_sync_interval_minutes": int(fb_cfg.get("sync_interval_minutes") or 5),
        "graph_error": graph_error,
        "rate_limited": rate_limited,
        "rate_limited_until": str(fb_cfg.get("graph_rate_limited_until") or ""),
        "rate_limited_message": str(fb_cfg.get("graph_rate_limited_message") or ""),
        "pending_leadgen_count": pending_count,
        "crm_facebook_leads_count": crm_facebook_leads,
        "webhook_app_id": cred.get("token_app_id") or "",
        "webhook_secret_len": cred.get("secret_len") or 0,
        "webhook_cred_ok": cred.get("ok"),
        "webhook_cred_issues": cred.get("issues") or [],
        "webhook_subscriptions": inspect_webhook_subscriptions(page_id=page_id) if page_id else {},
        "last_webhook_at": str(fb_cfg.get("last_webhook_at") or ""),
        "last_webhook_created": int(fb_cfg.get("last_webhook_created") or 0),
        "last_webhook_message": str(fb_cfg.get("last_webhook_message") or ""),
        "facebook_config": fb_cfg,
        "forms_on_page": forms,
    }


def _norm_key(s: str) -> str:
    return str(s or "").strip().lower().replace(" ", "_")


_FB_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "full_name": ("full_name", "name", "ho_ten", "họ_tên", "ten", "tên", "hoten"),
    "phone": ("phone_number", "phone", "sdt", "so_dien_thoai", "số_điện_thoại", "mobile"),
    "email": ("email", "e_mail"),
    "need": ("message", "notes", "note", "cau_hoi", "câu_hỏi", "ghi_chu", "mô_tả", "mo_ta"),
    "product_interest": ("product", "san_pham", "sản_phẩm", "loai_bds", "loại_bđs", "product_interest"),
    "region": ("city", "region", "khu_vuc", "khu_vực", "quan", "quận", "tinh", "tỉnh", "dia_chi", "địa_chỉ"),
    "utm_campaign": ("campaign_id", "campaign_name", "utm_campaign", "ad_id", "adset_id"),
}


def normalize_facebook_field_data(raw: dict[str, Any] | list[Any] | None) -> dict[str, str]:
    flat: dict[str, str] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            key = _norm_key(str(k))
            if isinstance(v, list) and v:
                flat[key] = str(v[0])
            else:
                flat[key] = str(v or "")
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = _norm_key(str(item.get("name") or ""))
            vals = item.get("values") or []
            if name and vals:
                flat[name] = str(vals[0])

    out: dict[str, str] = {}
    for target, aliases in _FB_FIELD_ALIASES.items():
        for alias in aliases:
            val = flat.get(_norm_key(alias), "").strip()
            if val:
                out[target] = val
                break
    for budget_key in ("budget", "ngan_sach", "ngân_sách", "budget_vnd"):
        val = flat.get(_norm_key(budget_key), "").strip()
        if val:
            out["_budget_raw"] = val
            break
    return out


def _normalize_region(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s)
    m = re.search(r"(?:quận|quan|q\.?)\s*(\d{1,2})", s)
    if m:
        return f"q.{int(m.group(1))}"
    return s[:120]


def _normalize_phone_display(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]
    if digits.startswith("0") and len(digits) >= 10:
        return digits[:11]
    return str(raw or "").strip()


def _title_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", str(raw or "").strip())
    if not s:
        return s
    return " ".join(w[:1].upper() + w[1:].lower() if w else "" for w in s.split(" "))


def optimize_facebook_lead_item(item: dict[str, Any]) -> dict[str, Any]:
    """Tối ưu dữ liệu lead Facebook trước khi chấm điểm / phân hạng."""
    out = dict(item)
    meta = dict(out.get("meta") or {}) if isinstance(out.get("meta"), dict) else {}

    out["full_name"] = _title_name(out.get("full_name") or "")
    out["phone"] = _normalize_phone_display(out.get("phone") or "")
    out["email"] = str(out.get("email") or "").strip().lower()
    out["region"] = _normalize_region(out.get("region") or "")
    out["product_interest"] = str(out.get("product_interest") or "").strip()
    need = str(out.get("need") or "").strip()
    prod = out["product_interest"]
    if prod and prod.lower() not in need.lower():
        need = f"{need} — quan tâm {prod}".strip(" —") if need else f"Quan tâm {prod}"
    out["need"] = need[:2000]
    out["source"] = "facebook"

    meta.setdefault("ingest_channel", "facebook_lead_ads")
    meta["source_detail"] = "facebook_lead_ads"
    meta["optimized_at"] = meta.get("optimized_at") or True
    if out.get("utm_campaign"):
        meta["utm_campaign"] = out["utm_campaign"]
    out["meta"] = meta
    return out


def build_facebook_lead_item(
    *,
    full_name: str = "",
    phone: str = "",
    email: str = "",
    need: str = "",
    product_interest: str = "",
    region: str = "",
    utm_campaign: str = "",
    leadgen_id: str = "",
    page_id: str = "",
    form_id: str = "",
    field_data: dict[str, Any] | list[Any] | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapped = normalize_facebook_field_data(field_data) if field_data else {}
    meta: dict[str, Any] = {
        "ingest_channel": "facebook_lead_ads",
        "facebook_leadgen_id": str(leadgen_id or "").strip(),
    }
    if page_id:
        meta["facebook_page_id"] = str(page_id)
    if form_id:
        meta["facebook_form_id"] = str(form_id)
    if mapped.get("_budget_raw"):
        meta["budget_raw"] = mapped.pop("_budget_raw")
        try:
            digits = "".join(ch for ch in meta["budget_raw"] if ch.isdigit())
            if digits:
                meta["budget_vnd"] = int(digits)
        except (TypeError, ValueError):
            pass
    if extra_meta:
        meta.update(extra_meta)

    item = {
        "full_name": str(full_name or mapped.get("full_name") or "").strip(),
        "phone": str(phone or mapped.get("phone") or "").strip(),
        "email": str(email or mapped.get("email") or "").strip(),
        "need": str(need or mapped.get("need") or "").strip(),
        "product_interest": str(product_interest or mapped.get("product_interest") or "").strip(),
        "region": str(region or mapped.get("region") or "").strip(),
        "utm_campaign": str(utm_campaign or mapped.get("utm_campaign") or "").strip(),
        "source": "facebook",
        "meta": meta,
    }
    return optimize_facebook_lead_item(item)


def fetch_facebook_lead_from_graph(leadgen_id: str) -> dict[str, Any]:
    data = _graph_get(
        leadgen_id,
        params={"fields": "id,created_time,field_data,ad_id,adset_id,campaign_id,form_id"},
    )
    graph_err = str(data.get("_graph_error") or "")
    if graph_err and not data.get("field_data"):
        return {"meta": {"facebook_leadgen_id": leadgen_id, "_graph_error": graph_err}}
    if not data or not data.get("id"):
        return {"meta": {"facebook_leadgen_id": leadgen_id, "_graph_error": graph_err or "Không lấy được lead."}}
    fields: dict[str, str] = {}
    for item in data.get("field_data") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        vals = item.get("values") or []
        if name and vals:
            fields[name] = str(vals[0])
    return build_facebook_lead_item(
        leadgen_id=leadgen_id,
        field_data=fields,
        page_id=str(data.get("page_id") or ""),
        form_id=str(data.get("form_id") or ""),
        utm_campaign=str(data.get("campaign_id") or data.get("ad_id") or ""),
        extra_meta={
            "facebook_created_time": str(data.get("created_time") or ""),
            "raw_field_data": fields,
            "_graph_error": graph_err or None,
        },
    )


def fetch_facebook_lead_from_graph_with_retry(
    leadgen_id: str,
    *,
    attempts: int = 3,
    delay_sec: float = 1.2,
) -> dict[str, Any]:
    """Graph thường chưa có field_data ngay khi webhook leadgen vừa tới — retry ngắn."""
    import time

    last: dict[str, Any] = {"meta": {"facebook_leadgen_id": leadgen_id}}
    tries = max(1, min(int(attempts), 5))
    for i in range(tries):
        item = fetch_facebook_lead_from_graph(leadgen_id)
        last = item
        phone = str(item.get("phone") or "").strip()
        email = str(item.get("email") or "").strip()
        if phone or email:
            return item
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        gerr = str(meta.get("_graph_error") or "")
        if gerr and ("80005" in gerr or "80006" in gerr or "too many leadgen" in gerr.lower()):
            return item
        if i + 1 < tries:
            time.sleep(max(0.3, float(delay_sec)))
    return last


def fetch_leads_live_revision(conn: sqlite3.Connection) -> dict[str, Any]:
    """Revision tăng mỗi webhook Facebook — UI poll để refresh (kể cả lead trùng leadgen)."""
    from crm_facebook_config import fetch_facebook_config

    fb = fetch_facebook_config(conn)
    return {
        "revision": int(fb.get("leads_live_revision") or 0),
        "webhook_message": str(fb.get("last_webhook_message") or ""),
        "webhook_created": int(fb.get("last_webhook_created") or 0),
        "webhook_at": str(fb.get("last_webhook_at") or ""),
    }


def save_facebook_webhook_receipt(
    conn: sqlite3.Connection,
    *,
    ts: str,
    event_count: int,
    created_count: int,
    message: str,
    updated_by: str = "webhook:facebook",
) -> None:
    from crm_lead_rules import fetch_lead_config, save_lead_config

    cfg = fetch_lead_config(conn)
    fb = merge_facebook_config(cfg.get("facebook_config"))
    fb["last_webhook_at"] = ts
    fb["last_webhook_events"] = int(event_count)
    fb["last_webhook_created"] = int(created_count)
    fb["last_webhook_message"] = str(message or "")[:500]
    fb["leads_live_revision"] = int(fb.get("leads_live_revision") or 0) + 1
    save_lead_config(conn, config={"facebook_config": fb}, updated_by=updated_by, ts=ts)


def find_lead_by_facebook_leadgen_id(conn: sqlite3.Connection, leadgen_id: str) -> int | None:
    lid = str(leadgen_id or "").strip()
    if not lid:
        return None
    row = conn.execute(
        """
        SELECT id FROM crm_leads
        WHERE json_extract(meta_json, '$.facebook_leadgen_id') = ?
           OR meta_json LIKE ?
        ORDER BY id DESC LIMIT 1
        """,
        (lid, f'%"facebook_leadgen_id": "{lid}"%'),
    ).fetchone()
    return int(row["id"]) if row else None


def fetch_facebook_lead_item(leadgen_id: str) -> dict[str, Any]:
    return fetch_facebook_lead_from_graph(leadgen_id)


def _field_data_from_graph_row(row: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in row.get("field_data") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        vals = item.get("values") or []
        if name and vals:
            fields[name] = str(vals[0])
    return fields


def graph_row_to_lead_item(row: dict[str, Any], *, page_id: str = "", form_id: str = "") -> dict[str, Any]:
    """Chuyển một dòng từ {form_id}/leads (có field_data) thành lead item."""
    leadgen_id = str(row.get("id") or "").strip()
    fid = str(row.get("form_id") or form_id or "").strip()
    fields = _field_data_from_graph_row(row)
    return build_facebook_lead_item(
        leadgen_id=leadgen_id,
        page_id=page_id,
        form_id=fid,
        field_data=fields,
        utm_campaign=str(row.get("campaign_id") or row.get("ad_id") or ""),
        extra_meta={
            "facebook_created_time": str(row.get("created_time") or ""),
            "raw_field_data": fields,
        },
    )


def list_form_leads(
    form_id: str, *, since: str = "", limit: int = 50
) -> tuple[list[dict[str, Any]], str]:
    """Danh sách lead trên form (kèm field_data — 1 API call thay vì N+1)."""
    params: dict[str, str] = {
        "fields": "id,created_time,field_data,form_id,ad_id,campaign_id",
        "limit": str(max(1, min(limit, 100))),
    }
    since_unix = _since_to_unix(since)
    if since_unix > 0:
        params["filtering"] = json.dumps(
            [{"field": "time_created", "operator": "GREATER_THAN", "value": since_unix}]
        )
    data = _graph_get(f"{form_id}/leads", params=params)
    graph_err = str(data.get("_graph_error") or "")
    if graph_err:
        return [], graph_err
    rows: list[dict[str, Any]] = []
    for row in data.get("data") or []:
        if isinstance(row, dict) and row.get("id"):
            rows.append(row)
    return rows, ""


def list_form_leadgen_ids(
    form_id: str, *, since: str = "", limit: int = 50
) -> tuple[list[str], str]:
    """Danh sách leadgen_id trên form. Trả (ids, graph_error)."""
    rows, graph_err = list_form_leads(form_id, since=since, limit=limit)
    if graph_err:
        return [], graph_err
    return [str(r.get("id") or "") for r in rows if r.get("id")], ""


def _pipeline_summary(row: sqlite3.Row, conn: sqlite3.Connection) -> dict[str, Any]:
    lead = lead_row_to_dict(row, conn)
    meta = lead.get("meta") if isinstance(lead.get("meta"), dict) else {}
    return {
        "lead_id": lead["id"],
        "full_name": lead["full_name"],
        "phone": lead["phone"],
        "email": lead["email"],
        "source": lead["source"],
        "lead_score": lead["lead_score"],
        "lead_level": lead["lead_level"],
        "lead_level_label": lead.get("lead_level_label"),
        "owner_id": lead.get("owner_id"),
        "owner_name": lead.get("owner_name"),
        "assign_strategy": meta.get("assign_strategy"),
        "is_duplicate": lead.get("is_duplicate"),
        "duplicate_of_id": lead.get("duplicate_of_id"),
        "facebook_leadgen_id": meta.get("facebook_leadgen_id"),
        "facebook_page_id": meta.get("facebook_page_id"),
        "facebook_form_id": meta.get("facebook_form_id"),
        "score_breakdown": lead.get("score_breakdown") or [],
        "optimized": bool(meta.get("optimized_at")),
    }


def _lead_meta_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    raw = row["meta_json"] if isinstance(row, sqlite3.Row) else row.get("meta_json")
    try:
        meta = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except json.JSONDecodeError:
        meta = {}
    return meta if isinstance(meta, dict) else {}


def _facebook_pending_placeholder_email(leadgen_id: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z]", "", str(leadgen_id or ""))[:48] or "unknown"
    return f"fb.{safe}@pending.ptt"


def _record_facebook_webhook_repeat(
    conn: sqlite3.Connection,
    lead_id: int,
    leadgen_id: str,
    *,
    created_by: str,
    ts: str,
) -> None:
    from crm_lead_store import log_lead_activity

    conn.execute(
        "UPDATE crm_leads SET updated_at = ?, updated_by = ? WHERE id = ?",
        (ts, str(created_by or "")[:120], int(lead_id)),
    )
    log_lead_activity(
        conn,
        lead_id=int(lead_id),
        activity_type="note",
        content=f"Webhook Facebook — leadgen {leadgen_id} đã có trong CRM (Meta gửi lại).",
        created_by=created_by,
        ts=ts,
    )


def _enrich_facebook_placeholder_lead(
    conn: sqlite3.Connection,
    existing_id: int,
    item: dict[str, Any],
    *,
    created_by: str,
    ts: str,
    fb_cfg: dict[str, Any],
) -> dict[str, Any] | None:
    """Cập nhật lead placeholder khi Graph API trả SĐT/email thật."""
    from crm_lead_store import update_lead

    row = conn.execute("SELECT * FROM crm_leads WHERE id = ?", (int(existing_id),)).fetchone()
    if row is None:
        return None
    meta = _lead_meta_dict(row)
    if not meta.get("awaiting_facebook_graph"):
        return None

    phone = str(item.get("phone") or "").strip()
    email = str(item.get("email") or "").strip()
    if email.endswith("@pending.ptt"):
        email = ""
    if not normalize_phone(phone) and not normalize_email(email):
        return None

    name = str(item.get("full_name") or "").strip() or str(row["full_name"] or "")
    meta.pop("awaiting_facebook_graph", None)
    meta["facebook_enriched_at"] = ts
    meta.setdefault("ingest_channel", "facebook_lead_ads")
    item_meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    for key in ("facebook_form_id", "facebook_page_id", "raw_field_data", "facebook_created_time"):
        if item_meta.get(key) is not None:
            meta[key] = item_meta[key]

    updated = update_lead(
        conn,
        int(existing_id),
        full_name=name,
        phone=phone,
        email=email,
        region=str(item.get("region") or row["region"] or ""),
        product_interest=str(item.get("product_interest") or row["product_interest"] or ""),
        need=str(item.get("need") or row["need"] or ""),
        updated_by=created_by,
        ts=ts,
    )
    conn.execute(
        "UPDATE crm_leads SET meta_json = ?, updated_at = ?, updated_by = ? WHERE id = ?",
        (json.dumps(meta, ensure_ascii=False), ts, created_by[:120], int(existing_id)),
    )
    refreshed = conn.execute("SELECT * FROM crm_leads WHERE id = ?", (int(existing_id),)).fetchone()
    if refreshed is None:
        refreshed = updated
    summary = _pipeline_summary(refreshed, conn)
    summary["status"] = "enriched"
    summary["message"] = "Đã bổ sung dữ liệu lead Facebook từ Graph API."
    if not summary.get("owner_id") and fb_cfg.get("auto_assign", True):
        from crm_lead_store import assign_lead_owner

        rd = dict(refreshed)
        owner_id, _owner_name, strategy = assign_lead_owner(
            conn,
            region=str(item.get("region") or rd.get("region") or ""),
            product_interest=str(item.get("product_interest") or rd.get("product_interest") or ""),
            industry_slug=str(rd.get("industry_slug") or ""),
            lead_level=str(summary.get("lead_level") or ""),
            lead_score=int(summary.get("lead_score") or 0),
            source="facebook",
            need=str(item.get("need") or ""),
        )
        if owner_id:
            update_lead(conn, int(existing_id), owner_id=int(owner_id), updated_by=created_by, ts=ts)
            meta.pop("assign_failed", None)
            meta.pop("assign_failed_at", None)
            meta.pop("assign_failed_reason", None)
            meta["assign_strategy"] = strategy
            meta["auto_assigned_at"] = ts
            conn.execute(
                "UPDATE crm_leads SET meta_json = ? WHERE id = ?",
                (json.dumps(meta, ensure_ascii=False), int(existing_id)),
            )
            refreshed = conn.execute("SELECT * FROM crm_leads WHERE id = ?", (int(existing_id),)).fetchone()
            summary = _pipeline_summary(refreshed, conn)
            summary["status"] = "created_assigned"
            summary["message"] = f"Đã bổ sung + gán {summary.get('owner_name') or owner_id}."
    return summary


def process_facebook_lead_item(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    *,
    created_by: str,
    ts: str,
    auto_assign: bool | None = None,
    fb_cfg: dict[str, Any] | None = None,
    skip_source_filter: bool = False,
    re_project_id: int | None = None,
    webhook_slug: str | None = None,
) -> dict[str, Any]:
    cfg = fb_cfg if fb_cfg is not None else fetch_facebook_config(conn)
    meta_pre = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    form_id_pre = str(
        meta_pre.get("facebook_form_id") or item.get("facebook_form_id") or ""
    ).strip()
    page_id_pre = str(meta_pre.get("facebook_page_id") or item.get("facebook_page_id") or "").strip()

    from crm_lead_product_model_p3 import resolve_facebook_industry_slug

    industry_slug = resolve_facebook_industry_slug(
        conn, item, webhook_slug=webhook_slug
    )
    _ = re_project_id  # legacy param — ignored (P3)

    if not skip_source_filter:
        ok, reason = matches_facebook_source(item, cfg)
        if not ok:
            return {
                "status": "filtered_out",
                "message": reason,
                "full_name": item.get("full_name"),
                "facebook_form_id": str(
                    (item.get("meta") or {}).get("facebook_form_id")
                    or item.get("facebook_form_id")
                    or ""
                ).strip(),
            }

    if cfg.get("auto_optimize", True):
        item = optimize_facebook_lead_item(item)

    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    leadgen_id = str(meta.get("facebook_leadgen_id") or "").strip()
    if leadgen_id:
        existing = find_lead_by_facebook_leadgen_id(conn, leadgen_id)
        if existing:
            enriched = _enrich_facebook_placeholder_lead(
                conn, int(existing), item, created_by=created_by, ts=ts, fb_cfg=cfg
            )
            if enriched:
                return enriched
            row = conn.execute("SELECT * FROM crm_leads WHERE id = ?", (existing,)).fetchone()
            if row:
                _record_facebook_webhook_repeat(
                    conn, int(existing), leadgen_id, created_by=created_by, ts=ts
                )
                summary = _pipeline_summary(row, conn)
                summary["status"] = "duplicate_seen"
                summary["repeat_webhook"] = True
                summary["message"] = (
                    f"Lead Facebook #{leadgen_id} đã có (CRM #{existing}) — Meta gửi webhook lặp."
                )
                return summary

    name = str(item.get("full_name") or "").strip()
    phone = str(item.get("phone") or "").strip()
    email = str(item.get("email") or "").strip()
    if not name:
        name = phone or email or "Lead Facebook"
    meta_obj = dict(meta)
    meta_obj.setdefault("ingest_channel", "facebook_lead_ads")
    meta_obj["ingested_at"] = ts
    placeholder = False
    if not normalize_phone(phone) and not normalize_email(email):
        if not leadgen_id:
            return {
                "status": "skipped",
                "message": "Thiếu SĐT hoặc email hợp lệ.",
                "full_name": name,
                "facebook_leadgen_id": leadgen_id or None,
            }
        email = _facebook_pending_placeholder_email(leadgen_id)
        meta_obj["awaiting_facebook_graph"] = True
        placeholder = True

    do_assign = cfg.get("auto_assign", True) if auto_assign is None else bool(auto_assign)

    try:
        row, dups, dup_matches = create_lead(
            conn,
            full_name=name,
            phone=phone,
            email=email,
            source="facebook",
            region=str(item.get("region") or ""),
            product_interest=str(item.get("product_interest") or ""),
            industry_slug=industry_slug,
            need=str(item.get("need") or ""),
            utm_campaign=str(item.get("utm_campaign") or ""),
            meta=meta_obj,
            auto_assign=do_assign,
            duplicate_policy=None,
            created_by=created_by,
            ts=ts,
        )
    except ValueError as exc:
        return {
            "status": "error",
            "message": str(exc),
            "full_name": name,
            "facebook_leadgen_id": leadgen_id or None,
        }

    summary = _pipeline_summary(row, conn)
    if dup_matches:
        summary["status"] = "duplicate_linked"
        summary["message"] = f"Trùng phone/email — liên kết lead #{dups[0]['id'] if dups else ''}."
    elif summary.get("is_duplicate"):
        summary["status"] = "duplicate_linked"
        summary["message"] = "Lead trùng SĐT/email — vẫn lưu bản ghi Facebook mới (đánh dấu trùng)."
    elif summary.get("owner_id"):
        summary["status"] = "created_assigned"
        summary["message"] = (
            (f"Lead placeholder — chờ Graph API · " if placeholder else "")
            + f"Tối ưu → chấm {summary['lead_score']}đ → "
            + f"{summary.get('lead_level_label') or summary['lead_level']} → "
            + f"gán {summary.get('owner_name') or summary['owner_id']} "
            + f"({summary.get('assign_strategy') or 'auto'})."
        )
    else:
        summary["status"] = "created_unassigned"
        summary["message"] = (
            (f"Lead placeholder — chờ Graph API · " if placeholder else "")
            + f"Tối ưu → chấm {summary['lead_score']}đ → "
            + f"{summary.get('lead_level_label') or summary['lead_level']} "
            + "— chưa gán NV."
        )
    if placeholder or meta_obj.get("awaiting_facebook_graph"):
        summary["awaiting_facebook_graph"] = True
    summary["industry_slug"] = industry_slug
    return summary


def _humanize_webhook_skip_message(result: dict[str, Any]) -> str:
    """Chuyển kết quả xử lý webhook sang câu dễ hiểu (không lộ mã kỹ thuật)."""
    st = str(result.get("status") or "").strip()
    msg = str(result.get("message") or "").strip()
    if st == "duplicate_seen":
        return "Meta gửi lại lead đã có trong CRM — không tạo dòng mới."
    if st == "duplicate_skipped":
        return "Lead đã có (trùng leadgen) — bỏ qua."
    if st == "filtered_out":
        form_id = str(result.get("facebook_form_id") or "").strip()
        if not form_id and "Form " in msg:
            m = re.search(r"Form\s+(\d+)", msg)
            form_id = m.group(1) if m else ""
        if form_id or "Form" in msg:
            fid = form_id or "…"
            return (
                f"Form Facebook (ID {fid}) chưa được thêm trong cấu hình CRM. "
                "Mở «Facebook Lead» → thêm Form ID → Lưu."
            )
        if "Page" in msg:
            return "Page Facebook không khớp cấu hình — kiểm tra Page ID trong «Facebook Lead»."
        return msg or "Lead bị bỏ qua do cấu hình page/form."
    if st == "pending_retry":
        return "Đang chờ Facebook trả SĐT/email — hệ thống sẽ thử lại."
    if st == "skipped":
        return msg or "Bỏ qua — thiếu thông tin liên hệ."
    if st == "error":
        return msg or "Lỗi xử lý lead Facebook."
    if st == "rate_limited":
        return "Facebook tạm giới hạn API — thử lại sau vài phút."
    return msg or st


def _summarize_facebook_webhook_results(
    results: list[dict[str, Any]],
    *,
    created: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> str:
    """Tóm tắt webhook — lưu vào CRM, hiển thị toast (tiếng Việt, không jargon)."""
    if created:
        ids = ", ".join(f"#{r.get('lead_id')}" for r in created[:5] if r.get("lead_id"))
        parts = [f"Đã thêm {len(created)} lead Facebook mới"]
        if ids:
            parts[0] += f" ({ids})"
    else:
        parts = ["Không có lead Facebook mới lần này"]

    if not skipped:
        return parts[0]

    reasons: list[str] = []
    for r in skipped[:3]:
        line = _humanize_webhook_skip_message(r)
        if line and line not in reasons:
            reasons.append(line)

    if reasons:
        parts.append(reasons[0] if len(reasons) == 1 else f"{len(skipped)} lead chưa xử lý: {reasons[0]}")
    return " · ".join(parts)


def extract_facebook_leadgen_events(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Trích sự kiện leadgen từ webhook Meta (object=page)."""
    events: list[dict[str, str]] = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        entry_page = str(entry.get("id") or "").strip()
        for change in entry.get("changes") or []:
            if not isinstance(change, dict) or change.get("field") != "leadgen":
                continue
            val = change.get("value") or {}
            if not isinstance(val, dict):
                continue
            leadgen_id = str(val.get("leadgen_id") or "").strip()
            if not leadgen_id:
                continue
            events.append(
                {
                    "leadgen_id": leadgen_id,
                    "page_id": str(val.get("page_id") or entry_page or "").strip(),
                    "form_id": str(val.get("form_id") or "").strip(),
                }
            )
    return events


def _webhook_fetch_leadgen_item(
    ev: dict[str, str],
    *,
    page_id: str = "",
) -> dict[str, Any]:
    """Webhook nóng — thử Graph nhanh (2 lần), không block 12s."""
    leadgen_id = str(ev.get("leadgen_id") or "").strip()
    item = fetch_facebook_lead_from_graph_with_retry(leadgen_id, attempts=2, delay_sec=0.6)
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    meta["facebook_leadgen_id"] = leadgen_id
    if ev.get("form_id"):
        meta["facebook_form_id"] = ev["form_id"]
    if ev.get("page_id"):
        meta["facebook_page_id"] = ev["page_id"]
    elif page_id:
        meta["facebook_page_id"] = page_id
    item["meta"] = meta
    item["source"] = "facebook"
    return item


def process_facebook_webhook_payload(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    created_by: str,
    ts: str,
    webhook_slug: str | None = None,
    forced_project_id: int | None = None,
) -> dict[str, Any]:
    fb_cfg = fetch_facebook_config(conn)
    if not fb_cfg.get("enabled"):
        return {
            "processed_count": 0,
            "created_count": 0,
            "skipped_count": 0,
            "results": [],
            "message": "Facebook Lead chưa bật trong cấu hình CRM.",
        }
    if not fb_cfg.get("webhook_enabled", True):
        return {
            "processed_count": 0,
            "created_count": 0,
            "skipped_count": 0,
            "results": [],
            "message": "Webhook Facebook đã tắt trong cấu hình.",
        }

    results: list[dict[str, Any]] = []
    leadgen_events = extract_facebook_leadgen_events(payload)
    if leadgen_events:
        page_id = str(fb_cfg.get("page_id") or "").strip()
        for ev in leadgen_events:
            item = _webhook_fetch_leadgen_item(ev, page_id=page_id)
            ev_project = forced_project_id
            if ev_project is None:
                from crm_project_webhooks import resolve_project_from_webhook

                ev_project = resolve_project_from_webhook(
                    conn,
                    webhook_slug=webhook_slug,
                    page_id=ev.get("page_id") or page_id,
                    form_id=ev.get("form_id") or "",
                )
            results.append(
                process_facebook_lead_item(
                    conn,
                    item,
                    created_by=created_by,
                    ts=ts,
                    fb_cfg=fb_cfg,
                    skip_source_filter=True,
                    re_project_id=ev_project,
                    webhook_slug=webhook_slug,
                )
            )
    else:
        items = parse_facebook_webhook(payload)
        for item in items:
            results.append(
                process_facebook_lead_item(
                    conn, item, created_by=created_by, ts=ts, fb_cfg=fb_cfg
                )
            )
    created = [
        r
        for r in results
        if r.get("status") in ("created_assigned", "created_unassigned", "duplicate_linked")
    ]
    skipped = [
        r
        for r in results
        if r.get("status")
        not in ("created_assigned", "created_unassigned", "duplicate_linked", "duplicate_seen")
    ]
    if leadgen_events:
        from crm_facebook_pending import enqueue_facebook_leadgen

        for i, ev in enumerate(leadgen_events):
            result = results[i] if i < len(results) else {"status": "error", "message": "Không xử lý"}
            needs_enrich = bool(result.get("awaiting_facebook_graph"))
            ev_project = forced_project_id
            if ev_project is None:
                ev_project = result.get("re_project_id")
            if result.get("status") in (
                "created_assigned",
                "created_unassigned",
                "duplicate_skipped",
                "duplicate_seen",
                "filtered_out",
            ) and not needs_enrich:
                continue
            enqueue_facebook_leadgen(
                conn,
                leadgen_id=ev["leadgen_id"],
                page_id=ev.get("page_id") or "",
                form_id=ev.get("form_id") or "",
                re_project_id=int(ev_project) if ev_project else None,
                source="webhook",
                ts=ts,
                error=str(result.get("message") or "Chưa xử lý được"),
            )
    return {
        "processed_count": len(results),
        "created_count": len(created),
        "skipped_count": len(skipped),
        "results": results,
        "created_ids": [int(r["lead_id"]) for r in created if r.get("lead_id")],
        "message": _summarize_facebook_webhook_results(results, created=created, skipped=skipped),
    }


def process_facebook_leadgen_id(
    conn: sqlite3.Connection,
    leadgen_id: str,
    *,
    created_by: str,
    ts: str,
) -> dict[str, Any]:
    item = fetch_facebook_lead_item(leadgen_id)
    if not item.get("full_name") and not item.get("phone"):
        return {"status": "error", "message": "Không lấy được lead từ Facebook Graph API."}
    return process_facebook_lead_item(
        conn, item, created_by=created_by, ts=ts, skip_source_filter=True
    )


def sync_facebook_leads(
    conn: sqlite3.Connection,
    *,
    created_by: str,
    ts: str,
    limit_per_form: int = 25,
    recent_only: bool = True,
) -> dict[str, Any]:
    """Đồng bộ lead từ form Facebook đã cấu hình (Graph API).

    recent_only=True (mặc định): lấy N lead mới nhất mỗi form, bỏ qua leadgen_id đã có trong CRM.
    recent_only=False: chỉ lấy lead có created_time > last_sync_at (incremental nền).
    """
    rate_limited, rate_msg = is_graph_rate_limited(conn)
    if rate_limited:
        return {
            "ok": False,
            "rate_limited": True,
            "message": rate_msg,
            "results": [],
            "created_count": 0,
            "graph_errors": [rate_msg],
        }

    fb_cfg = fetch_facebook_config(conn)
    if not fb_cfg.get("enabled"):
        return {"ok": False, "message": "Facebook Lead chưa bật.", "results": []}
    if not facebook_page_access_token():
        return {"ok": False, "message": "Thiếu CRM_FACEBOOK_PAGE_ACCESS_TOKEN.", "results": []}

    form_ids = list(fb_cfg.get("form_ids") or [])
    page_id = str(fb_cfg.get("page_id") or "").strip()
    graph_errors: list[str] = []
    if not form_ids and page_id:
        data = _graph_get(f"{page_id}/leadgen_forms", params={"fields": "id", "limit": "50"})
        if data.get("_graph_error"):
            graph_errors.append(str(data["_graph_error"]))
            if graph_error_is_rate_limit(data):
                record_graph_rate_limit(conn, graph_errors[-1], updated_by=created_by)
                return {
                    "ok": False,
                    "rate_limited": True,
                    "message": graph_errors[-1],
                    "results": [],
                    "created_count": 0,
                    "graph_errors": graph_errors,
                }
        form_ids = [str(r.get("id") or "") for r in (data.get("data") or []) if r.get("id")]

    if not form_ids:
        msg = "Chưa cấu hình Form ID hoặc Page ID."
        if graph_errors:
            msg += f" Graph: {graph_errors[0]}"
        return {"ok": False, "message": msg, "results": [], "graph_errors": graph_errors}

    since = "" if recent_only else str(fb_cfg.get("last_sync_at") or "").strip()
    per_form = min(limit_per_form, 10) if recent_only else limit_per_form
    results: list[dict[str, Any]] = []
    listed_total = 0
    skipped_existing = 0
    hit_rate_limit = False
    for fid in form_ids:
        rows, list_err = list_form_leads(fid, since=since, limit=per_form)
        if list_err:
            graph_errors.append(f"Form {fid}: {list_err}")
            if "80005" in list_err or "too many leadgen" in list_err.lower():
                record_graph_rate_limit(conn, list_err, updated_by=created_by)
                hit_rate_limit = True
                break
        listed_total += len(rows)
        for row in rows:
            lid = str(row.get("id") or "").strip()
            if not lid:
                continue
            if recent_only and find_lead_by_facebook_leadgen_id(conn, lid):
                skipped_existing += 1
                continue
            item = graph_row_to_lead_item(row, page_id=page_id, form_id=fid)
            gerr = (item.get("meta") or {}).get("_graph_error")
            if gerr:
                graph_errors.append(str(gerr))
            results.append(
                process_facebook_lead_item(
                    conn, item, created_by=created_by, ts=ts, fb_cfg=fb_cfg
                )
            )

    created = [
        r
        for r in results
        if r.get("status") in ("created_assigned", "created_unassigned", "duplicate_linked")
    ]
    duplicates = [r for r in results if r.get("status") in ("duplicate_seen", "duplicate_skipped")]
    filtered = [r for r in results if r.get("status") == "filtered_out"]
    mode = "quét form" if recent_only else "incremental"
    msg = (
        f"Đồng bộ {len(created)} lead mới / {listed_total} trên form "
        f"({skipped_existing} đã có CRM, {len(duplicates)} trùng, {len(filtered)} lọc) ({mode})."
    )
    if filtered:
        msg += f" Lọc: {str(filtered[0].get('message') or '')[:120]}"
    if hit_rate_limit:
        msg = f"Facebook giới hạn API (#80005). {is_graph_rate_limited(conn)[1]}"
    elif listed_total == 0 and not results:
        if graph_errors:
            msg += f" Graph: {graph_errors[0][:200]}"
        else:
            msg += f" Graph trả 0 lead trên {len(form_ids)} form — kiểm tra Form ID và quyền leads_retrieval."
    elif graph_errors and not results:
        msg += f" Lỗi Graph: {graph_errors[0][:200]}"
    if len(created) > 0 and not hit_rate_limit:
        clear_graph_rate_limit(conn)
    # Chỉ cập nhật last_sync_at khi thực sự quét được lead (tránh nhảy cursor khi Graph trả 0)
    if not hit_rate_limit and (listed_total > 0 or len(created) > 0):
        _save_sync_state(conn, ts=ts, count=len(created), message=msg, updated_by=created_by)
    return {
        "ok": not hit_rate_limit,
        "rate_limited": hit_rate_limit,
        "message": msg,
        "synced_count": len(results),
        "listed_count": listed_total,
        "skipped_existing_count": skipped_existing,
        "duplicate_count": len(duplicates),
        "filtered_count": len(filtered),
        "created_count": len(created),
        "results": results,
        "created_ids": [int(r["lead_id"]) for r in created if r.get("lead_id")],
        "graph_errors": graph_errors[:5],
        "form_ids": form_ids,
    }


def run_facebook_ingest_cycle(
    conn: sqlite3.Connection,
    *,
    created_by: str,
    ts: str,
    recent_only: bool = True,
    limit_per_form: int = 25,
) -> dict[str, Any]:
    """Một vòng ingest: pending webhook → poll Graph API."""
    from crm_facebook_pending import process_pending_facebook_leads

    pending = process_pending_facebook_leads(conn, created_by=created_by, ts=ts)
    sync = sync_facebook_leads(
        conn,
        created_by=created_by,
        ts=ts,
        recent_only=recent_only,
        limit_per_form=limit_per_form,
    )
    created_ids = list(pending.get("created_ids") or []) + list(sync.get("created_ids") or [])
    pending_created = int(pending.get("created_count") or 0)
    sync_ok = bool(sync.get("ok"))
    rate_limited = bool(pending.get("rate_limited") or sync.get("rate_limited"))
    sync_msg = str(sync.get("message") or "").strip()
    pending_msg = str(pending.get("message") or "").strip()
    if rate_limited:
        top_message = sync_msg or pending_msg or "Facebook Leadgen API bị giới hạn. Thử lại sau."
    elif sync_msg:
        top_message = sync_msg
    else:
        top_message = (
            f"Pending {pending.get('created_count', 0)} + "
            f"Sync {sync.get('created_count', 0)} lead mới."
        )
    return {
        "ok": sync_ok or pending_created > 0,
        "rate_limited": rate_limited,
        "message": top_message,
        "pending": pending,
        "sync": sync,
        "created_count": len(created_ids),
        "created_ids": created_ids,
        "graph_errors": list(sync.get("graph_errors") or []),
    }


def _save_sync_state(
    conn: sqlite3.Connection,
    *,
    ts: str,
    count: int,
    message: str,
    updated_by: str,
) -> None:
    from crm_lead_rules import fetch_lead_config, save_lead_config

    cfg = fetch_lead_config(conn)
    fb = merge_facebook_config(cfg.get("facebook_config"))
    fb["last_sync_at"] = ts
    fb["last_sync_count"] = int(count)
    fb["last_sync_message"] = message[:500]
    save_lead_config(conn, config={"facebook_config": fb}, updated_by=updated_by, ts=ts)
