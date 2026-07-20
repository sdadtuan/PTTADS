"""SERP capture — stub, SerpAPI, or DataForSEO (Gate C P3)."""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _stub_results(phrase: str, *, domain_hint: str = "") -> list[dict[str, Any]]:
    base = domain_hint or "example.com"
    return [
        {"position": 1, "title": f"{phrase} — Top result", "url": f"https://{base}/", "snippet": "Stub SERP #1"},
        {"position": 2, "title": f"Guide: {phrase}", "url": "https://competitor-a.com/p", "snippet": "Stub SERP #2"},
        {"position": 3, "title": f"{phrase} FAQ", "url": "https://competitor-b.com/faq", "snippet": "Stub SERP #3"},
    ]


def serp_provider() -> str:
    """Active provider: stub | serpapi | dataforseo."""
    return (os.environ.get("PTT_SERP_PROVIDER") or "stub").strip().lower()


def serpapi_configured() -> bool:
    return bool((os.environ.get("SERPAPI_API_KEY") or os.environ.get("PTT_SERPAPI_API_KEY") or "").strip())


def dataforseo_configured() -> bool:
    login = (os.environ.get("DATAFORSEO_LOGIN") or os.environ.get("PTT_DATAFORSEO_LOGIN") or "").strip()
    password = (os.environ.get("DATAFORSEO_PASSWORD") or os.environ.get("PTT_DATAFORSEO_PASSWORD") or "").strip()
    return bool(login and password)


def effective_provider() -> str:
    """Resolve configured provider; fall back to stub when keys missing."""
    provider = serp_provider()
    if provider == "serpapi" and serpapi_configured():
        return "serpapi"
    if provider == "dataforseo" and dataforseo_configured():
        return "dataforseo"
    return "stub"


def _normalize_results(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, row in enumerate(raw[:20], start=1):
        out.append(
            {
                "position": int(row.get("position") or i),
                "title": str(row.get("title") or ""),
                "url": str(row.get("url") or row.get("link") or ""),
                "snippet": str(row.get("snippet") or row.get("description") or ""),
            }
        )
    return out


def fetch_serp_results(
    phrase: str,
    *,
    domain_hint: str = "",
    location: str = "Vietnam",
    language: str = "vi",
) -> tuple[list[dict[str, Any]], str]:
    """Fetch organic SERP results. Returns (results, source)."""
    provider = effective_provider()
    if provider == "serpapi":
        return _fetch_serpapi(phrase, location=location, language=language), "serpapi"
    if provider == "dataforseo":
        return _fetch_dataforseo(phrase, location=location, language=language), "dataforseo"
    return _stub_results(phrase, domain_hint=domain_hint), "stub"


def _fetch_serpapi(phrase: str, *, location: str, language: str) -> list[dict[str, Any]]:
    api_key = (os.environ.get("SERPAPI_API_KEY") or os.environ.get("PTT_SERPAPI_API_KEY") or "").strip()
    params = urllib.parse.urlencode(
        {
            "engine": "google",
            "q": phrase,
            "api_key": api_key,
            "gl": "vn" if "vietnam" in location.lower() else "us",
            "hl": language[:2] if language else "vi",
            "num": "10",
        }
    )
    url = f"https://serpapi.com/search.json?{params}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise ValueError(f"SerpAPI HTTP {exc.code}: {body[:200]}") from exc
    organic = data.get("organic_results") or []
    return _normalize_results(organic)


def _fetch_dataforseo(phrase: str, *, location: str, language: str) -> list[dict[str, Any]]:
    login = (os.environ.get("DATAFORSEO_LOGIN") or os.environ.get("PTT_DATAFORSEO_LOGIN") or "").strip()
    password = (os.environ.get("DATAFORSEO_PASSWORD") or os.environ.get("PTT_DATAFORSEO_PASSWORD") or "").strip()
    cred = base64.b64encode(f"{login}:{password}".encode()).decode()
    payload = json.dumps(
        [
            {
                "keyword": phrase,
                "location_name": location or "Vietnam",
                "language_code": (language or "vi")[:2],
                "device": "desktop",
                "depth": 10,
            }
        ]
    ).encode()
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise ValueError(f"DataForSEO HTTP {exc.code}: {body[:200]}") from exc
    tasks = data.get("tasks") or []
    if not tasks:
        raise ValueError("DataForSEO: empty tasks response")
    task = tasks[0]
    if task.get("status_code") not in (20000, None) and task.get("status_message"):
        raise ValueError(f"DataForSEO: {task.get('status_message')}")
    results = (task.get("result") or [{}])[0].get("items") or []
    organic = [
        {
            "position": item.get("rank_absolute") or item.get("rank_group"),
            "title": (item.get("title") or ""),
            "url": (item.get("url") or ""),
            "snippet": (item.get("description") or ""),
        }
        for item in results
        if isinstance(item, dict) and item.get("type") in (None, "organic")
    ]
    if not organic:
        organic = [
            {
                "position": item.get("rank_absolute") or item.get("rank_group"),
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": item.get("description") or "",
            }
            for item in results
            if isinstance(item, dict) and item.get("url")
        ]
    return _normalize_results(organic)


def capture_serp_snapshot(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    phrase: str,
    keyword_id: int | None = None,
    domain_hint: str = "",
    snapshot_date: str | None = None,
    location: str = "Vietnam",
    language: str = "vi",
) -> dict[str, Any]:
    phrase = phrase.strip()
    if not phrase:
        raise ValueError("Thiếu phrase")
    snap = snapshot_date or date.today().isoformat()
    results, source = fetch_serp_results(
        phrase,
        domain_hint=domain_hint,
        location=location,
        language=language,
    )
    cur = conn.execute(
        """
        INSERT INTO seo_serp_snapshots (
            customer_id, keyword_id, phrase, snapshot_date, results_json, source, created_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            keyword_id,
            phrase,
            snap,
            json.dumps(results, ensure_ascii=False),
            source,
            _ts(),
        ),
    )
    conn.commit()
    return {
        "id": int(cur.lastrowid),
        "phrase": phrase,
        "snapshot_date": snap,
        "results": results,
        "source": source,
        "provider_configured": effective_provider(),
    }


def list_serp_snapshots(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM seo_serp_snapshots
        WHERE customer_id = ?
        ORDER BY snapshot_date DESC, id DESC
        LIMIT ?
        """,
        (customer_id, limit),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        try:
            item["results"] = json.loads(item.pop("results_json", "[]") or "[]")
        except json.JSONDecodeError:
            item["results"] = []
        out.append(item)
    return out
