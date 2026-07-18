"""Unified channel webhook API (v1)."""
from __future__ import annotations

import logging
import uuid

from flask import Blueprint, Response, jsonify, request

from ptt_channel.ingress import parse_channel_webhook, supported_channels
from ptt_channel.registry import get_default_registry

logger = logging.getLogger(__name__)

bp = Blueprint("channel_webhooks", __name__, url_prefix="/api/v1")


@bp.get("/channels")
def api_list_channels():
    reg = get_default_registry()
    return jsonify(
        {
            "channels": supported_channels(reg),
            "capabilities": {k: v.to_dict() for k, v in reg.list_capabilities().items()},
        }
    )


@bp.get("/webhooks/<channel>")
@bp.post("/webhooks/<channel>")
def api_channel_webhook(channel: str):
    headers = {k: v for k, v in request.headers.items()}
    raw = request.get_data(cache=True) or b""
    query = {k: v for k, v in request.args.items()}
    client_id = str(request.headers.get("X-PTT-Client-Id") or query.get("client_id") or "")
    correlation_id = str(request.headers.get("X-Correlation-Id") or uuid.uuid4())

    out = parse_channel_webhook(channel, headers, raw, query, client_id=client_id)

    if "challenge" in out:
        return Response(str(out["challenge"]), mimetype="text/plain")

    if not out.get("verified"):
        return jsonify(out), 401

    leads = out.get("leads") or []
    response_body: dict = {
        "verified": True,
        "channel": out.get("channel", channel),
        "correlation_id": correlation_id,
        "lead_count": len(leads),
        "events": out.get("events") or [],
    }

    if not leads:
        return jsonify(response_body)

    try:
        from ptt_jobs.enqueue import enqueue_ingest_leads

        enqueue_result = enqueue_ingest_leads(
            leads,
            channel=str(out.get("channel") or channel),
            correlation_id=correlation_id,
            client_id=client_id,
        )
        response_body["mode"] = enqueue_result.get("mode")
        response_body["accepted"] = True
        if enqueue_result.get("jobs"):
            response_body["job_ids"] = [j["id"] for j in enqueue_result["jobs"]]
            response_body["jobs"] = enqueue_result["jobs"]
        if enqueue_result.get("ingest"):
            response_body["ingest"] = enqueue_result["ingest"]
        logger.info(
            "webhook v1 channel=%s mode=%s leads=%d correlation_id=%s",
            channel,
            enqueue_result.get("mode"),
            len(leads),
            correlation_id,
            extra={"correlation_id": correlation_id, "channel": channel},
        )
    except Exception as exc:
        logger.exception("webhook enqueue failed correlation_id=%s: %s", correlation_id, exc)
        return jsonify({"verified": True, "accepted": False, "error": str(exc)}), 500

    return jsonify(response_body)
