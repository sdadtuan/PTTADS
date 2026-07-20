"""A/B experiment engine — subject line variants (EM-12)."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def _ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def assign_variant_key(*, experiment_id: str, contact_id: str, variants: list[dict[str, Any]]) -> str:
    if not variants:
        return "control"
    keys = [str(v.get("variant_key") or "control") for v in variants]
    weights = [max(0, int(v.get("split_pct") or 0)) for v in variants]
    total = sum(weights) or len(keys)
    digest = hashlib.sha256(f"{experiment_id}:{contact_id}".encode()).hexdigest()
    bucket = int(digest[:8], 16) % total
    acc = 0
    for key, weight in zip(keys, weights if sum(weights) else [1] * len(keys)):
        acc += weight if sum(weights) else 1
        if bucket < acc:
            return key
    return keys[0]


def get_running_experiment_for_campaign(campaign_id: str) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT e.id::text, e.client_id::text, e.name, e.experiment_type, e.status, e.config_json
                FROM {SCHEMA}.experiments e
                WHERE e.campaign_id = %s::uuid AND e.status = 'running'
                ORDER BY e.started_at DESC NULLS LAST
                LIMIT 1
                """,
                (campaign_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            exp_id = str(row[0])
            cur.execute(
                f"""
                SELECT variant_key, label, config_json, split_pct
                FROM {SCHEMA}.experiment_variants
                WHERE experiment_id = %s::uuid
                ORDER BY variant_key
                """,
                (exp_id,),
            )
            variants = []
            for vr in cur.fetchall():
                cfg = vr[2] if isinstance(vr[2], dict) else json.loads(vr[2] or "{}")
                variants.append(
                    {
                        "variant_key": str(vr[0]),
                        "label": str(vr[1]),
                        "config": cfg,
                        "split_pct": int(vr[3] or 0),
                    }
                )
            config = row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}")
            return {
                "id": exp_id,
                "client_id": str(row[1]),
                "name": str(row[2]),
                "experiment_type": str(row[3]),
                "status": str(row[4]),
                "config": config,
                "variants": variants,
            }


def resolve_subject_for_contact(
    *,
    campaign_id: str,
    contact_id: str,
    default_subject: str,
) -> tuple[str, dict[str, Any]]:
    exp = get_running_experiment_for_campaign(campaign_id)
    if not exp or exp.get("experiment_type") != "subject" or not exp.get("variants"):
        return default_subject, {}
    variant_key = assign_variant_key(
        experiment_id=exp["id"],
        contact_id=contact_id,
        variants=exp["variants"],
    )
    subject = default_subject
    for v in exp["variants"]:
        if v["variant_key"] == variant_key:
            subject = str(v.get("config", {}).get("subject") or v.get("config", {}).get("subject_template") or subject)
            break
    meta = {"experiment_id": exp["id"], "variant_key": variant_key}
    return subject, meta


