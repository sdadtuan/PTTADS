"""Temporal worker configuration."""
from __future__ import annotations

import os
from pathlib import Path


def temporal_address() -> str:
    return (
        os.environ.get("PTT_TEMPORAL_ADDRESS")
        or os.environ.get("TEMPORAL_ADDRESS")
        or "127.0.0.1:7233"
    ).strip()


def temporal_namespace() -> str:
    return (os.environ.get("PTT_TEMPORAL_NAMESPACE") or "default").strip()


def task_queue() -> str:
    return (os.environ.get("PTT_TEMPORAL_TASK_QUEUE") or "ptt-agency").strip()


def database_url() -> str:
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("PTT_DATABASE_URL")
        or "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency"
    ).strip()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
