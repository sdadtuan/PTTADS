"""Domain event outbox (PostgreSQL)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_jobs.db import PgUnavailableError, json_dumps, pg_connection

logger = logging.getLogger(__name__)


def emit_domain_event(
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> str | None:
    from ptt_jobs.events_catalog import build_event_idempotency_key

    idem = idempotency_key or build_event_idempotency_key(event_type, payload)
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                if idem:
                    cur.execute(
                        """
                        INSERT INTO domain_events (
                            event_type, aggregate_type, aggregate_id,
                            payload, correlation_id, idempotency_key
                        )
                        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                        ON CONFLICT (idempotency_key) WHERE (idempotency_key IS NOT NULL) DO NOTHING
                        RETURNING id
                        """,
                        (
                            event_type,
                            aggregate_type,
                            aggregate_id,
                            json_dumps(payload),
                            correlation_id,
                            idem,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO domain_events (
                            event_type, aggregate_type, aggregate_id, payload, correlation_id
                        )
                        VALUES (%s, %s, %s, %s::jsonb, %s)
                        RETURNING id
                        """,
                        (
                            event_type,
                            aggregate_type,
                            aggregate_id,
                            json_dumps(payload),
                            correlation_id,
                        ),
                    )
                row = cur.fetchone()
                conn.commit()
                return str(row[0]) if row else None
    except PgUnavailableError:
        logger.warning("domain event skipped (PG unavailable): %s", event_type)
        return None
    except Exception as exc:
        logger.exception("domain event failed: %s", exc)
        return None
