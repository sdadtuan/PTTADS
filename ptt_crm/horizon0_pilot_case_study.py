"""Horizon 0 — pilot case study metrics (Email open rate, SEO organic, Meta CPL)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
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
    raw = (os.environ.get("HORIZON0_PILOT_CLIENTS") or "").strip()
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
                    "label": parts[2].strip() if len(parts) > 2 else f"Pilot {len(pilots) + 1}",
                }
            )
    if not pilots:
        pilots.append({"client_uuid": "", "customer_id": "", "label": "Pilot 1 (configure HORIZON0_PILOT_CLIENTS)"})
    return pilots[:2]


def _email_metrics(cur: Any, client_id: str, days: int) -> dict[str, Any]:
    if not client_id:
        return {"ok": False, "error": "client_uuid_required"}
    cur.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE sq.status IN ('sent','delivered')) AS sent,
          COUNT(DISTINCT ee.contact_id) FILTER (WHERE ee.event_type = 'open') AS unique_opens,
          COUNT(DISTINCT ee.contact_id) FILTER (WHERE ee.event_type = 'click') AS unique_clicks
        FROM email_mkt.send_queue sq
        LEFT JOIN email_mkt.engagement_events ee ON ee.send_id = sq.id
        WHERE sq.client_id = %s::uuid
          AND sq.created_at >= NOW() - (%s || ' days')::interval
        """,
        (client_id, str(days)),
    )
    row = cur.fetchone()
    sent = int(row[0] or 0)
    opens = int(row[1] or 0)
    clicks = int(row[2] or 0)
    open_rate = round((opens / sent) * 100, 2) if sent else None
    click_rate = round((clicks / sent) * 100, 2) if sent else None
    return {
        "ok": True,
        "period_days": days,
        "sent": sent,
        "unique_opens": opens,
        "unique_clicks": clicks,
        "open_rate_pct": open_rate,
        "click_rate_pct": click_rate,
    }


def _seo_metrics(cur: Any, customer_id: str, days: int) -> dict[str, Any]:
    if not customer_id:
        return {"ok": False, "error": "customer_id_required_for_seo"}
    cur.execute(
        """
        SELECT
          COALESCE(SUM(clicks), 0) AS clicks,
          COALESCE(SUM(impressions), 0) AS impressions,
          COALESCE(SUM(CASE WHEN position <= 10 THEN clicks ELSE 0 END), 0) AS top10_clicks
        FROM seo_aeo.seo_gsc_daily_stats
        WHERE customer_id = %s
          AND stat_date >= CURRENT_DATE - (%s || ' days')::interval
        """,
        (customer_id, str(days)),
    )
    row = cur.fetchone()
    clicks = int(row[0] or 0)
    impressions = int(row[1] or 0)
    ctr = round((clicks / impressions) * 100, 2) if impressions else None
    return {
        "ok": True,
        "period_days": days,
        "organic_clicks": clicks,
        "organic_impressions": impressions,
        "organic_ctr_pct": ctr,
        "top10_clicks": int(row[2] or 0),
    }


def _meta_cpl(cur: Any, client_id: str, days: int) -> dict[str, Any]:
    if not client_id:
        return {"ok": False, "error": "client_uuid_required"}
    try:
        cur.execute(
            """
            SELECT
              COALESCE(SUM(dp.spend), 0) AS spend,
              COALESCE(SUM(dp.leads_crm), 0) AS leads
            FROM daily_performance dp
            JOIN clients c ON c.id = dp.client_id
            WHERE dp.client_id = %s::uuid
              AND dp.performance_date >= CURRENT_DATE - (%s || ' days')::interval
              AND dp.channel = 'meta'
            """,
            (client_id, str(days)),
        )
    except Exception as exc:
        return {"ok": False, "error": f"daily_performance_query: {exc}"}
    row = cur.fetchone()
    spend = float(row[0] or 0)
    leads = int(row[1] or 0)
    from ptt_agency.performance import compute_cpl

    cpl = compute_cpl(spend, leads)
    return {
        "ok": True,
        "period_days": days,
        "meta_spend_vnd": round(spend, 2),
        "meta_leads_crm": leads,
        "meta_cpl_vnd": cpl,
    }


