#!/usr/bin/env python3
"""Chẩn đoán Facebook Lead sync — chạy trên VPS trong thư mục PTT.

  cd /var/www/ptt && .venv/bin/python scripts/ptt_fb_diagnose.py
  cd /var/www/ptt && .venv/bin/python scripts/ptt_fb_diagnose.py --sync-full
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def _mask(val: str) -> str:
    v = (val or "").strip()
    if not v:
        return "(trống)"
    if len(v) <= 10:
        return v[:3] + "…"
    return v[:6] + "…" + v[-4:]


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chẩn đoán Facebook Lead sync PTT")
    parser.add_argument(
        "--sync-full",
        action="store_true",
        help="Chạy sync đầy đủ (recent_only=false) sau chẩn đoán",
    )
    parser.add_argument(
        "--sync-auto",
        action="store_true",
        help="Chạy sync autosync (giống cron) sau chẩn đoán",
    )
    parser.add_argument(
        "--reset-sync-cursor",
        action="store_true",
        help="Xóa last_sync_at và cooldown rate limit Graph trong CRM config",
    )
    parser.add_argument(
        "--subscribe-page",
        action="store_true",
        help="POST Page/subscribed_apps?subscribed_fields=leadgen (bật webhook leadgen)",
    )
    parser.add_argument(
        "--fix-webhook",
        action="store_true",
        help="Sửa webhooks.delivery.rejected: đăng ký leadgen ở App + Page",
    )
    parser.add_argument(
        "--force-webhook",
        action="store_true",
        help="Xóa subscription App cũ rồi đăng ký lại (dùng với --fix-webhook)",
    )
    args = parser.parse_args()

    from crm_facebook_config import fetch_facebook_config
    from crm_facebook_leads import (
        _graph_get,
        clear_graph_rate_limit,
        facebook_integration_status,
        list_form_leadgen_ids,
        run_facebook_ingest_cycle,
        subscribe_page_to_leadgen,
        ensure_app_webhook_leadgen,
        inspect_webhook_subscriptions,
        resolve_facebook_app_id,
    )
    from crm_facebook_pending import ensure_facebook_pending_schema, list_pending_facebook_leadgens
    from crm_lead_webhooks import (
        facebook_app_secret,
        facebook_page_access_token,
        facebook_verify_token,
        facebook_webhook_callback_url,
    )
    from app import _crm_ts, get_connection

    if args.reset_sync_cursor:
        _section("Reset sync cursor")
        from crm_lead_rules import fetch_lead_config, save_lead_config

        with get_connection() as conn:
            cfg = fetch_lead_config(conn)
            fb = dict(cfg.get("facebook_config") or {})
            fb["last_sync_at"] = ""
            fb["last_sync_count"] = 0
            fb["last_sync_message"] = ""
            fb["graph_rate_limited_until"] = ""
            fb["graph_rate_limited_message"] = ""
            save_lead_config(
                conn,
                config={"facebook_config": fb},
                updated_by="diagnose:reset",
                ts=_crm_ts(),
            )
            clear_graph_rate_limit(conn)
            conn.commit()
        print("  ✅ Đã xóa last_sync_at và rate limit cooldown.")

    ok = True

    _section("1. Biến môi trường (.env)")
    for key in (
        "CRM_FACEBOOK_VERIFY_TOKEN",
        "CRM_FACEBOOK_APP_SECRET",
        "CRM_FACEBOOK_PAGE_ACCESS_TOKEN",
        "CRM_FACEBOOK_SYNC_SECRET",
    ):
        val = os.getenv(key, "")
        status = "OK" if val.strip() else "THIẾU"
        if status == "THIẾU" and key != "CRM_FACEBOOK_SYNC_SECRET":
            ok = False
        print(f"  {key}: {status} {_mask(val)}")

    token = facebook_page_access_token()
    if not token:
        print("\n  ❌ Thiếu CRM_FACEBOOK_PAGE_ACCESS_TOKEN — không thể gọi Graph API.")
        return 1

    _section("2. Kiểm tra token Graph API")
    me = _graph_get("me", params={"fields": "id,name"})
    if me.get("_graph_error"):
        ok = False
        print(f"  ❌ Token lỗi: {me['_graph_error']}")
    else:
        print(f"  ✅ Token hợp lệ — Page: {me.get('name') or me.get('id')}")

    _section("3. Cấu hình CRM (database)")
    with get_connection() as conn:
        fb_cfg = fetch_facebook_config(conn)
        status = facebook_integration_status(conn)
        ensure_facebook_pending_schema(conn)
        pending = list_pending_facebook_leadgens(conn, limit=20)
        fb_leads = conn.execute(
            "SELECT COUNT(*) FROM crm_leads WHERE source='facebook'"
        ).fetchone()[0]

    print(json.dumps(fb_cfg, ensure_ascii=False, indent=2))
    if not fb_cfg.get("enabled"):
        ok = False
        print("  ❌ Facebook Lead CHƯA BẬT trong CRM → Leads → Cấu hình → tab Facebook")
    if not fb_cfg.get("auto_sync", True):
        print("  ⚠ Tự động đồng bộ TẮT — cron sẽ bỏ qua (skipped)")
    if not fb_cfg.get("auto_assign", True):
        print("  ⚠ Tự động phân công TẮT — không có thông báo cho NV")
    form_ids = list(fb_cfg.get("form_ids") or [])
    page_id = str(fb_cfg.get("page_id") or "").strip()
    if not form_ids and not page_id:
        ok = False
        print("  ❌ Thiếu Page ID và Form ID")

    print(f"\n  Lead Facebook trong CRM: {fb_leads}")
    print(f"  Pending webhook queue: {len(pending)}")
    wh_at = str(fb_cfg.get("last_webhook_at") or "").strip()
    if wh_at:
        print(f"  ✅ Webhook nhận lần cuối: {wh_at} (+{fb_cfg.get('last_webhook_created', 0)} lead)")
    else:
        print("  ⚠ Chưa nhận webhook nào — Meta chưa gửi hoặc APP_SECRET sai (401)")
    if pending:
        for p in pending[:5]:
            print(f"    - {p['leadgen_id']}: {p.get('last_error') or 'chờ xử lý'}")

    _section("4. Graph API — form & lead")
    forms = status.get("forms_on_page") or []
    if status.get("graph_error"):
        ok = False
        print(f"  ❌ leadgen_forms: {status['graph_error']}")
    elif forms:
        print(f"  ✅ forms_on_page ({len(forms)}):")
        for f in forms[:10]:
            print(f"    - {f.get('id')} {f.get('name') or ''}")
    else:
        print("  ⚠ forms_on_page rỗng — cần Form ID thủ công hoặc quyền leads_retrieval")

    test_forms = form_ids or [str(f.get("id") or "") for f in forms if f.get("id")]
    if not test_forms and page_id:
        data = _graph_get(f"{page_id}/leadgen_forms", params={"fields": "id", "limit": "5"})
        test_forms = [str(r.get("id") or "") for r in (data.get("data") or []) if r.get("id")]

    for fid in test_forms[:3]:
        ids, err = list_form_leadgen_ids(fid, limit=5)
        if err:
            ok = False
            print(f"  ❌ Form {fid}/leads: {err}")
        else:
            print(f"  ✅ Form {fid}/leads: {len(ids)} lead (mẫu: {ids[:3]})")

    _section("5. Webhook")
    cb_url = facebook_webhook_callback_url()
    print(f"  URL: {cb_url}")
    print(f"  Verify token: {'OK' if facebook_verify_token() else 'THIẾU'}")
    print(f"  App secret: {'OK' if facebook_app_secret() else 'THIẾU (dev: không verify chữ ký)'}")
    app_id = resolve_facebook_app_id()
    print(f"  App ID: {app_id or '(chưa xác định — thêm CRM_FACEBOOK_APP_ID)'}")
    print(f"  CRM webhook_enabled: {fb_cfg.get('webhook_enabled', True)}")
    wh_info = inspect_webhook_subscriptions(page_id=page_id)
    if wh_info.get("app_error"):
        ok = False
        print(f"  ❌ App /subscriptions: {wh_info['app_error']}")
    elif wh_info.get("app_leadgen_subscribed"):
        print("  ✅ App đã subscribe field leadgen (cấp App)")
        if not wh_info.get("callback_url_match"):
            ok = False
            print(f"  ❌ Callback URL Meta ≠ .env ({cb_url})")
            for u in wh_info.get("app_callback_urls") or []:
                print(f"     Meta: {u}")
            print("     Chạy: .venv/bin/python scripts/ptt_fb_webhook_probe.py --fix --force")
    else:
        ok = False
        print("  ❌ App CHƯA subscribe leadgen → Meta báo webhooks.delivery.rejected")
        print("     Chạy: .venv/bin/python scripts/ptt_fb_diagnose.py --fix-webhook")
    if wh_info.get("page_error"):
        print(f"  ⚠ Page subscribed_apps: {wh_info['page_error']}")
    elif wh_info.get("page_leadgen_subscribed"):
        print("  ✅ Page đã subscribe leadgen (cấp Page)")
    else:
        ok = False
        print("  ❌ Page CHƯA subscribe leadgen")
    if status.get("rate_limited"):
        print(f"  ⚠ Rate limit Graph: {status.get('rate_limited_message') or status.get('graph_error')}")
    print("  Lỗi delivery.rejected thường do: App+Page thiếu leadgen, APP_SECRET sai (401), hoặc URL không trả 200.")
    if args.fix_webhook or args.subscribe_page:
        _section("Sửa webhook subscriptions")
        app_result = ensure_app_webhook_leadgen(force=args.force_webhook)
        if app_result.get("ok"):
            tag = " (đã có)" if app_result.get("already") else ""
            print(f"  ✅ App: {app_result.get('message')}{tag}")
        else:
            ok = False
            print(f"  ❌ App: {app_result.get('message')}")
        if page_id:
            sub_result = subscribe_page_to_leadgen(page_id=page_id)
            if sub_result.get("ok"):
                print(f"  ✅ Page: {sub_result.get('message')}")
            else:
                ok = False
                print(f"  ❌ Page: {sub_result.get('message')}")
        else:
            ok = False
            print("  ❌ Thiếu Page ID trong CRM config")

    do_sync = args.sync_full or args.sync_auto
    if do_sync:
        _section("6. Chạy sync thử")
        if args.sync_full:
            label = "quét form (50–100 lead mới nhất, bỏ qua đã có CRM)"
            recent_only = True
            limit = 100
        else:
            label = "autosync (cron)"
            recent_only = True
            limit = 10
        print(f"  Mode: {label}")
        with get_connection() as conn:
            result = run_facebook_ingest_cycle(
                conn,
                created_by="diagnose:facebook",
                ts=_crm_ts(),
                recent_only=recent_only,
                limit_per_form=limit,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("graph_errors"):
            ok = False
        listed = int((result.get("sync") or {}).get("listed_count") or 0)
        created = int(result.get("created_count") or 0)
        filtered = int((result.get("sync") or {}).get("filtered_count") or 0)
        if filtered:
            print(f"  ⚠ {filtered} lead bị lọc — kiểm tra Form ID / Page ID trong CRM")
        if listed == 0 and created == 0 and not result.get("graph_errors"):
            print("  ⚠ Graph trả 0 lead — token/form OK? Form ID đúng?")
    else:
        _section("6. Gợi ý chạy sync")
        print("  .venv/bin/python scripts/ptt_fb_diagnose.py --sync-auto")
        print("  .venv/bin/python scripts/ptt_fb_diagnose.py --sync-full   # kéo lead cũ trên form")

    _section("Kết luận")
    if ok:
        print("  Cấu hình cơ bản OK. Nếu vẫn 0 lead mới → chạy --sync-full hoặc lead đã có trong CRM.")
    else:
        print("  ❌ Có lỗi cần sửa (xem trên).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
