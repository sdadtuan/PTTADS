"""Gunicorn — khởi động autosync Facebook trong từng worker."""
from __future__ import annotations


def post_fork(server, worker):  # noqa: ARG001
    try:
        from app import app
        from crm_facebook_autosync import start_facebook_autosync_worker

        start_facebook_autosync_worker(app)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Facebook autosync post_fork failed")
