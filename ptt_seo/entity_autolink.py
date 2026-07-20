"""Entity auto-link from keyword clusters and content (Gate E4)."""
from __future__ import annotations

import re
import sqlite3
from typing import Any

from ptt_seo.entities import create_entity, create_entity_link, list_entities


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _find_entity_by_name(entities: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    target = _norm(name)
    for e in entities:
        if _norm(str(e.get("entity_name") or "")) == target:
            return e
    return None


def _ensure_entity(
    conn: sqlite3.Connection,
    customer_id: int,
    name: str,
    entity_type: str,
    *,
    notes: str = "",
    cache: list[dict[str, Any]],
) -> dict[str, Any]:
    found = _find_entity_by_name(cache, name)
    if found:
        return found
    eid = create_entity(
        conn,
        customer_id,
        {"entity_name": name, "entity_type": entity_type, "notes": notes},
    )
    row = {"id": eid, "entity_name": name, "entity_type": entity_type}
    cache.append(row)
    return row


def autolink_from_clusters(conn: sqlite3.Connection, customer_id: int) -> dict[str, int]:
    """Create topic_cluster entities from keyword clusters and link related pairs."""
    from ptt_seo.clusters import list_clusters

    entities = list_entities(conn, customer_id)
    clusters = list_clusters(conn, customer_id)
    created_entities = 0
    created_links = 0
    cluster_entities: list[dict[str, Any]] = []

    for cluster in clusters:
        name = str(cluster.get("name") or "").strip()
        if not name:
            continue
        before = len(entities)
        ent = _ensure_entity(
            conn,
            customer_id,
            name,
            "topic_cluster",
            notes=f"cluster_id:{cluster['id']}",
            cache=entities,
        )
        if len(entities) > before:
            created_entities += 1
        cluster_entities.append(ent)

    for i, src in enumerate(cluster_entities):
        for tgt in cluster_entities[i + 1 :]:
            try:
                create_entity_link(
                    conn,
                    customer_id,
                    {
                        "source_entity_id": int(src["id"]),
                        "target_entity_id": int(tgt["id"]),
                        "link_type": "cluster_related",
                        "weight": 0.5,
                    },
                )
                created_links += 1
            except ValueError:
                pass

    return {"entities_created": created_entities, "links_created": created_links}


def autolink_from_content(conn: sqlite3.Connection, customer_id: int) -> dict[str, int]:
    """Link content titles / target keywords to nearest entity nodes."""
    import json

    entities = list_entities(conn, customer_id)
    rows = conn.execute(
        """
        SELECT id, title, brief_json, target_keyword_id
        FROM seo_content
        WHERE customer_id = ? AND workflow_status NOT IN ('archived')
        """,
        (customer_id,),
    ).fetchall()
    created_entities = 0
    created_links = 0

    for row in rows:
        title = str(row["title"] or "").strip()
        keyword = ""
        try:
            brief = json.loads(row["brief_json"] or "{}")
            keyword = str(brief.get("target_keyword") or brief.get("primary_topic") or "").strip()
        except (json.JSONDecodeError, TypeError):
            pass
        if not keyword and row["target_keyword_id"]:
            from ptt_seo.research import get_keyword

            kw = get_keyword(conn, int(row["target_keyword_id"]))
            if kw:
                keyword = str(kw.get("phrase") or "")
        label = keyword or title
        if not label:
            continue
        before = len(entities)
        ent = _ensure_entity(
            conn,
            customer_id,
            label,
            "content_topic",
            notes=f"content_id:{row['id']}",
            cache=entities,
        )
        if len(entities) > before:
            created_entities += 1
        for topic in entities:
            if topic.get("entity_type") != "topic_cluster":
                continue
            if _norm(str(topic.get("entity_name") or "")) in _norm(label) or _norm(label) in _norm(
                str(topic.get("entity_name") or "")
            ):
                try:
                    create_entity_link(
                        conn,
                        customer_id,
                        {
                            "source_entity_id": int(ent["id"]),
                            "target_entity_id": int(topic["id"]),
                            "link_type": "content_cluster",
                            "weight": 1.0,
                        },
                    )
                    created_links += 1
                except ValueError:
                    pass

    return {"entities_created": created_entities, "links_created": created_links}


def autolink_all(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    clusters = autolink_from_clusters(conn, customer_id)
    content = autolink_from_content(conn, customer_id)
    return {
        "ok": True,
        "clusters": clusters,
        "content": content,
        "entities_created": clusters["entities_created"] + content["entities_created"],
        "links_created": clusters["links_created"] + content["links_created"],
    }
