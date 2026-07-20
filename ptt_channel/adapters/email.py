"""Email marketing channel adapter — SendGrid/Mailgun (EM-6)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from typing import Any
from urllib import error, request

from ptt_channel.base import ChannelAdapter
from ptt_channel.capabilities import AdapterCapabilities
from ptt_channel.context import AdapterContext
from ptt_channel.enums import ChannelCode, EventSource, StandardEventName
from ptt_channel.models import NormalizedEvent
from ptt_channel.results import CredentialValidationResult, WebhookParseResult

logger = logging.getLogger(__name__)


class EmailAdapter(ChannelAdapter):
    @property
    def channel(self) -> ChannelCode:
        return ChannelCode.EMAIL

    @property
    def display_name(self) -> str:
        return "Email Marketing (ESP)"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_webhooks=True,
            supports_server_events=False,
            supports_campaign_write=True,
            supports_lead_ingest=False,
            supports_daily_insights=True,
            supports_creative_upload=True,
            supports_audience_sync=True,
            max_insights_lookback_days=365,
        )

    def validate_credentials(self, ctx: AdapterContext, *, api_key: str | None = None) -> CredentialValidationResult:
        key = (api_key or "").strip()
        if not key:
            return CredentialValidationResult(valid=False, message="Missing ESP API key")
        if key.startswith("dry-"):
            return CredentialValidationResult(valid=True, message="dry-run key")
        try:
            req = request.Request(
                "https://api.sendgrid.com/v3/user/profile",
                headers={"Authorization": f"Bearer {key}"},
                method="GET",
            )
            with request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return CredentialValidationResult(valid=True, message="SendGrid OK")
        except error.HTTPError as exc:
            return CredentialValidationResult(valid=False, message=f"SendGrid HTTP {exc.code}")
        except Exception as exc:
            return CredentialValidationResult(valid=False, message=str(exc))
        return CredentialValidationResult(valid=False, message="SendGrid validation failed")

    def parse_webhook(
        self,
        headers: dict[str, str],
        raw_body: bytes,
        query: dict[str, str] | None = None,
        *,
        client_id: str = "",
    ) -> WebhookParseResult:
        from ptt_email.config import email_webhook_verify

        body_text = raw_body.decode("utf-8") if raw_body else "[]"
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError:
            return WebhookParseResult(verified=False, reject_reason="invalid_json")

        events = payload if isinstance(payload, list) else payload.get("events") or [payload]
        if email_webhook_verify():
            if not self._verify_sendgrid_signature(headers, raw_body):
                return WebhookParseResult(verified=False, reject_reason="signature_invalid")

        normalized: list[dict[str, Any]] = []
        for raw in events:
            if not isinstance(raw, dict):
                continue
            evt = dict(raw)
            if client_id:
                evt.setdefault("client_id", client_id)
            normalized.append(evt)

        return WebhookParseResult(verified=True, events=normalized)

    def normalize_event(self, raw: dict, source: str) -> NormalizedEvent | None:
        event_type = str(raw.get("event") or raw.get("type") or "").lower()
        name_map = {
            "open": StandardEventName.EMAIL_OPEN,
            "click": StandardEventName.EMAIL_CLICK,
            "unsubscribe": StandardEventName.UNSUBSCRIBE,
            "spamreport": StandardEventName.UNSUBSCRIBE,
        }
        mapped = name_map.get(event_type)
        if not mapped:
            return None
        return NormalizedEvent(
            event_id=str(raw.get("id") or raw.get("event_id") or uuid.uuid4()),
            event_name=mapped,
            occurred_at=str(raw.get("timestamp") or ""),
            source=EventSource.EMAIL,
            channel=ChannelCode.EMAIL,
            user={"email": str(raw.get("email") or "") or None},
            raw=raw,
        )

    def send_batch(
        self,
        ctx: AdapterContext,
        messages: list[dict[str, Any]],
        *,
        api_key: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        if dry_run or not (api_key or "").strip():
            for msg in messages:
                results.append(
                    {
                        "ok": True,
                        "send_id": msg.get("send_id"),
                        "esp_message_id": f"dry-{uuid.uuid4()}",
                        "mode": "dry_run",
                    }
                )
            return {"ok": True, "results": results, "mode": "dry_run"}

        for msg in messages:
            out = self._send_sendgrid(api_key or "", msg)
            out["send_id"] = msg.get("send_id")
            results.append(out)
        return {"ok": True, "results": results, "mode": "sendgrid"}

    def _send_sendgrid(self, api_key: str, msg: dict[str, Any]) -> dict[str, Any]:
        from_email = str(msg.get("from_email") or "noreply@example.com")
        from_name = str(msg.get("from_name") or "")
        unsub_url = str(msg.get("unsubscribe_url") or "").strip()
        headers: dict[str, str] = {}
        if unsub_url:
            headers["List-Unsubscribe"] = f"<{unsub_url}>"
            headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        payload = {
            "personalizations": [
                {
                    "to": [{"email": msg.get("to_email")}],
                    "custom_args": msg.get("custom_args") or {},
                }
            ],
            "from": {"email": from_email, "name": from_name} if from_name else {"email": from_email},
            "subject": str(msg.get("subject") or ""),
            "content": [
                {"type": "text/html", "value": str(msg.get("html_body") or "")},
            ],
            "reply_to": {"email": str(msg.get("reply_to") or from_email)},
            "tracking_settings": {"click_tracking": {"enable": True}, "open_tracking": {"enable": True}},
        }
        if headers:
            payload["headers"] = headers
        text_body = str(msg.get("text_body") or "").strip()
        if text_body:
            payload["content"].append({"type": "text/plain", "value": text_body})

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                msg_id = resp.headers.get("X-Message-Id") or f"sg-{uuid.uuid4()}"
                return {"ok": True, "esp_message_id": msg_id}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.warning("SendGrid send failed: %s %s", exc.code, body[:200])
            return {"ok": False, "error": f"sendgrid_http_{exc.code}", "detail": body[:500]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _verify_sendgrid_signature(self, headers: dict[str, str], raw_body: bytes) -> bool:
        import os

        public_key = (os.environ.get("SENDGRID_WEBHOOK_VERIFICATION_KEY") or "").strip()
        if not public_key:
            return False
        signature = str(headers.get("X-Twilio-Email-Event-Webhook-Signature") or headers.get("x-twilio-email-event-webhook-signature") or "")
        timestamp = str(headers.get("X-Twilio-Email-Event-Webhook-Timestamp") or headers.get("x-twilio-email-event-webhook-timestamp") or "")
        if not signature or not timestamp:
            return False
        signed = timestamp.encode() + raw_body
        digest = hmac.new(public_key.encode(), signed, hashlib.sha256).digest()
        import base64

        expected = base64.b64encode(digest).decode()
        return hmac.compare_digest(expected, signature)
