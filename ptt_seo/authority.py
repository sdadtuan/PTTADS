"""Authority & trust — backlinks, citations, mentions (Phase 4C)."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

SIGNAL_TYPES = frozenset({"backlink", "citation", "brand_mention", "pr"})

_SOURCE_URL_KEYS = (
    "referring page url",
    "referring url",
    "source url",
    "source page",
    "from url",
    "url",
)
_TARGET_URL_KEYS = (
    "target url",
    "destination url",
    "to url",
    "landing page",
)
_ANCHOR_KEYS = ("anchor", "anchor text", "link anchor")
_DR_KEYS = ("domain rating", "dr", "domain rank", "authority score")
_DOMAIN_KEYS = ("referring domains", "source domain", "domain", "referring domain")
_STATUS_KEYS = ("status", "link type", "type")


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return date.today().isoformat()


def _norm_key(key: str) -> str:
    return " ".join(str(key or "").strip().lower().replace("_", " ").split())


def _pick(row: dict[str, str], keys: tuple[str, ...]) -> str:
    normalized = {_norm_key(k): v for k, v in row.items()}
    for key in keys:
        val = normalized.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.netloc or parsed.path.split("/")[0] or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _parse_dr(raw: str) -> float | None:
    text = str(raw or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _infer_status(raw: str) -> str:
    text = str(raw or "").strip().lower()
    if text in ("lost", "removed", "broken", "inactive"):
        return "lost"
    if text in ("pending", "new"):
        return "pending"
    return "active"


def list_signals(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    signal_type: str | None = None,
    status: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_authority_signals WHERE customer_id = ?"
    params: list[Any] = [customer_id]
    if signal_type:
        sql += " AND signal_type = ?"
        params.append(signal_type)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY last_seen_at DESC, id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def authority_summary(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT signal_type, status, COUNT(*) AS c, AVG(domain_rating) AS avg_dr
        FROM seo_authority_signals
        WHERE customer_id = ?
        GROUP BY signal_type, status
        """,
        (customer_id,),
    ).fetchall()
    summary: dict[str, Any] = {
        "backlinks_active": 0,
        "backlinks_lost": 0,
        "citations": 0,
        "brand_mentions": 0,
        "pr_signals": 0,
        "avg_dr": 0.0,
    }
    dr_sum = 0.0
    dr_count = 0
    for row in rows:
        st = str(row["signal_type"] or "")
        status = str(row["status"] or "")
        count = int(row["c"] or 0)
        avg_dr = row["avg_dr"]
        if avg_dr is not None:
            dr_sum += float(avg_dr) * count
            dr_count += count
        if st == "backlink":
            if status == "lost":
                summary["backlinks_lost"] += count
            else:
                summary["backlinks_active"] += count
        elif st == "citation":
            summary["citations"] += count
        elif st == "brand_mention":
            summary["brand_mentions"] += count
        elif st == "pr":
            summary["pr_signals"] += count
    summary["avg_dr"] = round(dr_sum / dr_count, 2) if dr_count else 0.0
    summary["total_signals"] = sum(
        int(summary[k])
        for k in ("backlinks_active", "backlinks_lost", "citations", "brand_mentions", "pr_signals")
    )
    return summary


def import_signals_csv(
    conn: sqlite3.Connection,
    customer_id: int,
    csv_text: str,
    *,
    signal_type: str = "backlink",
) -> dict[str, Any]:
    """Import Ahrefs/Semrush-style backlink or citation CSV."""
    stype = str(signal_type or "backlink").strip().lower()
    if stype not in SIGNAL_TYPES:
        return {"ok": False, "error": f"invalid_signal_type:{stype}"}

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        return {"ok": False, "error": "empty_csv"}

    today = _today()
    imported = 0
    skipped = 0
    for row in reader:
        source_url = _pick(row, _SOURCE_URL_KEYS)
        target_url = _pick(row, _TARGET_URL_KEYS)
        if not source_url and not target_url:
            skipped += 1
            continue
        source_domain = _pick(row, _DOMAIN_KEYS) or _domain_from_url(source_url)
        anchor = _pick(row, _ANCHOR_KEYS)
        dr = _parse_dr(_pick(row, _DR_KEYS))
        status = _infer_status(_pick(row, _STATUS_KEYS))

        conn.execute(
            """
            INSERT INTO seo_authority_signals (
                customer_id, signal_type, source_domain, source_url, target_url,
                anchor_text, domain_rating, status, first_seen_at, last_seen_at,
                notes, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(customer_id, signal_type, source_url, target_url) DO UPDATE SET
                source_domain=excluded.source_domain,
                anchor_text=excluded.anchor_text,
                domain_rating=COALESCE(excluded.domain_rating, seo_authority_signals.domain_rating),
                status=excluded.status,
                first_seen_at=COALESCE(seo_authority_signals.first_seen_at, excluded.first_seen_at),
                last_seen_at=excluded.last_seen_at
            """,
            (
                customer_id,
                stype,
                source_domain,
                source_url,
                target_url,
                anchor,
                dr,
                status,
                today,
                today,
                "",
                _ts(),
            ),
        )
        imported += 1
    conn.commit()
    return {
        "ok": True,
        "signal_type": stype,
        "rows_imported": imported,
        "rows_skipped": skipped,
    }
