"""Experimentation — hypothesis, variants, decision log (Spec 6.9 Phase 5)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any

EXPERIMENT_STATUSES: tuple[str, ...] = ("draft", "running", "paused", "completed", "archived")
STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("running", "archived"),
    "running": ("paused", "completed", "archived"),
    "paused": ("running", "completed", "archived"),
    "completed": ("archived",),
    "archived": (),
}


def experiments_enabled() -> bool:
    return os.environ.get("PTT_SEO_EXPERIMENTS_ENABLED", "0").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _loads(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return {}


def _row_experiment(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def _uplift_pct(control_total: float, variant_total: float) -> float | None:
    if control_total <= 0:
        return None
    return round(((variant_total - control_total) / control_total) * 100, 1)


def _observation_click_totals(
    conn: sqlite3.Connection,
    experiment_ids: list[int],
) -> dict[int, dict[str, float]]:
    if not experiment_ids:
        return {}
    placeholders = ",".join("?" * len(experiment_ids))
    rows = conn.execute(
        f"""
        SELECT experiment_id, variant_key, SUM(metric_value) AS total
        FROM seo_experiment_observations
        WHERE experiment_id IN ({placeholders}) AND metric_name = 'clicks'
        GROUP BY experiment_id, variant_key
        """,
        experiment_ids,
    ).fetchall()
    out: dict[int, dict[str, float]] = {}
    for row in rows:
        d = dict(row)
        eid = int(d["experiment_id"])
        out.setdefault(eid, {})[str(d["variant_key"])] = float(d["total"] or 0)
    return out


def summarize_uplift(observations: list[dict[str, Any]], *, metric_name: str = "clicks") -> dict[str, Any]:
    totals: dict[str, float] = {}
    for obs in observations:
        if str(obs.get("metric_name")) != metric_name:
            continue
        key = str(obs.get("variant_key") or "")
        totals[key] = totals.get(key, 0.0) + float(obs.get("metric_value") or 0)
    control = totals.get("control", 0.0)
    variant = totals.get("variant_a", 0.0)
    uplift = _uplift_pct(control, variant)
    return {
        "metric_name": metric_name,
        "totals": totals,
        "uplift_pct": uplift,
        "uplift_label": f"{uplift:+.1f}%" if uplift is not None else "—",
    }


def create_experiment(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Thiếu title")
    cur = conn.execute(
        """
        INSERT INTO seo_experiments (
            customer_id, title, hypothesis, experiment_type, target_url, content_id,
            status, owner_id, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            title,
            str(payload.get("hypothesis") or ""),
            str(payload.get("experiment_type") or "content"),
            str(payload.get("target_url") or ""),
            payload.get("content_id"),
            "draft",
            str(payload.get("owner_id") or ""),
            _ts(),
            _ts(),
        ),
    )
    conn.commit()
    eid = int(cur.lastrowid)
    for vk, label in (("control", "Control"), ("variant_a", "Variant A")):
        conn.execute(
            """
            INSERT INTO seo_experiment_variants (experiment_id, variant_key, label, config_json)
            VALUES (?,?,?,?)
            """,
            (eid, vk, label, "{}"),
        )
    conn.commit()
    item = get_experiment(conn, eid)
    assert item is not None
    return item


