#!/usr/bin/env python3
"""Kiểm tra webhook Facebook — chữ ký, verify URL, subscription App+Page.

  cd /var/www/ptt && .venv/bin/python scripts/ptt_fb_webhook_probe.py
  cd /var/www/ptt && .venv/bin/python scripts/ptt_fb_webhook_probe.py --fix --force
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _http_get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, resp.read().decode()[:500]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:500]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


def _http_post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode()[:500]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:500]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Facebook webhook PTT")
    parser.add_argument("--fix", action="store_true", help="Đăng ký lại App+Page subscriptions")
    parser.add_argument("--force", action="store_true", help="Xóa subscription App cũ rồi tạo lại")
    args = parser.parse_args()

    from crm_facebook_config import fetch_facebook_config
    from crm_facebook_leads import (
        ensure_app_webhook_leadgen,
        inspect_webhook_subscriptions,
        repair_facebook_webhook_delivery,
        resolve_facebook_app_id,
        subscribe_page_to_leadgen,
        validate_facebook_app_credentials,
    )
    from crm_lead_webhooks import (
        facebook_app_secret,
        facebook_signature_hex,
        facebook_signature_headers,
        facebook_verify_token,
        facebook_webhook_callback_url,
    )
    from ptt_crm.crm_sqlite import get_connection

    ok = True
    cb = facebook_webhook_callback_url()
    vtok = facebook_verify_token()
    secret = facebook_app_secret()

    _section("1. Biến môi trường")
    print(f"  Callback URL: {cb}")
    if cb.endswith("/"):
        ok = False
        print("  ❌ Callback URL có dấu / cuối — Meta sẽ nhận 404 → delivery.rejected")
    if not cb.startswith("https://"):
        ok = False
        print("  ❌ Callback URL phải bắt đầu https:// (http redirect làm POST thành 405)")
    print(f"  Verify token: {'OK' if vtok else 'THIẾU'} ({len(vtok)} ký tự)")
    print(f"  App secret: {'OK' if secret else 'THIẾU'} ({len(secret)} ký tự — không phải Client Token)")
    if secret:
        print(f"  App secret fp: {secret[:3]}…{secret[-3:]} (so sánh sau restart ptt)")
    cred = validate_facebook_app_credentials()
    print(f"  App ID (token): {cred.get('token_app_id') or resolve_facebook_app_id() or 'THIẾU'}")
    if cred.get("env_app_id"):
        print(f"  App ID (.env):  {cred.get('env_app_id')}")
    for issue in cred.get("issues") or []:
        ok = False
        print(f"  ❌ {issue}")
    if not vtok or not secret:
        ok = False

    _section("2. GET hub.challenge (Meta verify)")
    if vtok:
        q = urllib.parse.urlencode(
            {"hub.mode": "subscribe", "hub.verify_token": vtok, "hub.challenge": "probe123"}
        )
        code, body = _http_get(f"{cb}?{q}")
        if code == 200 and body.strip() == "probe123":
            print("  ✅ Verify token khớp — Meta có thể xác minh callback URL")
        else:
            ok = False
            print(f"  ❌ HTTP {code} body={body!r}")
            print("     → CRM_FACEBOOK_VERIFY_TOKEN phải khớp Meta → Webhooks → Verify Token")
    else:
        ok = False
        print("  ❌ Thiếu CRM_FACEBOOK_VERIFY_TOKEN")

    _section("3. POST chữ ký (APP_SECRET)")
    if secret:
        payload = b'{"object":"page","entry":[]}'
        sig = facebook_signature_hex(payload)
        code, body = _http_post(
            cb,
            payload,
            {
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={sig}",
            },
        )
        if code == 200:
            print("  ✅ APP_SECRET đúng — server trả 200 EVENT_RECEIVED")
        else:
            ok = False
            print(f"  ❌ HTTP {code} — server phải luôn trả 200 cho Meta webhook")
            print(f"     body={body[:200]}")
    else:
        ok = False
        print("  ❌ Thiếu CRM_FACEBOOK_APP_SECRET")

    _section("3b. POST không chữ ký (Meta queue)")
    code, body = _http_post(cb, b'{"object":"page"}', {"Content-Type": "application/json"})
    if code == 200:
        print("  ✅ Server trả 200 khi thiếu chữ ký (Meta không bị kẹt delivery.rejected)")
    else:
        ok = False
        print(f"  ❌ HTTP {code} — phải 200, không 401 (401 kẹt hàng đợi leadgen Meta)")

    _section("3c. POST URL có dấu / cuối")
    code, body = _http_post(f"{cb}/", b'{"object":"page"}', {"Content-Type": "application/json"})
    if code == 200:
        print("  ✅ URL có / cuối vẫn trả 200 (Flask strict_slashes=False hoặc Nginx redirect)")
    else:
        ok = False
        print(f"  ❌ HTTP {code} — Meta có thể đăng ký URL có / cuối → delivery.rejected")
        print("     Sửa callback URL trên Meta Dashboard hoặc áp dụng deploy/nginx-facebook-webhook.conf")

    with get_connection() as conn:
        fb_cfg = fetch_facebook_config(conn)
    page_id = str(fb_cfg.get("page_id") or "").strip()

    _section("4. Subscriptions App + Page")
    info = inspect_webhook_subscriptions(page_id=page_id)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    if not info.get("app_leadgen_subscribed"):
        ok = False
        print("  ❌ App chưa subscribe leadgen")
    if not info.get("page_leadgen_subscribed"):
        ok = False
        print("  ❌ Page chưa subscribe leadgen")
    if info.get("app_leadgen_subscribed") and not info.get("callback_url_match"):
        ok = False
        print("  ❌ Callback URL trên Meta App KHÁC URL trong .env:")
        print(f"     .env: {cb}")
        for u in info.get("app_callback_urls") or []:
            print(f"     Meta: {u}")

    if args.fix:
        _section("5. Sửa subscriptions (repair)")
        force = args.force or not info.get("callback_url_match")
        if force and not args.force:
            print("  ℹ️  Callback URL lệch — tự bật --force để đăng ký lại App subscription")
        repair = repair_facebook_webhook_delivery(page_id=page_id, force=force)
        print(json.dumps(repair, ensure_ascii=False, indent=2))
        if not repair.get("ok"):
            ok = False
        info = repair.get("inspect") or inspect_webhook_subscriptions(page_id=page_id)

    _section("6. Nginx")
    print("  Nếu probe OK mà Meta vẫn rejected → kiểm tra Nginx chuyển header chữ ký:")
    print("  Xem deploy/nginx-facebook-webhook.conf và reload nginx")
    print("  sudo nginx -t && sudo systemctl reload nginx")

    _section("Kết luận")
    if ok:
        print("  Webhook sẵn sàng. Gửi lead test → Meta deliveries phải HTTP 200.")
    else:
        print("  ❌ Sửa các mục trên, rồi chạy lại:")
        print("     .venv/bin/python scripts/ptt_fb_webhook_probe.py --fix --force")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
