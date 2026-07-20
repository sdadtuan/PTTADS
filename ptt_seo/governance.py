"""Governance & compliance — policy engine (Spec 6.12 Phase 5)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any

from ptt_seo.content import get_content
from ptt_seo.technical import count_open_critical
from ptt_seo.workflow import approval_timeline


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _sql_bool(conn: Any, value: bool) -> bool | int:
    return value if getattr(conn, "backend", "sqlite") == "pg" else int(value)


def governance_enabled() -> bool:
    return os.environ.get("PTT_SEO_GOVERNANCE_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _loads_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return {}


DEFAULT_POLICIES: tuple[dict[str, Any], ...] = (
    {
        "policy_key": "metadata_required",
        "name": "Metadata bắt buộc",
        "description": "Title, keyword/topic, meta title & description trong brief",
        "rule_type": "required_fields",
        "rule_config": {
            "fields": ["title", "target_keyword", "meta_title", "meta_description"],
        },
        "severity": "block",
    },
    {
        "policy_key": "qa_complete",
        "name": "QA stages hoàn tất",
        "description": "SEO, AEO, Technical review đã approved",
        "rule_type": "approval_complete",
        "rule_config": {"stages": ["seo_review", "aeo_review", "technical_review"]},
        "severity": "block",
    },
    {
        "policy_key": "no_critical_technical",
        "name": "Không issue critical mở",
        "description": "Zero critical technical issues cho client",
        "rule_type": "technical_critical",
        "rule_config": {"max_open": 0},
        "severity": "block",
    },
    {
        "policy_key": "schema_valid",
        "name": "Schema checklist",
        "description": "Brief checklist có mục schema",
        "rule_type": "schema_valid",
        "rule_config": {"require_schema_checklist": True},
        "severity": "block",
    },
)


def seed_default_policies(conn: sqlite3.Connection, *, customer_id: int | None = None) -> None:
    for pol in DEFAULT_POLICIES:
        row = conn.execute(
            """
            SELECT id FROM seo_governance_policies
            WHERE policy_key = ? AND customer_id IS NULL
            """,
            (pol["policy_key"],),
        ).fetchone()
        if customer_id is not None:
            row_c = conn.execute(
                """
                SELECT id FROM seo_governance_policies
                WHERE policy_key = ? AND customer_id = ?
                """,
                (pol["policy_key"], customer_id),
            ).fetchone()
            if row_c:
                continue
        elif row:
            continue
        cfg = json.dumps(pol["rule_config"], ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO seo_governance_policies (
                customer_id, policy_key, name, description, rule_type,
                rule_config, severity, active, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                customer_id,
                pol["policy_key"],
                pol["name"],
                pol["description"],
                pol["rule_type"],
                cfg,
                pol["severity"],
                _sql_bool(conn, True),
                _ts(),
                _ts(),
            ),
        )
    conn.commit()


def list_policies(conn: sqlite3.Connection, *, customer_id: int | None = None) -> list[dict[str, Any]]:
    seed_default_policies(conn, customer_id=None)
    if customer_id is not None:
        seed_default_policies(conn, customer_id=customer_id)
    if customer_id is None:
        rows = conn.execute(
            "SELECT * FROM seo_governance_policies WHERE customer_id IS NULL ORDER BY policy_key"
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM seo_governance_policies
            WHERE customer_id IS NULL OR customer_id = ?
            ORDER BY CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END, policy_key
            """,
            (customer_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        d = dict(row)
        key = str(d["policy_key"])
        if key in seen:
            continue
        seen.add(key)
        d["rule_config"] = _loads_json(d.get("rule_config"))
        d["active"] = bool(d.get("active"))
        out.append(d)
    return out


def _field_value(content: dict[str, Any], field: str) -> Any:
    if field == "title":
        return (content.get("title") or "").strip()
    if field == "target_keyword":
        if content.get("target_keyword_id"):
            return content.get("target_keyword") or True
        brief = content.get("brief") or {}
        return (brief.get("primary_topic") or "").strip()
    brief = content.get("brief") or {}
    if field == "meta_title":
        return (brief.get("meta_title") or "").strip()
    if field == "meta_description":
        return (brief.get("meta_description") or "").strip()
    return content.get(field)


def _eval_required_fields(content: dict[str, Any], config: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in config.get("fields") or []:
        val = _field_value(content, str(field))
        if not val:
            missing.append(str(field))
    return missing


def _eval_approval_complete(conn: sqlite3.Connection, content_id: int, config: dict[str, Any]) -> list[str]:
    stages = config.get("stages") or []
    timeline = {t["stage"]: t["status"] for t in approval_timeline(conn, content_id)}
    missing = [s for s in stages if timeline.get(s) != "approved"]
    return missing


def _eval_technical_critical(conn: sqlite3.Connection, customer_id: int, config: dict[str, Any]) -> list[str]:
    max_open = int(config.get("max_open", 0))
    open_count = count_open_critical(conn, customer_id)
    if open_count > max_open:
        return [f"critical_open:{open_count}"]
    return []


def _eval_schema_valid(content: dict[str, Any], config: dict[str, Any]) -> list[str]:
    if not config.get("require_schema_checklist", True):
        return []
    brief = content.get("brief") or {}
    checklist = brief.get("checklist") or []
    for item in checklist:
        if "schema" in str(item).lower():
            return []
    outline = content.get("outline") or {}
    if outline.get("schema") or outline.get("schema_json"):
        return []
    return ["schema_checklist_missing"]


def _evaluate_policy(
    conn: sqlite3.Connection,
    policy: dict[str, Any],
    *,
    content: dict[str, Any],
    content_id: int,
    customer_id: int,
) -> dict[str, Any] | None:
    rule_type = str(policy.get("rule_type") or "")
    config = policy.get("rule_config") or {}
    detail: list[str] = []
    if rule_type == "required_fields":
        detail = _eval_required_fields(content, config)
    elif rule_type == "approval_complete":
        detail = _eval_approval_complete(conn, content_id, config)
    elif rule_type == "technical_critical":
        detail = _eval_technical_critical(conn, customer_id, config)
    elif rule_type == "schema_valid":
        detail = _eval_schema_valid(content, config)
    if not detail:
        return None
    return {
        "policy_key": policy["policy_key"],
        "name": policy.get("name") or policy["policy_key"],
        "severity": policy.get("severity") or "block",
        "details": detail,
    }


def list_content_override_keys(conn: sqlite3.Connection, content_id: int) -> frozenset[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT o.policy_key
        FROM seo_governance_overrides o
        INNER JOIN seo_governance_evaluations e ON e.id = o.evaluation_id
        WHERE e.entity_type = 'content' AND e.entity_id = ?
        """,
        (content_id,),
    ).fetchall()
    return frozenset(str(dict(row)["policy_key"]) for row in rows)


class GovernanceBlockError(ValueError):
    """Raised when publish/approve is blocked by governance policies."""

    def __init__(self, result: dict[str, Any]):
        self.result = result
        keys = ", ".join(v["policy_key"] for v in result["violations"])
        super().__init__(f"Governance block: {keys}")


def evaluate_content_publish(
    conn: sqlite3.Connection,
    *,
    content_id: int,
    action: str = "publish",
    override_policy_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    if not governance_enabled():
        return {"ok": True, "violations": [], "evaluation_id": None}

    content = get_content(conn, content_id)
    if content is None:
        raise ValueError("Content không tồn tại")
    customer_id = int(content["customer_id"])
    policies = [p for p in list_policies(conn, customer_id=customer_id) if p.get("active")]
    overrides = (override_policy_keys or frozenset()) | list_content_override_keys(conn, content_id)

    violations: list[dict[str, Any]] = []
    for policy in policies:
        if policy["policy_key"] in overrides:
            continue
        hit = _evaluate_policy(
            conn,
            policy,
            content=content,
            content_id=content_id,
            customer_id=customer_id,
        )
        if hit and hit.get("severity") == "block":
            violations.append(hit)

    passed = len(violations) == 0
    vjson = json.dumps(violations, ensure_ascii=False)
    cur = conn.execute(
        """
        INSERT INTO seo_governance_evaluations (
            customer_id, entity_type, entity_id, action, passed, violations_json, evaluated_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (customer_id, "content", content_id, action, _sql_bool(conn, passed), vjson, _ts()),
    )
    conn.commit()
    evaluation_id = int(cur.lastrowid)
    return {
        "ok": passed,
        "violations": violations,
        "evaluation_id": evaluation_id,
    }


def assert_publish_allowed(
    conn: sqlite3.Connection,
    *,
    content_id: int,
    action: str = "publish",
) -> None:
    result = evaluate_content_publish(conn, content_id=content_id, action=action)
    if not result["ok"]:
        raise GovernanceBlockError(result)


def record_override(
    conn: sqlite3.Connection,
    *,
    evaluation_id: int,
    policy_key: str,
    actor_id: str = "",
    reason: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO seo_governance_overrides (
            evaluation_id, policy_key, actor_id, reason, created_at
        ) VALUES (?,?,?,?,?)
        """,
        (evaluation_id, policy_key, actor_id, reason, _ts()),
    )
    conn.commit()
    return int(cur.lastrowid)


def upsert_policy(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    policy_key = str(payload.get("policy_key") or "").strip()
    if not policy_key:
        raise ValueError("Thiếu policy_key")
    customer_id = payload.get("customer_id")
    cfg = json.dumps(payload.get("rule_config") or {}, ensure_ascii=False)
    existing = conn.execute(
        """
        SELECT id FROM seo_governance_policies
        WHERE policy_key = ? AND customer_id IS ?
        """,
        (policy_key, customer_id),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE seo_governance_policies SET
                name=?, description=?, rule_type=?, rule_config=?, severity=?, active=?, updated_at=?
            WHERE id=?
            """,
            (
                str(payload.get("name") or policy_key),
                str(payload.get("description") or ""),
                str(payload.get("rule_type") or "custom"),
                cfg,
                str(payload.get("severity") or "block"),
                1 if payload.get("active", True) else 0,
                _ts(),
                int(dict(existing)["id"]),
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO seo_governance_policies (
                customer_id, policy_key, name, description, rule_type,
                rule_config, severity, active, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                customer_id,
                policy_key,
                str(payload.get("name") or policy_key),
                str(payload.get("description") or ""),
                str(payload.get("rule_type") or "custom"),
                cfg,
                str(payload.get("severity") or "block"),
                1 if payload.get("active", True) else 0,
                _ts(),
                _ts(),
            ),
        )
    conn.commit()
    policies = list_policies(conn, customer_id=customer_id if customer_id else None)
    for p in policies:
        if p["policy_key"] == policy_key:
            return p
    raise ValueError("Policy upsert failed")


def compliance_summary(conn: sqlite3.Connection, *, customer_id: int | None = None, days: int = 7) -> dict[str, Any]:
    from datetime import timedelta

    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        SELECT passed, COUNT(*) AS c FROM seo_governance_evaluations
        WHERE evaluated_at >= ?
    """
    params: list[Any] = [cutoff]
    if customer_id is not None:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    sql += " GROUP BY passed"
    rows = conn.execute(sql, params).fetchall()
    passed = failed = 0
    for row in rows:
        if int(dict(row)["passed"]):
            passed = int(dict(row)["c"])
        else:
            failed = int(dict(row)["c"])
    total = passed + failed
    recent = conn.execute(
        """
        SELECT * FROM seo_governance_evaluations
        WHERE passed = 0
        ORDER BY id DESC LIMIT 20
        """
    ).fetchall()
    violations_out: list[dict[str, Any]] = []
    for row in recent:
        d = dict(row)
        d["violations"] = json.loads(d.get("violations_json") or "[]")
        violations_out.append(d)
    return {
        "days": days,
        "total_evaluations": total,
        "passed": passed,
        "failed": failed,
        "pass_rate_pct": round(100.0 * passed / total, 1) if total else 100.0,
        "recent_violations": violations_out,
    }