def build_case_studies(*, days: int | None = None) -> dict[str, Any]:
    days = int(days or os.environ.get("HORIZON0_METRICS_DAYS", "28"))
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not db_url:
        return {"ok": False, "error": "DATABASE_URL required"}

    import psycopg2

    pilots = _parse_pilot_ids()
    studies: list[dict[str, Any]] = []
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()
        for pilot in pilots:
            study = {
                "label": pilot["label"],
                "client_uuid": pilot["client_uuid"] or None,
                "customer_id": pilot["customer_id"] or None,
                "generated_at": _now_iso(),
                "email": _email_metrics(cur, pilot["client_uuid"], days),
                "seo": _seo_metrics(cur, pilot["customer_id"], days),
                "meta": _meta_cpl(cur, pilot["client_uuid"], days),
            }
            study["headline"] = _headline(study)
            studies.append(study)
    finally:
        cur.close()
        conn.close()

    out_dir = ROOT / "docs" / "case-studies"
    out_dir.mkdir(parents=True, exist_ok=True)
    art = _artifacts_dir()
    report = {
        "ok": True,
        "generated_at": _now_iso(),
        "period_days": days,
        "studies": studies,
    }
    (art / "horizon0-pilot-case-studies.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for idx, study in enumerate(studies, start=1):
        slug = f"pilot-{idx}"
        md = _render_markdown(study)
        (out_dir / f"{slug}.md").write_text(md, encoding="utf-8")
    (out_dir / "README.md").write_text(_index_markdown(studies), encoding="utf-8")
    return report


def _headline(study: dict[str, Any]) -> str:
    parts: list[str] = []
    email = study.get("email") or {}
    seo = study.get("seo") or {}
    meta = study.get("meta") or {}
    if email.get("open_rate_pct") is not None:
        parts.append(f"Email open {email['open_rate_pct']}%")
    if seo.get("organic_clicks"):
        parts.append(f"{seo['organic_clicks']} organic clicks")
    if meta.get("meta_cpl_vnd") is not None:
        parts.append(f"CPL {meta['meta_cpl_vnd']:,.0f} VND")
    return " · ".join(parts) if parts else "Metrics pending — configure pilot IDs"


def _render_markdown(study: dict[str, Any]) -> str:
    email = study.get("email") or {}
    seo = study.get("seo") or {}
    meta = study.get("meta") or {}
    return f"""# Case study — {study.get('label')}

> Auto-generated by `scripts/generate_horizon0_case_studies.sh` · {_now_iso()}

## Headline

{study.get('headline')}

## Pilot identifiers

| Field | Value |
|-------|-------|
| Client UUID | `{study.get('client_uuid') or '—'}` |
| CRM customer_id | `{study.get('customer_id') or '—'}` |

## Email marketing (EM-OS)

| Metric | Value |
|--------|-------|
| Sent | {email.get('sent', '—')} |
| Unique opens | {email.get('unique_opens', '—')} |
| Open rate | {email.get('open_rate_pct', '—')}% |
| Click rate | {email.get('click_rate_pct', '—')}% |

## SEO / organic (GSC)

| Metric | Value |
|--------|-------|
| Organic clicks | {seo.get('organic_clicks', '—')} |
| Impressions | {seo.get('organic_impressions', '—')} |
| CTR | {seo.get('organic_ctr_pct', '—')}% |

## Meta ads performance

| Metric | Value |
|--------|-------|
| Spend (VND) | {meta.get('meta_spend_vnd', '—')} |
| CRM leads | {meta.get('meta_leads_crm', '—')} |
| CPL (VND) | {meta.get('meta_cpl_vnd', '—')} |

## Narrative (fill after pilot)

- **Challenge:**
- **Approach:**
- **Result:**
- **Client quote:**
"""


def _index_markdown(studies: list[dict[str, Any]]) -> str:
    lines = [
        "# Horizon 0 — Pilot case studies",
        "",
        "Generated metrics for Gate A sales / sign-off evidence.",
        "",
        "| Pilot | Headline | File |",
        "|-------|----------|------|",
    ]
    for idx, study in enumerate(studies, start=1):
        lines.append(f"| {study.get('label')} | {study.get('headline')} | [pilot-{idx}.md](./pilot-{idx}.md) |")
    lines.extend(
        [
            "",
            "## Regenerate",
            "",
            "```bash",
            "export DATABASE_URL=postgresql://...",
            "export HORIZON0_PILOT_CLIENTS='uuid:customer_id:Client Name,uuid2:cid2:Client 2'",
            "./scripts/generate_horizon0_case_studies.sh",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else None
    report = build_case_studies(days=days)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
