"""Research intelligence — keywords & questions (Spec 6.3 Phase 2)."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _opportunity_score(volume: int | None, difficulty: float | None, business_value: str) -> float:
    vol = max(0, int(volume or 0))
    diff = float(difficulty if difficulty is not None else 50.0)
    bv = {"low": 0.2, "medium": 0.5, "high": 0.8}.get(str(business_value or "medium"), 0.5)
    vol_norm = min(vol / 5000.0, 1.0)
    diff_inv = max(0.0, 1.0 - diff / 100.0)
    return round((vol_norm * 0.4 + diff_inv * 0.35 + bv * 0.25) * 100, 1)


def _has_cluster_table(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM seo_keyword_clusters LIMIT 1")
        return True
    except Exception:
        return False


def list_keywords(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    q: str | None = None,
    intent: str | None = None,
    cluster_id: int | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    has_clusters = _has_cluster_table(conn)
    if has_clusters:
        sql = """
            SELECT k.*, c.name AS cluster_name
            FROM seo_keywords k
            LEFT JOIN seo_keyword_clusters c
              ON c.id = k.cluster_id AND c.customer_id = k.customer_id AND c.status = 'active'
            WHERE k.customer_id = ? AND k.status = 'active'
        """
    else:
        sql = """
            SELECT k.*, NULL AS cluster_name
            FROM seo_keywords k
            WHERE k.customer_id = ? AND k.status = 'active'
        """
    params: list[Any] = [customer_id]
    if intent:
        sql += " AND k.intent = ?"
        params.append(intent)
    if cluster_id is not None:
        sql += " AND k.cluster_id = ?"
        params.append(cluster_id)
    if q:
        sql += " AND k.phrase LIKE ?"
        params.append(f"%{q}%")
    sql += " ORDER BY COALESCE(k.opportunity_score, 0) DESC, k.id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_keyword(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    phrase = str(payload.get("phrase") or "").strip()
    if not phrase:
        raise ValueError("Thiếu phrase")
    volume = payload.get("volume")
    difficulty = payload.get("difficulty")
    business_value = str(payload.get("business_value") or "medium")
    score = _opportunity_score(
        int(volume) if volume is not None else None,
        float(difficulty) if difficulty is not None else None,
        business_value,
    )
    cur = conn.execute(
        """
        INSERT INTO seo_keywords (
            customer_id, phrase, volume, difficulty, intent, business_value,
            opportunity_score, created_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            phrase,
            int(volume) if volume is not None else None,
            float(difficulty) if difficulty is not None else None,
            str(payload.get("intent") or "informational"),
            business_value,
            score,
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def import_keywords_csv(conn: sqlite3.Connection, customer_id: int, csv_text: str) -> int:
    reader = csv.DictReader(io.StringIO(csv_text))
    count = 0
    for row in reader:
        phrase = (row.get("phrase") or row.get("keyword") or "").strip()
        if not phrase:
            continue
        create_keyword(
            conn,
            customer_id,
            {
                "phrase": phrase,
                "volume": row.get("volume"),
                "difficulty": row.get("difficulty"),
                "intent": row.get("intent") or "informational",
                "business_value": row.get("business_value") or "medium",
            },
        )
        count += 1
    return count


def list_questions(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    q: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_questions WHERE customer_id = ? AND status = 'active'"
    params: list[Any] = [customer_id]
    if q:
        sql += " AND question_text LIKE ?"
        params.append(f"%{q}%")
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_question(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    text = str(payload.get("question_text") or "").strip()
    if not text:
        raise ValueError("Thiếu question_text")
    cur = conn.execute(
        """
        INSERT INTO seo_questions (
            customer_id, question_text, intent, funnel_stage, source, created_at
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            customer_id,
            text,
            str(payload.get("intent") or "informational"),
            str(payload.get("funnel_stage") or "awareness"),
            str(payload.get("source") or "manual"),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_keyword(conn: sqlite3.Connection, keyword_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM seo_keywords WHERE id = ?", (keyword_id,)).fetchone()
    return dict(row) if row else None


def get_question(conn: sqlite3.Connection, question_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM seo_questions WHERE id = ?", (question_id,)).fetchone()
    return dict(row) if row else None


def list_entity_groups(conn: sqlite3.Connection, customer_id: int) -> list[dict[str, Any]]:
    """Group keywords by intent as entity clusters (MVP — no seo_entities table)."""
    rows = conn.execute(
        """
        SELECT intent,
               COUNT(*) AS keyword_count,
               ROUND(AVG(COALESCE(opportunity_score, 0)), 1) AS avg_score,
               MAX(COALESCE(opportunity_score, 0)) AS top_score
        FROM seo_keywords
        WHERE customer_id = ? AND status = 'active'
        GROUP BY intent
        ORDER BY keyword_count DESC, top_score DESC
        """,
        (customer_id,),
    ).fetchall()
    groups: list[dict[str, Any]] = []
    for row in rows:
        intent = str(row["intent"] or "informational")
        samples = conn.execute(
            """
            SELECT phrase, opportunity_score FROM seo_keywords
            WHERE customer_id = ? AND status = 'active' AND intent = ?
            ORDER BY COALESCE(opportunity_score, 0) DESC LIMIT 5
            """,
            (customer_id, intent),
        ).fetchall()
        groups.append(
            {
                "entity_key": intent,
                "label": intent.replace("_", " ").title(),
                "intent": intent,
                "keyword_count": int(row["keyword_count"] or 0),
                "avg_opportunity_score": float(row["avg_score"] or 0),
                "top_opportunity_score": float(row["top_score"] or 0),
                "sample_keywords": [dict(s) for s in samples],
            }
        )
    return groups


def list_opportunities(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    min_score: float = 40.0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM seo_keywords
        WHERE customer_id = ? AND status = 'active'
          AND COALESCE(opportunity_score, 0) >= ?
        ORDER BY opportunity_score DESC, id DESC
        LIMIT ?
        """,
        (customer_id, min_score, limit),
    ).fetchall()
    return [dict(r) for r in rows]
