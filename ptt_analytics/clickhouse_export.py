"""Export PG domain_events → ClickHouse (Phase 4 F4)."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def _clickhouse_endpoint() -> tuple[str, str | None, str | None]:
    """Return (base_http_url, user, password)."""
    env_user = (os.environ.get("CLICKHOUSE_USER") or "").strip() or None
    env_password = (os.environ.get("CLICKHOUSE_PASSWORD") or "").strip() or None

    raw = (os.environ.get("CLICKHOUSE_URL") or "").strip()
    if raw:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8123
        scheme = parsed.scheme or "http"
        user = parsed.username or env_user
        password = parsed.password if parsed.password is not None else env_password
        return f"{scheme}://{host}:{port}", user, password

    host = (os.environ.get("CLICKHOUSE_HOST") or "127.0.0.1:8123").strip()
    if "://" not in host:
        host = f"http://{host}"
    return host.rstrip("/"), env_user or "ptt", env_password or "ptt_dev"


def clickhouse_url() -> str:
    base, user, password = _clickhouse_endpoint()
    if user and password:
        parsed = urllib.parse.urlparse(base)
        return f"{parsed.scheme}://{user}:{password}@{parsed.netloc}"
    return base


def _auth_header() -> dict[str, str]:
    _, user, password = _clickhouse_endpoint()
    if not user:
        return {}
    token = base64.b64encode(f"{user}:{password or ''}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _ch_request(
    query: str,
    *,
    data: bytes | None = None,
    method: str = "GET",
    timeout: float = 30,
) -> bytes:
    base, _, _ = _clickhouse_endpoint()
    headers = _auth_header()
    if data is not None:
        url = f"{base}/?query={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
    elif method.upper() == "POST":
        url = f"{base}/"
        req = urllib.request.Request(url, data=query.encode("utf-8"), method="POST")
    else:
        url = f"{base}/?query={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, method="GET")
    for key, value in headers.items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_since(raw: str | None) -> datetime:
    if raw:
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=1)


def _client_id_from_correlation(correlation_id: str | None) -> str | None:
    if correlation_id and _UUID_RE.match(correlation_id.strip()):
        return correlation_id.strip()
    return None


def fetch_domain_events(*, since: datetime, limit: int = 50_000) -> list[dict[str, Any]]:
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, event_type, aggregate_type, aggregate_id,
                       payload::text, COALESCE(idempotency_key, ''), correlation_id,
                       created_at
                FROM domain_events
                WHERE created_at >= %s::timestamptz
                ORDER BY created_at
                LIMIT %s
                """,
                (since, limit),
            )
            rows = cur.fetchall()

    out: list[dict[str, Any]] = []
    for eid, etype, atype, aid, payload, idem, corr, created_at in rows:
        ts = created_at
        if hasattr(ts, "astimezone"):
            ts = ts.astimezone(timezone.utc)
        client_id = _client_id_from_correlation(corr)
        out.append(
            {
                "event_id": eid,
                "event_type": etype,
                "aggregate_type": atype,
                "aggregate_id": aid,
                "client_id": client_id,
                "payload": payload or "{}",
                "idempotency_key": idem or "",
                "created_at": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            }
        )
    return out


def clickhouse_ping() -> bool:
    try:
        return _ch_request("SELECT 1", timeout=5).decode().strip() == "1"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.debug("clickhouse_ping failed: %s", exc)
        return False


def clickhouse_init_schema(*, ddl_path: str | None = None) -> dict[str, Any]:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = Path(ddl_path) if ddl_path else root / "deploy/clickhouse/init-domain-events.sql"
    sql = path.read_text(encoding="utf-8")
    applied: list[str] = []
    for stmt in sql.split(";"):
        chunk = stmt.strip()
        if not chunk:
            continue
        lines = [ln for ln in chunk.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        if not lines:
            continue
        sql_chunk = "\n".join(lines)
        _ch_request(sql_chunk, method="POST")
        applied.append(lines[0][:80])
    return {"ok": True, "statements": len(applied)}


def export_to_clickhouse(
    *,
    since: str | None = None,
    limit: int = 50_000,
) -> dict[str, Any]:
    since_dt = _parse_since(since)
    rows = fetch_domain_events(since=since_dt, limit=limit)
    if not rows:
        return {"ok": True, "exported": 0, "since": since_dt.isoformat()}

    lines = []
    for row in rows:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        lines.append(
            json.dumps(
                {
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "aggregate_type": row["aggregate_type"],
                    "aggregate_id": row["aggregate_id"],
                    "client_id": row["client_id"],
                    "payload": json.dumps(payload, ensure_ascii=False),
                    "idempotency_key": row["idempotency_key"],
                    "created_at": row["created_at"],
                },
                ensure_ascii=False,
            )
        )
    body = "\n".join(lines).encode("utf-8")
    _ch_request("INSERT INTO ptt.domain_events FORMAT JSONEachRow", data=body, method="POST", timeout=120)

    return {
        "ok": True,
        "exported": len(rows),
        "since": since_dt.isoformat(),
    }


def clickhouse_count() -> int:
    raw = _ch_request("SELECT count() FROM ptt.domain_events", method="POST", timeout=10).decode().strip()
    return int(raw)


def seed_test_domain_event(*, client_id: str | None = None) -> str:
    """Insert one domain event for export smoke tests."""
    from ptt_jobs.db import pg_connection

    eid = str(uuid.uuid4())
    cid = client_id or "550e8400-e29b-41d4-a716-446655440000"
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO domain_events (
                  id, event_type, aggregate_type, aggregate_id, payload, correlation_id, idempotency_key
                ) VALUES (
                  %s::uuid, 'ClickHouseExportSmoke', 'test', %s, '{}'::jsonb, %s, %s
                )
                ON CONFLICT (idempotency_key) WHERE (idempotency_key IS NOT NULL) DO NOTHING
                RETURNING id::text
                """,
                (eid, eid, cid, f"clickhouse-smoke:{eid}"),
            )
            row = cur.fetchone()
        conn.commit()
    return str(row[0]) if row else eid
