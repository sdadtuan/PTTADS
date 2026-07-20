"""SQLite CRM connection — no Flask app dependency (Horizon 1 autosync standalone)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]


def db_path() -> Path:
    raw = (os.environ.get("PTT_DB_PATH") or os.environ.get("SQLITE_PATH") or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else ROOT / p
    return ROOT / "ptt.db"


def crm_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def crm_connection() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
