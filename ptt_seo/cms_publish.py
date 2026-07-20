"""CMS publish connector — webhook stub + job queue."""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from ptt_seo.content import get_content


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def cms_auto_publish_enabled() -> bool:
    return os.getenv("PTT_SEO_CMS_AUTO_PUBLISH", "0").strip().lower() in ("1", "true", "yes")


def maybe_auto_publish(conn: sqlite3.Connection, content_id: int) -> dict[str, Any] | None:
    """Queue CMS publish when content reaches published (Gate E5)."""
    if not cms_auto_publish_enabled():
        return None
    content = get_content(conn, content_id)
    if content is None:
        return None
    target = get_cms_target(conn, int(content["customer_id"]))
    if target is None or not target.get("active", True):
        return None
    try:
        return queue_publish(conn, content_id)
    except ValueError:
        return None


def get_cms_target(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM seo_cms_targets WHERE customer_id = ?", (customer_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    try:
        d["auth"] = json.loads(d.pop("auth_json", "{}") or "{}")
    except json.JSONDecodeError:
        d["auth"] = {}
    return d


def upsert_cms_target(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    auth = payload.get("auth") or {}
    conn.execute(
        """
        INSERT INTO seo_cms_targets (customer_id, cms_type, base_url, auth_json, active, updated_at)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(customer_id) DO UPDATE SET
            cms_type = excluded.cms_type,
            base_url = excluded.base_url,
            auth_json = excluded.auth_json,
            active = excluded.active,
            updated_at = excluded.updated_at
        """,
        (
            customer_id,
            str(payload.get("cms_type") or "webhook"),
            str(payload.get("base_url") or ""),
            json.dumps(auth, ensure_ascii=False),
            1 if payload.get("active", True) else 0,
            _ts(),
        ),
    )
    conn.commit()
    result = get_cms_target(conn, customer_id)
    assert result is not None
    return result


def list_publish_jobs(
    conn: sqlite3.Connection,
    customer_id: int | None = None,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_cms_publish_jobs WHERE 1=1"
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for row in rows:
        for key in ("payload_json", "response_json"):
            try:
                row[key.replace("_json", "")] = json.loads(row.pop(key, "{}") or "{}")
            except json.JSONDecodeError:
                row[key.replace("_json", "")] = {}
    return rows


def _build_payload(content: dict[str, Any]) -> dict[str, Any]:
    brief = content.get("brief") or {}
    outline = content.get("outline") or {}
    return {
        "event": "seo.content.publish",
        "title": content.get("title"),
        "slug": content.get("slug"),
        "content_type": content.get("content_type"),
        "body_html": content.get("body_html"),
        "meta_title": brief.get("meta_title") or content.get("title"),
        "meta_description": brief.get("meta_description") or "",
        "target_keyword": brief.get("target_keyword") or "",
        "schema_json": outline.get("schema_json") or outline.get("schema") or "",
        "publish_date": content.get("publish_date") or _ts()[:10],
        "content_id": content.get("id"),
        "customer_id": content.get("customer_id"),
    }


def build_test_payload(*, customer_id: int, title: str = "CMS Pilot Test") -> dict[str, Any]:
    slug = "cms-pilot-test-" + _ts().replace(":", "").replace(" ", "-")
    return {
        "event": "seo.content.publish.test",
        "title": title,
        "slug": slug,
        "content_type": "blog",
        "body_html": "<p>CMS webhook pilot ping from PTTADS SEO/AEO.</p>",
        "meta_title": title,
        "meta_description": "Pilot webhook connectivity test",
        "publish_date": _ts()[:10],
        "customer_id": customer_id,
    }


def _auth_headers(auth: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    token = auth.get("bearer_token") or auth.get("api_key")
    if token:
        prefix = str(auth.get("auth_prefix") or "Bearer").strip()
        headers["Authorization"] = f"{prefix} {token}".strip() if prefix else str(token)
    header_name = str(auth.get("header_name") or "").strip()
    header_value = str(auth.get("header_value") or "").strip()
    if header_name and header_value:
        headers[header_name] = header_value
    secret = (os.environ.get("PTT_SEO_CMS_WEBHOOK_SECRET") or "").strip()
    if secret and auth.get("send_pilot_secret_header"):
        headers["X-PTT-CMS-Secret"] = secret
    return headers


def _dispatch_webhook(target: dict[str, Any], payload: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    url = (target.get("base_url") or "").strip()
    if not url:
        return "failed", {}, "CMS base_url chưa cấu hình"
    auth = target.get("auth") or {}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PTTADS-SEO-CMS/1.0",
        **_auth_headers(auth),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                data = {"raw": raw[:2000]}
            remote = str(data.get("url") or data.get("permalink") or "")
            return "published", data, remote
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:500]
        return "failed", {"status": exc.code, "body": err_body}, ""
    except Exception as exc:
        return "failed", {}, str(exc)


def queue_publish(conn: sqlite3.Connection, content_id: int, *, dry_run: bool = False) -> dict[str, Any]:
    content = get_content(conn, content_id)
    if content is None:
        raise ValueError("Content không tồn tại")
    customer_id = int(content["customer_id"])
    target = get_cms_target(conn, customer_id)
    cms_type = (target or {}).get("cms_type") or "webhook"
    payload = _build_payload(content)
    cur = conn.execute(
        """
        INSERT INTO seo_cms_publish_jobs (
            customer_id, content_id, cms_type, status, payload_json, created_at
        ) VALUES (?,?,?,?,?,?)
        """,
        (customer_id, content_id, cms_type, "pending", json.dumps(payload, ensure_ascii=False), _ts()),
    )
    conn.commit()
    job_id = int(cur.lastrowid)
    if dry_run or target is None or not target.get("active", True):
        status = "sent" if dry_run else ("pending" if target is None else "sent")
        msg = "Dry-run — payload queued, không gửi webhook" if dry_run else "Chưa cấu hình CMS target"
        if dry_run and target is not None:
            msg = "Dry-run — payload sẵn sàng gửi tới " + str(target.get("base_url") or "")
        conn.execute(
            """
            UPDATE seo_cms_publish_jobs SET status = ?, error_message = ?, finished_at = ?,
                payload_json = ?
            WHERE id = ?
            """,
            (status, msg, _ts(), json.dumps(payload, ensure_ascii=False), job_id),
        )
        conn.commit()
        return {
            "job_id": job_id,
            "status": status,
            "dry_run": dry_run,
            "message": msg,
            "payload": payload,
        }

    pub_status, response, remote_url = _dispatch_webhook(target, payload)
    conn.execute(
        """
        UPDATE seo_cms_publish_jobs SET
            status = ?, response_json = ?, remote_url = ?, error_message = ?, finished_at = ?
        WHERE id = ?
        """,
        (
            pub_status,
            json.dumps(response, ensure_ascii=False),
            remote_url,
            "" if pub_status == "published" else str(response.get("body") or response),
            _ts(),
            job_id,
        ),
    )
    if pub_status == "published":
        conn.execute(
            "UPDATE seo_content SET publish_date = ?, updated_at = ? WHERE id = ?",
            (_ts()[:10], _ts(), content_id),
        )
    conn.commit()
    return {
        "job_id": job_id,
        "status": pub_status,
        "remote_url": remote_url,
        "response": response,
    }


def test_cms_webhook(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    target = get_cms_target(conn, customer_id)
    if target is None or not (target.get("base_url") or "").strip():
        raise ValueError("Chưa cấu hình CMS webhook URL cho client này")
    payload = build_test_payload(customer_id=customer_id)
    status, response, remote_url = _dispatch_webhook(target, payload)
    return {
        "ok": status == "published",
        "status": status,
        "remote_url": remote_url,
        "response": response,
        "webhook_url": target.get("base_url"),
    }
