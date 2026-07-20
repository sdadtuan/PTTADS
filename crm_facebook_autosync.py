"""Tự động kéo lead Facebook mới — polling nền + retry webhook pending."""
from __future__ import annotations

import fcntl
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_LOCK_PATH = Path(os.getenv("CRM_FACEBOOK_AUTOSYNC_LOCK", "/tmp/ptt_fb_autosync.lock"))
_PENDING_LOCK_PATH = Path(os.getenv("CRM_FACEBOOK_PENDING_LOCK", "/tmp/ptt_fb_pending.lock"))
_worker_started = False
_PENDING_INTERVAL_SEC = 8.0


def _lock_path(path: Path) -> Path:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def _try_file_lock(path: Path) -> tuple[Any | None, bool]:
    """Thử khóa file không chặn — chỉ một worker Gunicorn chạy mỗi lần."""
    try:
        fh = open(_lock_path(path), "w")
    except OSError:
        return None, False
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None, False
    return fh, True


def _release_file_lock(fh: Any | None) -> None:
    if fh is None:
        return
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        fh.close()
    except OSError:
        pass


def _crm_ts() -> str:
    from ptt_crm.crm_sqlite import crm_ts

    return crm_ts()


def _crm_conn():
    from ptt_crm.crm_sqlite import crm_connection

    return crm_connection()


def run_facebook_pending_once() -> dict[str, Any]:
    """Retry hàng đợi webhook — chạy cả khi auto_sync Graph tắt."""
    from crm_facebook_config import fetch_facebook_config
    from crm_facebook_pending import process_pending_facebook_leads

    fh, locked = _try_file_lock(_PENDING_LOCK_PATH)
    if not locked:
        return {
            "ok": True,
            "skipped": True,
            "message": "Pending retry đang chạy ở worker khác.",
            "created_count": 0,
        }
    try:
        with _crm_conn() as conn:
            fb_cfg = fetch_facebook_config(conn)
            if not fb_cfg.get("enabled"):
                return {
                    "ok": True,
                    "skipped": True,
                    "message": "Facebook Lead chưa bật.",
                    "created_count": 0,
                }
            if not fb_cfg.get("webhook_enabled", True):
                return {
                    "ok": True,
                    "skipped": True,
                    "message": "Webhook Facebook đã tắt.",
                    "created_count": 0,
                }
            result = process_pending_facebook_leads(
                conn,
                created_by="autosync:pending",
                ts=_crm_ts(),
                max_items=10,
            )
            conn.commit()
            return {
                "ok": True,
                "created_count": int(result.get("created_count") or 0),
                "processed": int(result.get("processed") or 0),
                "pending": result,
            }
    except Exception as exc:
        _log.exception("Facebook pending retry failed")
        return {
            "ok": False,
            "message": str(exc) or "Facebook pending retry failed",
            "created_count": 0,
        }
    finally:
        _release_file_lock(fh)


def run_facebook_autosync_once() -> dict[str, Any]:
    """Chạy một vòng đồng bộ Graph nếu Facebook Lead + auto_sync đang bật."""
    from crm_facebook_config import fetch_facebook_config
    from crm_facebook_leads import run_facebook_ingest_cycle

    fh, locked = _try_file_lock(_LOCK_PATH)
    if not locked:
        return {
            "ok": True,
            "skipped": True,
            "message": "Sync đang chạy ở worker khác (file lock).",
            "created_count": 0,
        }
    try:
        with _crm_conn() as conn:
            fb_cfg = fetch_facebook_config(conn)
            if not fb_cfg.get("enabled"):
                return {
                    "ok": True,
                    "skipped": True,
                    "message": "Facebook Lead chưa bật trong CRM → Leads → Cấu hình.",
                    "created_count": 0,
                }
            if not fb_cfg.get("auto_sync", True):
                return {
                    "ok": True,
                    "skipped": True,
                    "message": "Tự động đồng bộ Graph đã tắt (webhook vẫn hoạt động).",
                    "created_count": 0,
                }
            return run_facebook_ingest_cycle(
                conn,
                created_by="autosync:facebook",
                ts=_crm_ts(),
                recent_only=True,
            )
    except Exception as exc:
        _log.exception("Facebook autosync failed")
        return {
            "ok": False,
            "message": str(exc) or "Facebook autosync failed",
            "created_count": 0,
        }
    finally:
        _release_file_lock(fh)


def _autosync_sleep_seconds() -> float:
    from crm_facebook_config import fetch_facebook_config

    try:
        with _crm_conn() as conn:
            fb_cfg = fetch_facebook_config(conn)
    except Exception:
        fb_cfg = {}
    if not fb_cfg.get("enabled") or not fb_cfg.get("auto_sync", True):
        return 60.0
    try:
        mins = int(fb_cfg.get("sync_interval_minutes") or 5)
    except (TypeError, ValueError):
        mins = 5
    mins = max(5, min(60, mins))
    return float(mins * 60)


def _background_worker_loop() -> None:
    time.sleep(5.0)
    next_pending = time.time()
    next_sync = time.time()
    while True:
        now = time.time()
        if now >= next_pending:
            try:
                run_facebook_pending_once()
            except Exception:
                _log.exception("Facebook pending loop error")
            next_pending = now + _PENDING_INTERVAL_SEC
        if now >= next_sync:
            try:
                run_facebook_autosync_once()
            except Exception:
                _log.exception("Facebook autosync loop error")
            next_sync = now + _autosync_sleep_seconds()
        time.sleep(2.0)


def start_facebook_autosync_worker(app: Any) -> None:
    """Khởi động thread nền (daemon) — pending webhook + optional Graph poll."""
    global _worker_started
    if _worker_started:
        return
    if os.getenv("CRM_FACEBOOK_BACKGROUND", "1").strip().lower() in ("0", "false", "no", "off"):
        return
    from ptt_crm.config import facebook_background_in_gunicorn

    if not facebook_background_in_gunicorn():
        return
    _worker_started = True

    def _runner() -> None:
        with app.app_context():
            _background_worker_loop()

    t = threading.Thread(target=_runner, name="ptt-fb-background", daemon=True)
    t.start()
    _log.info("Facebook background worker started (pending=%ss)", _PENDING_INTERVAL_SEC)


def run_facebook_background_daemon() -> None:
    """Blocking loop for standalone systemd service (Sprint 0 — outside Gunicorn)."""
    _log.info("Facebook background daemon starting (pending=%ss)", _PENDING_INTERVAL_SEC)
    _background_worker_loop()
