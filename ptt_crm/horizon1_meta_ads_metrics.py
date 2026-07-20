"""Horizon 1 — Meta Ads pilot metrics (CPL, spend, leads, webhook ingest)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_pilot_ids() -> list[dict[str, str]]:
    raw = (os.environ.get("HORIZON1_PILOT_CLIENTS") or os.environ.get("HORIZON0_PILOT_CLIENTS") or "").strip()
    pilots: list[dict[str, str]] = []
    if raw:
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = chunk.split(":")
            pilots.append(
                {
                    "client_uuid": parts[0].strip(),
                    "customer_id": parts[1].strip() if len(parts) > 1 else "",
                    "label": parts[2].strip() if len(parts) > 2 else f"Meta pilot {len(pilots) + 1}",
                }
            )
    if not pilots:
        pilots.append({"client_uuid": "", "customer_id": "", "label": "Meta pilot (configure HORIZON1_PILOT_CLIENTS)"})
    return pilots[:2]


def _meta_metrics(cur: Any, client_id: str, days: int) -> dict[str, Any]:
    if not client_id:
        return {"ok": False, "error": "client_uuid_required"}
    cur.execute(
        """
        SELECT
          COALESCE(SUM(dp.spend), 0) AS spend,
          COALESCE(SUM(dp.leads_crm), 0) AS leads
        FROM daily_performance dp
        WHERE dp.client_id = %s::uuid
          AND dp.performance_date >= CURRENT_DATE - (%s || ' days')::interval
          AND dp.channel = 'meta'
        """,
        (client_id, str(days)),
    )
    row = cur.fetchone()
    spend = float(row[0] or 0)
    leads = int(row[1] or 0)
    from ptt_agency.performance import compute_cpl

    cpl = compute_cpl(spend, leads)
    cur.execute(
        """
        SELECT COUNT(*) FROM job_queue
        WHERE job_type LIKE 'lead%%'
          AND created_at >= NOW() - (%s || ' hours')::interval
        """,
        (str(max(24, days * 24)),),
    )
    webhook_jobs = int((cur.fetchone() or [0])[0] or 0)
    return {
        "ok": True,
        "period_days": days,
        "meta_spend_vnd": round(spend, 2),
        "meta_leads_crm": leads,
        "meta_cpl_vnd": cpl,
        "webhook_ingest_jobs": webhook_jobs,
    }


def build_metrics(*, days: int | None = None) -> dict[str, Any]:
    days = int(days or os.environ.get("HORIZON1_METRICS_DAYS", "28"))
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        return {"ok": False, "error": "DATABASE_URL required"}

    import psycopg2

    pilots = _parse_pilot_ids()
    studies: list[dict[str, Any]] = []
    try:
        conn = psycopg2.connect(db_url)
    except Exception as exc:
        return {"ok": False, "error": f"pg_connect: {exc}"}
    try:
        cur = conn.cursor()
        for pilot in pilots:
            meta = _meta_metrics(cur, pilot["client_uuid"], days)
            studies.append(
                {
                    "label": pilot["label"],
                    "client_uuid": pilot["client_uuid"] or None,
                    "generated_at": _now_iso(),
                    "meta": meta,
                    "headline": _headline(meta),
                }
            )
    finally:
        cur.close()
        conn.close()

    art = _artifacts_dir()
    report = {
        "ok": True,
        "horizon": 1,
        "component": "meta_ads_pilot_metrics",
        "generated_at": _now_iso(),
        "period_days": days,
        "studies": studies,
    }
    (art / "horizon1-meta-ads-pilot-metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _update_signoff_pilot_metrics(studies[0]["meta"] if studies else {})
    return report


def _headline(meta: dict[str, Any]) -> str:
    if not meta.get("ok"):
        return "Metrics pending — configure HORIZON1_PILOT_CLIENTS"
    parts: list[str] = []
    if meta.get("meta_spend_vnd"):
        parts.append(f"Spend {meta['meta_spend_vnd']:,.0f} VND")
    if meta.get("meta_leads_crm") is not None:
        parts.append(f"{meta['meta_leads_crm']} leads")
    if meta.get("meta_cpl_vnd") is not None:
        parts.append(f"CPL {meta['meta_cpl_vnd']:,.0f} VND")
    return " · ".join(parts) if parts else "Metrics pending"


def _update_signoff_pilot_metrics(meta: dict[str, Any]) -> None:
    signoff_path = ROOT / "docs" / "evidence" / "horizon1-meta-ads-signoff.json"
    if not signoff_path.is_file():
        return
    try:
        signoff = json.loads(signoff_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    signoff["pilot_metrics"] = {
        "period_days": meta.get("period_days", 28),
        "meta_spend_vnd": meta.get("meta_spend_vnd"),
        "meta_leads_crm": meta.get("meta_leads_crm"),
        "meta_cpl_vnd": meta.get("meta_cpl_vnd"),
        "webhook_ingest_24h": meta.get("webhook_ingest_jobs"),
    }
    signoff_path.write_text(json.dumps(signoff, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else None
    report = build_metrics(days=days)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
