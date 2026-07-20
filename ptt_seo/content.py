"""Content factory — pipeline, brief, versions (Spec 6.4 Phase 2)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from ptt_seo.constants import (
    CONTENT_TRANSITIONS,
    CONTENT_WORKFLOW_STATUSES,
    PIPELINE_COLUMNS,
    can_transition,
)
from ptt_seo.research import get_keyword, get_question
from ptt_seo.workflow import approval_timeline, log_audit, record_approval


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _loads(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def list_content(
    conn: sqlite3.Connection,
    customer_id: int | None = None,
    *,
    lifecycle_id: int | None = None,
    workflow_status: str | None = None,
    owner_staff_id: int | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_content WHERE workflow_status != 'archived'"
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    if lifecycle_id is not None:
        sql += " AND lifecycle_id = ?"
        params.append(lifecycle_id)
    if workflow_status:
        sql += " AND workflow_status = ?"
        params.append(workflow_status)
    if owner_staff_id is not None:
        sql += " AND owner_staff_id = ?"
        params.append(owner_staff_id)
    sql += " ORDER BY updated_at DESC, id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def pipeline_board(
    conn: sqlite3.Connection,
    customer_id: int | None = None,
    *,
    lifecycle_id: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    items = list_content(conn, customer_id, lifecycle_id=lifecycle_id)
    board: dict[str, list[dict[str, Any]]] = {col: [] for col, _ in PIPELINE_COLUMNS}
    status_to_col = {}
    for col, statuses in PIPELINE_COLUMNS:
        for st in statuses:
            status_to_col[st] = col
    for item in items:
        col = status_to_col.get(item["workflow_status"], "idea")
        board[col].append(item)
    return board


def get_content(conn: sqlite3.Connection, content_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM seo_content WHERE id = ?", (content_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    brief_raw = d.pop("brief_json", "{}")
    outline_raw = d.pop("outline_json", "{}")
    if isinstance(brief_raw, dict):
        d["brief"] = brief_raw
    else:
        d["brief"] = _loads(brief_raw if isinstance(brief_raw, str) else json.dumps(brief_raw or {}))
    if isinstance(outline_raw, dict):
        d["outline"] = outline_raw
    else:
        d["outline"] = _loads(outline_raw if isinstance(outline_raw, str) else json.dumps(outline_raw or {}))
    d["approvals"] = approval_timeline(conn, content_id)
    if d.get("target_keyword_id"):
        d["target_keyword"] = get_keyword(conn, int(d["target_keyword_id"]))
    if d.get("target_question_id"):
        d["target_question"] = get_question(conn, int(d["target_question_id"]))
    return d


def create_content(conn: sqlite3.Connection, payload: dict[str, Any]) -> int:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Thiếu title")
    customer_id = int(payload["customer_id"])
    cur = conn.execute(
        """
        INSERT INTO seo_content (
            customer_id, project_id, lifecycle_id, title, slug, content_type,
            workflow_status, target_keyword_id, target_question_id, intent, funnel_stage,
            owner_staff_id, due_date, brief_json, outline_json, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            payload.get("project_id"),
            payload.get("lifecycle_id"),
            title,
            str(payload.get("slug") or ""),
            str(payload.get("content_type") or "blog"),
            str(payload.get("workflow_status") or "idea"),
            payload.get("target_keyword_id"),
            payload.get("target_question_id"),
            str(payload.get("intent") or ""),
            str(payload.get("funnel_stage") or ""),
            payload.get("owner_staff_id"),
            payload.get("due_date"),
            json.dumps(payload.get("brief") or {}, ensure_ascii=False),
            json.dumps(payload.get("outline") or {}, ensure_ascii=False),
            _ts(),
            _ts(),
        ),
    )
    conn.commit()
    cid = int(cur.lastrowid)
    log_audit(conn, customer_id=customer_id, entity_type="content", entity_id=cid, action="create")
    conn.commit()
    return cid


