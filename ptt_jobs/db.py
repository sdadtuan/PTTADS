"""PostgreSQL connection helpers."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from ptt_jobs.config import database_url

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore[assignment]


class PgUnavailableError(RuntimeError):
    pass


def pg_available() -> bool:
    if psycopg2 is None:
        return False
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as exc:
        logger.debug("PostgreSQL unavailable: %s", exc)
        return False


@contextmanager
def pg_connection() -> Iterator[Any]:
    if psycopg2 is None:
        raise PgUnavailableError("psycopg2 not installed")
    conn = psycopg2.connect(database_url())
    try:
        yield conn
    finally:
        conn.close()


def json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, default=str)
