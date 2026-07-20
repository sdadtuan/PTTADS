"""Entity graph — entities, links, graph JSON (enterprise backlog)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _loads(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    try:
        val = json.loads(raw if isinstance(raw, str) else str(raw))
        return val if isinstance(val, list) else []
    except json.JSONDecodeError:
        return []


def list_entities(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_entities WHERE customer_id = ?"
    params: list[Any] = [customer_id]
    if entity_type:
        sql += " AND entity_type = ?"
        params.append(entity_type)
    sql += " ORDER BY entity_name ASC, id ASC"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for row in rows:
        row["same_as"] = _loads(row.pop("same_as_json", "[]"))
    return rows


def create_entity(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    name = str(payload.get("entity_name") or "").strip()
    if not name:
        raise ValueError("Thiếu entity_name")
    same_as = payload.get("same_as") or []
    cur = conn.execute(
        """
        INSERT INTO seo_entities (
            customer_id, entity_name, entity_type, same_as_json,
            confidence_score, notes, created_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            name,
            str(payload.get("entity_type") or "category"),
            json.dumps(same_as, ensure_ascii=False),
            payload.get("confidence_score"),
            str(payload.get("notes") or ""),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def create_entity_link(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    src = int(payload["source_entity_id"])
    tgt = int(payload["target_entity_id"])
    if src == tgt:
        raise ValueError("Không thể link entity với chính nó")
    cur = conn.execute(
        """
        INSERT INTO seo_entity_links (
            customer_id, source_entity_id, target_entity_id, link_type, weight, created_at
        ) VALUES (?,?,?,?,?,?)
        ON CONFLICT(customer_id, source_entity_id, target_entity_id, link_type)
        DO UPDATE SET weight = excluded.weight
        """,
        (
            customer_id,
            src,
            tgt,
            str(payload.get("link_type") or "related"),
            float(payload.get("weight") or 1.0),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def seed_entities_from_keywords(conn: sqlite3.Connection, customer_id: int) -> int:
    """Bootstrap entities from distinct keyword intents (one-time helper)."""
    rows = conn.execute(
        """
        SELECT DISTINCT intent FROM seo_keywords
        WHERE customer_id = ? AND status = 'active' AND intent != ''
        """,
        (customer_id,),
    ).fetchall()
    created = 0
    for row in rows:
        intent = str(row["intent"] if isinstance(row, sqlite3.Row) else row[0])
        name = intent.replace("_", " ").title()
        existing = conn.execute(
            """
            SELECT id FROM seo_entities
            WHERE customer_id = ? AND entity_name = ? AND entity_type = 'topic_cluster'
            """,
            (customer_id, name),
        ).fetchone()
        if existing:
            continue
        create_entity(
            conn,
            customer_id,
            {"entity_name": name, "entity_type": "topic_cluster", "notes": f"intent:{intent}"},
        )
        created += 1
    return created


def entity_graph(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    entities = list_entities(conn, customer_id)
    entity_ids = {e["id"] for e in entities}
    link_rows = conn.execute(
        "SELECT * FROM seo_entity_links WHERE customer_id = ?",
        (customer_id,),
    ).fetchall()
    nodes = [
        {
            "id": f"e{e['id']}",
            "entity_id": e["id"],
            "label": e["entity_name"],
            "type": e["entity_type"],
            "confidence": e.get("confidence_score"),
        }
        for e in entities
    ]
    edges: list[dict[str, Any]] = []
    for row in link_rows:
        link = dict(row)
        if link["source_entity_id"] not in entity_ids or link["target_entity_id"] not in entity_ids:
            continue
        edges.append(
            {
                "id": f"l{link['id']}",
                "source": f"e{link['source_entity_id']}",
                "target": f"e{link['target_entity_id']}",
                "type": link["link_type"],
                "weight": link.get("weight") or 1.0,
            }
        )
    return {"nodes": nodes, "edges": edges, "entity_count": len(nodes), "link_count": len(edges)}
