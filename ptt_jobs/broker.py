"""Message broker — RabbitMQ optional; PG queue remains source of truth."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_jobs.config import event_publish_rmq_enabled, rabbitmq_url

logger = logging.getLogger(__name__)

_JOBS_EXCHANGE = "ptt.jobs"
_EVENTS_EXCHANGE = "ptt.events"


def _connect():
    import pika

    params = pika.URLParameters(rabbitmq_url())
    return pika.BlockingConnection(params)


def notify_job_enqueued(*, job_id: str, job_type: str, correlation_id: str | None = None) -> bool:
    """Lightweight wake signal for workers (optional)."""
    if not event_publish_rmq_enabled():
        return False
    try:
        import pika
    except ImportError:
        logger.debug("pika not installed — skip job notify")
        return False
    try:
        body = json.dumps(
            {"job_id": job_id, "job_type": job_type, "correlation_id": correlation_id},
            ensure_ascii=False,
        )
        with _connect() as conn:
            ch = conn.channel()
            ch.exchange_declare(exchange=_JOBS_EXCHANGE, exchange_type="direct", durable=True)
            ch.basic_publish(
                exchange=_JOBS_EXCHANGE,
                routing_key=job_type,
                body=body.encode("utf-8"),
                properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            )
        return True
    except Exception as exc:
        logger.warning("RMQ job notify failed: %s", exc)
        return False


def publish_domain_event_message(event: dict[str, Any]) -> bool:
    """Publish one outbox row to ptt.events topic exchange."""
    if not event_publish_rmq_enabled():
        return False
    try:
        import pika
    except ImportError:
        logger.debug("pika not installed — skip event publish")
        return False
    event_type = str(event.get("event_type") or "unknown")
    routing_key = event_type
    envelope = {
        "id": event.get("id"),
        "event_type": event_type,
        "aggregate_type": event.get("aggregate_type"),
        "aggregate_id": event.get("aggregate_id"),
        "payload": event.get("payload") or {},
        "correlation_id": event.get("correlation_id"),
        "created_at": event.get("created_at"),
    }
    if isinstance(envelope["payload"], str):
        try:
            envelope["payload"] = json.loads(envelope["payload"])
        except json.JSONDecodeError:
            envelope["payload"] = {}
    try:
        body = json.dumps(envelope, ensure_ascii=False, default=str)
        with _connect() as conn:
            ch = conn.channel()
            ch.exchange_declare(exchange=_EVENTS_EXCHANGE, exchange_type="topic", durable=True)
            ch.basic_publish(
                exchange=_EVENTS_EXCHANGE,
                routing_key=routing_key,
                body=body.encode("utf-8"),
                properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            )
        return True
    except Exception as exc:
        logger.warning("RMQ event publish failed id=%s: %s", event.get("id"), exc)
        return False


def publish_pending_events(*, batch_size: int = 50) -> int:
    """Drain unpublished domain_events to RabbitMQ."""
    if not event_publish_rmq_enabled():
        return 0
    from ptt_jobs.events_store import fetch_unpublished_events, mark_event_published

    events = fetch_unpublished_events(limit=batch_size)
    published = 0
    for ev in events:
        if publish_domain_event_message(ev):
            if mark_event_published(str(ev["id"])):
                published += 1
    if published:
        logger.info("published %d domain event(s) to RMQ", published)
    return published