def rollup_experiment_metrics(experiment_id: str) -> dict[str, Any]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT e.id::text, e.campaign_id::text, e.config_json
                FROM {SCHEMA}.experiments e WHERE e.id = %s::uuid
                """,
                (experiment_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "experiment_not_found"}
            _exp_id, campaign_id, config_raw = row
            if not campaign_id:
                return {"ok": False, "error": "campaign_required"}
            config = config_raw if isinstance(config_raw, dict) else json.loads(config_raw or "{}")
            winner_metric = str(config.get("winner_metric") or "open_rate")

            cur.execute(
                f"""
                SELECT sq.personalization->>'variant_key' AS variant_key,
                       COUNT(*) FILTER (WHERE sq.status IN ('sent','delivered')) AS sent,
                       COUNT(DISTINCT ee.contact_id) FILTER (WHERE ee.event_type = 'open') AS opens,
                       COUNT(DISTINCT ee.contact_id) FILTER (WHERE ee.event_type = 'click') AS clicks
                FROM {SCHEMA}.send_queue sq
                LEFT JOIN {SCHEMA}.engagement_events ee ON ee.send_id = sq.id
                WHERE sq.campaign_id = %s::uuid
                  AND sq.personalization ? 'variant_key'
                GROUP BY sq.personalization->>'variant_key'
                """,
                (campaign_id,),
            )
            variants: list[dict[str, Any]] = []
            for vr in cur.fetchall():
                variant_key, sent, opens, clicks = vr
                sent_n = int(sent or 0)
                opens_n = int(opens or 0)
                clicks_n = int(clicks or 0)
                open_rate = round((opens_n / sent_n) * 100, 2) if sent_n else 0.0
                click_rate = round((clicks_n / sent_n) * 100, 2) if sent_n else 0.0
                variants.append(
                    {
                        "variant_key": variant_key or "unknown",
                        "sent": sent_n,
                        "opens": opens_n,
                        "clicks": clicks_n,
                        "open_rate": open_rate,
                        "click_rate": click_rate,
                    }
                )
                now = datetime.now(timezone.utc)
                for metric_name, value, sample in (
                    ("sent", sent_n, sent_n),
                    ("opens", opens_n, sent_n),
                    ("clicks", clicks_n, sent_n),
                    ("open_rate", open_rate, sent_n),
                    ("click_rate", click_rate, sent_n),
                ):
                    cur.execute(
                        f"""
                        INSERT INTO {SCHEMA}.experiment_observations (
                          experiment_id, variant_key, metric_name, metric_value, sample_size, observed_at
                        ) VALUES (%s::uuid, %s, %s, %s, %s, %s)
                        ON CONFLICT (experiment_id, variant_key, metric_name, observed_at) DO UPDATE
                          SET metric_value = EXCLUDED.metric_value, sample_size = EXCLUDED.sample_size
                        """,
                        (experiment_id, variant_key or "unknown", metric_name, value, sample, now),
                    )

            winner = None
            if variants:
                if winner_metric == "click_rate":
                    winner = max(variants, key=lambda v: v["click_rate"])
                else:
                    winner = max(variants, key=lambda v: v["open_rate"])
            min_sample = int(config.get("min_sample") or 100)
            winner_key = None
            if winner and winner.get("sent", 0) >= min_sample:
                winner_key = winner["variant_key"]
        conn.commit()

    return {
        "ok": True,
        "experiment_id": experiment_id,
        "variants": variants,
        "winner_metric": winner_metric,
        "winner_variant_key": winner_key,
        "min_sample": min_sample,
    }


def declare_winner(experiment_id: str, *, variant_key: str, actor: str, rationale: str = "") -> dict[str, Any]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {SCHEMA}.experiments
                SET status = 'completed', winner_variant_key = %s, ended_at = NOW(), updated_at = NOW()
                WHERE id = %s::uuid AND status = 'running'
                """,
                (variant_key, experiment_id),
            )
            if cur.rowcount == 0:
                return {"ok": False, "error": "invalid_status_or_not_found"}
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.experiment_decisions (experiment_id, decision, rationale, decided_by)
                VALUES (%s::uuid, %s, %s, %s)
                """,
                (experiment_id, f"winner:{variant_key}", rationale or "", actor),
            )
        conn.commit()
    return {"ok": True, "experiment_id": experiment_id, "winner_variant_key": variant_key}


def start_experiment(experiment_id: str, *, actor: str) -> dict[str, Any]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {SCHEMA}.experiments
                SET status = 'running', started_at = COALESCE(started_at, NOW()), updated_at = NOW()
                WHERE id = %s::uuid AND status IN ('draft', 'running')
                RETURNING campaign_id::text
                """,
                (experiment_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "invalid_status"}
            campaign_id = str(row[0]) if row[0] else None
            if campaign_id:
                cur.execute(
                    f"""
                    UPDATE {SCHEMA}.campaigns
                    SET experiment_config = jsonb_set(
                      COALESCE(experiment_config, '{{}}'::jsonb),
                      '{{enabled}}', 'true'::jsonb, true
                    ),
                    updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (campaign_id,),
                )
        conn.commit()
    return {"ok": True, "experiment_id": experiment_id, "status": "running"}


def enqueue_experiment_rollup(experiment_id: str) -> dict[str, Any]:
    try:
        from ptt_jobs.enqueue import enqueue_job

        job = enqueue_job(
            "email_experiment_rollup",
            {"experiment_id": experiment_id},
            f"email_experiment_rollup:{experiment_id}",
        )
        return {"ok": True, "job": job}
    except Exception as exc:
        logger.warning("inline experiment rollup: %s", exc)
        return rollup_experiment_metrics(experiment_id)