def create_content_from_research(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    keyword_id: int | None = None,
    question_id: int | None = None,
    lifecycle_id: int | None = None,
    project_id: int | None = None,
    title: str | None = None,
    brief: dict[str, Any] | None = None,
    owner_staff_id: int | None = None,
    due_date: str | None = None,
) -> int:
    title_val = str(title or "").strip()
    intent = ""
    if keyword_id:
        kw = get_keyword(conn, keyword_id)
        if kw:
            if not title_val:
                title_val = f"Content: {kw['phrase']}"
            intent = kw.get("intent") or ""
    elif question_id:
        q = get_question(conn, question_id)
        if q:
            if not title_val:
                title_val = f"FAQ: {q['question_text'][:80]}"
            intent = q.get("intent") or ""
    if not title_val:
        title_val = "Untitled content"
    brief_data = brief if isinstance(brief, dict) and brief else generate_brief_template(
        conn, keyword_id=keyword_id, question_id=question_id
    )
    payload: dict[str, Any] = {
        "customer_id": customer_id,
        "lifecycle_id": lifecycle_id,
        "project_id": project_id,
        "title": title_val,
        "target_keyword_id": keyword_id,
        "target_question_id": question_id,
        "intent": intent,
        "workflow_status": "brief_ready",
        "brief": brief_data,
    }
    if owner_staff_id is not None:
        payload["owner_staff_id"] = owner_staff_id
    if due_date:
        payload["due_date"] = due_date
    return create_content(conn, payload)


def preview_research_brief(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    keyword_id: int | None = None,
    question_id: int | None = None,
    use_ai: bool = False,
) -> dict[str, Any]:
    """Preview brief before creating content (Flow F1)."""
    title = "Untitled content"
    intent = ""
    primary = ""
    if keyword_id:
        kw = get_keyword(conn, keyword_id)
        if kw is None or int(kw.get("customer_id") or 0) != customer_id:
            raise ValueError("Keyword không tồn tại")
        title = f"Content: {kw['phrase']}"
        intent = str(kw.get("intent") or "")
        primary = str(kw.get("phrase") or "")
    elif question_id:
        q = get_question(conn, question_id)
        if q is None or int(q.get("customer_id") or 0) != customer_id:
            raise ValueError("Question không tồn tại")
        title = f"FAQ: {q['question_text'][:80]}"
        intent = str(q.get("intent") or "")
        primary = str(q.get("question_text") or "")
    else:
        raise ValueError("Thiếu keyword_id hoặc question_id")

    brief = generate_brief_template(conn, keyword_id=keyword_id, question_id=question_id)
    source = "template"
    if use_ai:
        from ptt_seo.brief_ai import ai_brief_available, generate_brief_ai

        if ai_brief_available():
            try:
                brief = generate_brief_ai(primary=primary, intent=intent)
                source = "ai"
            except Exception:
                source = "template_fallback"
        else:
            source = "template_no_api_key"

    from ptt_seo.brief_ai import ai_brief_available as _ai_ok

    return {
        "title": title,
        "brief": brief,
        "source": source,
        "keyword_id": keyword_id,
        "question_id": question_id,
        "ai_available": _ai_ok(),
    }


def generate_brief_template(
    conn: sqlite3.Connection,
    *,
    keyword_id: int | None = None,
    question_id: int | None = None,
) -> dict[str, Any]:
    kw = get_keyword(conn, keyword_id) if keyword_id else None
    q = get_question(conn, question_id) if question_id else None
    primary = (kw or {}).get("phrase") or (q or {}).get("question_text") or ""
    return {
        "primary_topic": primary,
        "objective": "Tăng visibility organic và AEO coverage",
        "target_audience": "Người tìm kiếm có intent liên quan",
        "sections": [
            "Answer-first intro",
            "Core content blocks",
            "FAQ / schema block",
            "Internal links",
            "CTA",
        ],
        "checklist": [
            "Target keyword/question rõ ràng",
            "Heading theo câu hỏi",
            "Schema phù hợp",
            "AEO answer-first paragraph",
        ],
    }


