#!/usr/bin/env python3
"""Seed demo daily_performance for Client Portal MVP (T-30 Meta + Google)."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"

CAMPAIGNS = [
    {
        "channel": "meta",
        "external_campaign_id": "camp_demo_meta_summer",
        "external_campaign_name": "Demo Summer Meta",
        "hub_campaign_id": 9101,
        "target_cpl_vnd": 120_000,
        "base_spend": 180_000,
        "base_leads": 2,
    },
    {
        "channel": "google",
        "external_campaign_id": "camp_demo_google_search",
        "external_campaign_name": "Demo Google Search",
        "hub_campaign_id": 9102,
        "target_cpl_vnd": 150_000,
        "base_spend": 220_000,
        "base_leads": 1,
    },
]


def ensure_client(client_id: str) -> None:
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (id, code, name, status)
                VALUES (%s::uuid, 'PORTAL_DEMO', 'Portal Demo Client', 'active')
                ON CONFLICT (id) DO UPDATE SET
                    code = EXCLUDED.code,
                    name = EXCLUDED.name,
                    status = EXCLUDED.status
                """,
                (client_id,),
            )
        conn.commit()


def ensure_hub_maps(client_id: str) -> dict[str, str]:
    from ptt_jobs.db import pg_connection

    map_ids: dict[str, str] = {}
    with pg_connection() as conn:
        with conn.cursor() as cur:
            for c in CAMPAIGNS:
                cur.execute(
                    """
                    INSERT INTO hub_campaign_map (
                        client_id, hub_campaign_id, channel,
                        external_campaign_id, external_campaign_name,
                        target_cpl_vnd, active
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, TRUE
                    )
                    ON CONFLICT (client_id, channel, external_campaign_id) DO UPDATE SET
                        external_campaign_name = EXCLUDED.external_campaign_name,
                        target_cpl_vnd = EXCLUDED.target_cpl_vnd,
                        active = TRUE,
                        updated_at = NOW()
                    RETURNING id::text
                    """,
                    (
                        client_id,
                        c["hub_campaign_id"],
                        c["channel"],
                        c["external_campaign_id"],
                        c["external_campaign_name"],
                        c["target_cpl_vnd"],
                    ),
                )
                map_ids[c["external_campaign_id"]] = str(cur.fetchone()[0])
        conn.commit()
    return map_ids


def seed_performance(client_id: str, days: int) -> int:
    from ptt_jobs.db import pg_connection

    map_ids = ensure_hub_maps(client_id)
    today = date.today()
    rows = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            for offset in range(1, days + 1):
                perf_date = today - timedelta(days=offset)
                for idx, c in enumerate(CAMPAIGNS):
                    spend = c["base_spend"] + (offset % 5) * 12_000 + idx * 8_000
                    leads = max(1, c["base_leads"] + (offset % 3))
                    impressions = 800 + offset * 40 + idx * 200
                    clicks = 20 + offset + idx * 5
                    cur.execute(
                        """
                        INSERT INTO daily_performance (
                            client_id, channel, external_campaign_id, external_campaign_name,
                            hub_campaign_map_id, performance_date, spend, leads_crm,
                            leads_platform, impressions, clicks
                        ) VALUES (
                            %s::uuid, %s, %s, %s, %s::uuid, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (client_id, channel, external_campaign_id, performance_date)
                        DO UPDATE SET
                            external_campaign_name = EXCLUDED.external_campaign_name,
                            hub_campaign_map_id = EXCLUDED.hub_campaign_map_id,
                            spend = EXCLUDED.spend,
                            leads_crm = EXCLUDED.leads_crm,
                            leads_platform = EXCLUDED.leads_platform,
                            impressions = EXCLUDED.impressions,
                            clicks = EXCLUDED.clicks,
                            synced_at = NOW()
                        """,
                        (
                            client_id,
                            c["channel"],
                            c["external_campaign_id"],
                            c["external_campaign_name"],
                            map_ids[c["external_campaign_id"]],
                            perf_date.isoformat(),
                            spend,
                            leads,
                            max(0, leads - 1),
                            impressions,
                            clicks,
                        ),
                    )
                    rows += 1
        conn.commit()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed portal demo performance data")
    parser.add_argument("--client-id", default=os.environ.get("PORTAL_DEMO_CLIENT_ID", DEFAULT_CLIENT))
    parser.add_argument("--days", type=int, default=int(os.environ.get("PORTAL_DEMO_DAYS", "30")))
    args = parser.parse_args()

    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency",
    )
    ensure_client(args.client_id)
    n = seed_performance(args.client_id, max(1, args.days))
    print(f"OK  Seeded {n} daily_performance rows for client {args.client_id} (T-{args.days})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