def list_experiments(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    status: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_experiments WHERE customer_id = ?"
    params: list[Any] = [customer_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY updated_at DESC, id DESC"
    rows = [_row_experiment(dict(r)) for r in conn.execute(sql, params).fetchall()]
    totals_by_exp = _observation_click_totals(conn, [int(r["id"]) for r in rows])
    for row in rows:
        totals = totals_by_exp.get(int(row["id"]), {})
        uplift = _uplift_pct(totals.get("control", 0.0), totals.get("variant_a", 0.0))
        row["uplift_pct"] = uplift
        row["uplift_label"] = f"{uplift:+.1f}%" if uplift is not None else "—"
    return rows


def get_experiment(conn: sqlite3.Connection, experiment_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM seo_experiments WHERE id = ?", (experiment_id,)).fetchone()
    if row is None:
        return None
    d = _row_experiment(dict(row))
    variants = conn.execute(
        "SELECT * FROM seo_experiment_variants WHERE experiment_id = ? ORDER BY variant_key",
        (experiment_id,),
    ).fetchall()
    d["variants"] = [{**dict(v), "config": _loads(dict(v).get("config_json"))} for v in variants]
    observations = conn.execute(
        """
        SELECT * FROM seo_experiment_observations
        WHERE experiment_id = ? ORDER BY metric_date DESC, variant_key, metric_name
        """,
        (experiment_id,),
    ).fetchall()
    d["observations"] = [dict(o) for o in observations]
    decisions = conn.execute(
        "SELECT * FROM seo_experiment_decisions WHERE experiment_id = ? ORDER BY id DESC",
        (experiment_id,),
    ).fetchall()
    d["decisions"] = [dict(x) for x in decisions]
    d["metrics_summary"] = summarize_uplift(d["observations"])
    return d


def transition_experiment(
    conn: sqlite3.Connection,
    experiment_id: int,
    status: str,
    *,
    actor_id: str = "",
) -> dict[str, Any]:
    if status not in EXPERIMENT_STATUSES:
        raise ValueError(f"Status không hợp lệ: {status}")
    row = conn.execute("SELECT * FROM seo_experiments WHERE id = ?", (experiment_id,)).fetchone()
    if row is None:
        raise ValueError("Experiment không tồn tại")
    current = dict(row)["status"]
    if status not in STATUS_TRANSITIONS.get(str(current), ()):
        raise ValueError(f"Không thể chuyển {current} → {status}")
    started_at = dict(row).get("started_at")
    ended_at = dict(row).get("ended_at")
    if status == "running" and not started_at:
        started_at = _ts()
    if status in {"completed", "archived"}:
        ended_at = _ts()
    conn.execute(
        """
        UPDATE seo_experiments SET status=?, started_at=?, ended_at=?, updated_at=?, owner_id=COALESCE(NULLIF(owner_id,''), ?)
        WHERE id=?
        """,
        (status, started_at, ended_at, _ts(), actor_id, experiment_id),
    )
    conn.commit()
    item = get_experiment(conn, experiment_id)
    assert item is not None
    return item


def upsert_observation(
    conn: sqlite3.Connection,
    experiment_id: int,
    *,
    variant_key: str,
    metric_date: str,
    metric_name: str,
    metric_value: float,
    source: str = "manual",
) -> dict[str, Any]:
    conn.execute(
        """
        INSERT INTO seo_experiment_observations (
            experiment_id, variant_key, metric_date, metric_name, metric_value, source, created_at
        ) VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(experiment_id, variant_key, metric_date, metric_name)
        DO UPDATE SET metric_value=excluded.metric_value, source=excluded.source
        """,
        (experiment_id, variant_key, metric_date, metric_name, float(metric_value), source, _ts()),
    )
    conn.commit()
    return {"ok": True}


def pull_gsc_metrics(
    conn: sqlite3.Connection,
    experiment_id: int,
    *,
    date_from: str,
    date_to: str,
) -> int:
    exp = get_experiment(conn, experiment_id)
    if exp is None:
        raise ValueError("Experiment không tồn tại")
    target = (exp.get("target_url") or "").strip()
    if not target:
        raise ValueError("Thiếu target_url")
    customer_id = int(exp["customer_id"])
    rows = conn.execute(
        """
        SELECT stat_date, SUM(clicks) AS clicks, SUM(impressions) AS impressions
        FROM seo_gsc_daily_stats
        WHERE customer_id = ? AND page = ? AND stat_date >= ? AND stat_date <= ?
        GROUP BY stat_date
        ORDER BY stat_date
        """,
        (customer_id, target, date_from, date_to),
    ).fetchall()
    count = 0
    for row in rows:
        d = dict(row)
        stat_date = str(d["stat_date"])[:10]
        upsert_observation(
            conn,
            experiment_id,
            variant_key="control",
            metric_date=stat_date,
            metric_name="clicks",
            metric_value=float(d["clicks"] or 0),
            source="gsc",
        )
        upsert_observation(
            conn,
            experiment_id,
            variant_key="control",
            metric_date=stat_date,
            metric_name="impressions",
            metric_value=float(d["impressions"] or 0),
            source="gsc",
        )
        count += 2
    return count


def record_decision(
    conn: sqlite3.Connection,
    experiment_id: int,
    *,
    decision: str,
    rationale: str = "",
    decided_by: str = "",
) -> dict[str, Any]:
    allowed = {"ship", "rollback", "iterate", "inconclusive"}
    if decision not in allowed:
        raise ValueError(f"Decision không hợp lệ: {decision}")
    conn.execute(
        """
        INSERT INTO seo_experiment_decisions (experiment_id, decision, rationale, decided_by, decided_at)
        VALUES (?,?,?,?,?)
        """,
        (experiment_id, decision, rationale, decided_by, _ts()),
    )
    conn.commit()
    if decision in {"ship", "rollback", "inconclusive"}:
        transition_experiment(conn, experiment_id, "completed", actor_id=decided_by)
    item = get_experiment(conn, experiment_id)
    assert item is not None
    return item