def update_content(conn: sqlite3.Connection, content_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM seo_content WHERE id = ?", (content_id,)).fetchone()
    if row is None:
        raise ValueError("Content không tồn tại")
    current = dict(row)
    fields = {
        "title": payload.get("title", current["title"]),
        "slug": payload.get("slug", current["slug"]),
        "content_type": payload.get("content_type", current["content_type"]),
        "body_html": payload.get("body_html", current["body_html"]),
        "due_date": payload.get("due_date", current["due_date"]),
        "owner_staff_id": payload.get("owner_staff_id", current["owner_staff_id"]),
        "intent": payload.get("intent", current["intent"]),
        "funnel_stage": payload.get("funnel_stage", current["funnel_stage"]),
    }
    brief = payload.get("brief")
    outline = payload.get("outline")
    if brief is not None:
        current_brief = _loads(current["brief_json"])
        if isinstance(brief, dict):
            current_brief.update(brief)
        brief_json = json.dumps(current_brief, ensure_ascii=False)
    else:
        brief_json = current["brief_json"]
    if outline is not None:
        current_outline = _loads(current["outline_json"])
        if isinstance(outline, dict):
            current_outline.update(outline)
        outline_json = json.dumps(current_outline, ensure_ascii=False)
    else:
        outline_json = current["outline_json"]
    conn.execute(
        """
        UPDATE seo_content SET
            title=?, slug=?, content_type=?, body_html=?, due_date=?, owner_staff_id=?,
            intent=?, funnel_stage=?, brief_json=?, outline_json=?, updated_at=?
        WHERE id=?
        """,
        (
            str(fields["title"]),
            str(fields["slug"]),
            str(fields["content_type"]),
            str(fields["body_html"]),
            fields["due_date"],
            fields["owner_staff_id"],
            str(fields["intent"] or ""),
            str(fields["funnel_stage"] or ""),
            brief_json,
            outline_json,
            _ts(),
            content_id,
        ),
    )
    conn.commit()
    result = get_content(conn, content_id)
    assert result is not None
    return result


def transition_status(
    conn: sqlite3.Connection,
    content_id: int,
    target_status: str,
    *,
    actor_id: str = "",
    notes: str = "",
) -> dict[str, Any]:
    if target_status not in CONTENT_WORKFLOW_STATUSES:
        raise ValueError(f"Status không hợp lệ: {target_status}")
    row = conn.execute("SELECT * FROM seo_content WHERE id = ?", (content_id,)).fetchone()
    if row is None:
        raise ValueError("Content không tồn tại")
    current = dict(row)
    current_status = current["workflow_status"]
    if not can_transition(current_status, target_status):
        allowed = ", ".join(CONTENT_TRANSITIONS.get(current_status, ()))
        raise ValueError(f"Không thể chuyển {current_status} → {target_status}. Cho phép: {allowed}")

    if target_status == "published":
        from ptt_seo.governance import assert_publish_allowed

        assert_publish_allowed(conn, content_id=content_id, action="publish")

    conn.execute(
        "UPDATE seo_content SET workflow_status = ?, updated_at = ? WHERE id = ?",
        (target_status, _ts(), content_id),
    )
    log_audit(
        conn,
        customer_id=current.get("customer_id"),
        entity_type="content",
        entity_id=content_id,
        action=f"status:{current_status}->{target_status}",
        actor_id=actor_id,
        payload={"notes": notes},
    )
    conn.commit()
    result = get_content(conn, content_id)
    assert result is not None
    if target_status == "published":
        try:
            from ptt_seo.cms_publish import maybe_auto_publish

            pub = maybe_auto_publish(conn, content_id)
            if pub:
                result["cms_publish"] = pub
        except Exception:
            pass
    if target_status == "client_review":
        from ptt_seo.temporal_bridge import start_content_approval_workflow

        wf = start_content_approval_workflow(
            conn,
            content_id=content_id,
            customer_id=int(current.get("customer_id") or 0),
            title=str(current.get("title") or ""),
            submitted_by=actor_id,
        )
        result["temporal_signal"] = wf.get("temporal_signal")
    return result


def approve_stage(
    conn: sqlite3.Connection,
    content_id: int,
    stage: str,
    *,
    approved: bool,
    actor_id: str = "",
    notes: str = "",
) -> dict[str, Any]:
    status = "approved" if approved else "rejected"
    record_approval(conn, content_id=content_id, stage=stage, status=status, actor_id=actor_id, notes=notes)
    row = conn.execute("SELECT * FROM seo_content WHERE id = ?", (content_id,)).fetchone()
    if row is None:
        raise ValueError("Content không tồn tại")
    current = dict(row)
    if approved:
        if stage == "client_review":
            from ptt_seo.governance import assert_publish_allowed

            assert_publish_allowed(conn, content_id=content_id, action="approve")
        next_map = {
            "seo_review": "aeo_review",
            "aeo_review": "approved",
            "technical_review": "client_review",
            "client_review": "approved",
        }
        nxt = next_map.get(stage)
        if nxt and can_transition(current["workflow_status"], nxt):
            conn.execute(
                "UPDATE seo_content SET workflow_status = ?, updated_at = ? WHERE id = ?",
                (nxt, _ts(), content_id),
            )
            if nxt == "client_review":
                from ptt_seo.temporal_bridge import start_content_approval_workflow

                start_content_approval_workflow(
                    conn,
                    content_id=content_id,
                    customer_id=int(current.get("customer_id") or 0),
                    title=str(current.get("title") or ""),
                    submitted_by=actor_id,
                )
    elif can_transition(current["workflow_status"], "in_writing"):
        conn.execute(
            "UPDATE seo_content SET workflow_status = 'in_writing', updated_at = ? WHERE id = ?",
            (_ts(), content_id),
        )
    log_audit(
        conn,
        customer_id=current.get("customer_id"),
        entity_type="content",
        entity_id=content_id,
        action=f"approval:{stage}:{status}",
        actor_id=actor_id,
        payload={"notes": notes},
    )
    conn.commit()
    result = get_content(conn, content_id)
    assert result is not None
    if stage == "client_review":
        from ptt_seo.temporal_bridge import signal_content_review_workflow

        sig = signal_content_review_workflow(
            conn,
            content_id=content_id,
            approved=approved,
            reviewed_by=actor_id,
            note=notes,
        )
        result["temporal_signal"] = sig.get("temporal_signal")
    return result


def list_versions(conn: sqlite3.Connection, content_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, content_id, version_number, changes_summary, created_by, created_at,
               LENGTH(body_html) AS body_length
        FROM seo_content_versions
        WHERE content_id = ?
        ORDER BY version_number DESC
        """,
        (content_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_version(conn: sqlite3.Connection, content_id: int, version_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM seo_content_versions WHERE id = ? AND content_id = ?",
        (version_id, content_id),
    ).fetchone()
    return dict(row) if row else None


def save_version(
    conn: sqlite3.Connection,
    content_id: int,
    *,
    body_html: str,
    changes_summary: str = "",
    created_by: str = "",
) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version_number), 0) AS v FROM seo_content_versions WHERE content_id = ?",
        (content_id,),
    ).fetchone()
    ver = int(row["v"] or 0) + 1
    cur = conn.execute(
        """
        INSERT INTO seo_content_versions (content_id, version_number, body_html, changes_summary, created_by, created_at)
        VALUES (?,?,?,?,?,?)
        """,
        (content_id, ver, body_html, changes_summary, created_by, _ts()),
    )
    conn.execute(
        "UPDATE seo_content SET body_html = ?, updated_at = ? WHERE id = ?",
        (body_html, _ts(), content_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def count_by_status(conn: sqlite3.Connection, customer_id: int) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT workflow_status, COUNT(*) AS c FROM seo_content
        WHERE customer_id = ? AND workflow_status != 'archived'
        GROUP BY workflow_status
        """,
        (customer_id,),
    ).fetchall()
    return {str(r["workflow_status"]): int(r["c"]) for r in rows}


def aeo_checklist_for_content(conn: sqlite3.Connection, content_id: int) -> dict[str, Any]:
    """AEO readiness checklist for content detail (S-08)."""
    item = get_content(conn, content_id)
    if item is None:
        raise ValueError("Content không tồn tại")
    brief = item.get("brief") or {}
    outline = item.get("outline") or {}
    checklist_items = brief.get("checklist") or []
    body = (item.get("body_html") or "").lower()
    schema_raw = outline.get("schema_json") or outline.get("schema") or ""
    has_schema = bool(str(schema_raw).strip())
    has_faq = "faq" in body or "câu hỏi" in body
    has_answer_first = len(body.strip()) > 80
    linked_question = None
    qid = item.get("target_question_id")
    if qid:
        q = get_question(conn, int(qid))
        if q:
            linked_question = {
                "id": q["id"],
                "question_text": q.get("question_text") or "",
                "brand_visible": bool(int(q.get("brand_visible") or 0)),
            }
    rows = []
    for label in checklist_items:
        done = False
        low = str(label).lower()
        if "schema" in low:
            done = has_schema
        elif "aeo" in low or "answer" in low:
            done = has_answer_first and has_faq
        elif "keyword" in low or "question" in low:
            done = bool(brief.get("target_keyword") or brief.get("primary_topic") or linked_question)
        elif "heading" in low:
            done = "<h" in (item.get("body_html") or "").lower()
        else:
            done = bool(body)
        rows.append({"label": label, "done": done})
    if not rows:
        rows = [
            {"label": "Answer-first paragraph", "done": has_answer_first},
            {"label": "FAQ block", "done": has_faq},
            {"label": "Schema JSON-LD", "done": has_schema},
            {"label": "Linked AEO question", "done": linked_question is not None},
        ]
    done_count = sum(1 for r in rows if r["done"])
    return {
        "content_id": content_id,
        "items": rows,
        "done_count": done_count,
        "total_count": len(rows),
        "readiness_pct": round(100.0 * done_count / len(rows), 1) if rows else 0,
        "linked_question": linked_question,
    }
