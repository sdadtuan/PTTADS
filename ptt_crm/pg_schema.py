"""PostgreSQL crm_leads read replica schema helpers (Phase 1b Bước 5)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DDL_V2_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v2-leads.sql")
DDL_V3_OLTP_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v3-leads-oltp.sql")
DDL_V3_PERF_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v3-performance.sql")
DDL_V3_EVENTS_IDEM_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v3-domain-events-idempotency.sql")
DDL_V3_SPRINT0_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v3-sprint0-w5-prod-id.sql")
DDL_V3_CREATIVES_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v3-creatives.sql")
DDL_V3_LAUNCH_QA_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v3-launch-qa.sql")
DDL_V3_GOOGLE_SYNC_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v3-google-sync.sql")
DDL_V4_HUB_SOP_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v4-hub-sop.sql")
DDL_V5_CAMPAIGN_WRITES_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v5-campaign-writes.sql")
DDL_V3_INGEST_CONFIG_REL = Path("docs/specs/2026-07-17-postgresql-ddl-v3-leads-ingest-config.sql")
KPI_DICTIONARY_SEED_REL = Path("docs/specs/2026-07-17-kpi-dictionary-seed.sql")
MIGRATION_VERSION = "2026-07-17-v2-leads"
MIGRATION_V3_OLTP = "2026-07-17-v3-leads-oltp"
MIGRATION_V3_PERF = "2026-07-17-v3-performance"
MIGRATION_V3_EVENTS_IDEM = "2026-07-17-v3-ev-idem"
MIGRATION_V3_SPRINT0 = "2026-07-17-v3-sprint0"
MIGRATION_V3_CREATIVES = "2026-07-17-v3-creatives"
MIGRATION_V3_LAUNCH_QA = "2026-07-17-v3-launch-qa"
MIGRATION_V3_GOOGLE_SYNC = "2026-07-17-v3-google-sync"
MIGRATION_V4_HUB_SOP = "2026-07-17-v4-hub-sop"
MIGRATION_V5_CAMPAIGN_WRITES = "2026-07-17-v5-campaign-writes"
MIGRATION_V3_INGEST_CONFIG = "2026-07-17-v3-ingest"

CRM_LEADS_COLUMNS: tuple[str, ...] = (
    "sqlite_lead_id",
    "full_name",
    "phone",
    "email",
    "status",
    "source",
    "owner_id",
    "is_duplicate",
    "meta_json",
    "agency_client_id",
    "channel",
    "external_lead_id",
    "campaign_id",
    "received_at",
    "created_at",
    "synced_at",
    "sync_version",
)


def ddl_v2_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V2_REL


def ddl_v3_oltp_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V3_OLTP_REL


def ddl_v3_perf_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V3_PERF_REL


def ddl_v3_events_idempotency_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V3_EVENTS_IDEM_REL


def ddl_v3_sprint0_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V3_SPRINT0_REL


def ddl_v3_creatives_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V3_CREATIVES_REL


def ddl_v3_launch_qa_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V3_LAUNCH_QA_REL


def ddl_v3_google_sync_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V3_GOOGLE_SYNC_REL


def ddl_v4_hub_sop_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V4_HUB_SOP_REL


def ddl_v5_campaign_writes_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V5_CAMPAIGN_WRITES_REL


def ddl_v3_leads_ingest_config_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base / DDL_V3_INGEST_CONFIG_REL


def _apply_sql_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    sql = path.read_text(encoding="utf-8")
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)


def pg_leads_replica_ready() -> bool:
    """True when crm_leads + sync_state exist on PostgreSQL."""
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN ('crm_leads', 'crm_leads_sync_state')
                    """
                )
                row = cur.fetchone()
                return int(row[0] or 0) >= 2
    except Exception as exc:
        logger.debug("pg_leads_replica_ready: %s", exc)
        return False


def pg_leads_migration_applied() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s LIMIT 1",
                    (MIGRATION_VERSION,),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def pg_leads_stats() -> dict[str, Any]:
    """Row counts for Agency dashboard / health."""
    out: dict[str, Any] = {"ready": False, "rows": 0, "last_sqlite_id": 0}
    if not pg_leads_replica_ready():
        return out
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM crm_leads WHERE is_duplicate IS NOT TRUE")
                out["rows"] = int(cur.fetchone()[0] or 0)
                cur.execute(
                    "SELECT last_sqlite_id, last_sync_at, rows_total FROM crm_leads_sync_state WHERE id = 1"
                )
                sync = cur.fetchone()
                if sync:
                    out["last_sqlite_id"] = int(sync[0] or 0)
                    out["last_sync_at"] = sync[1].isoformat() if sync[1] else None
                    out["rows_total"] = int(sync[2] or 0)
        out["ready"] = True
    except Exception as exc:
        out["error"] = str(exc)
    return out


def pg_row_to_v1(row: dict[str, Any]) -> dict[str, Any]:
    """Map PG crm_leads row → LeadV1 (for Bước 7 Nest PG read)."""

    def _fmt_ts(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            dt = value
            if getattr(dt, "hour", 0) == 0 and getattr(dt, "minute", 0) == 0 and getattr(dt, "second", 0) == 0:
                return dt.date().isoformat()
            text = dt.isoformat()
            return text.replace("+00:00", "Z") if text.endswith("+00:00") else text
        return str(value)

    received = row.get("received_at")
    created = row.get("created_at")
    return {
        "id": int(row["sqlite_lead_id"]),
        "full_name": row.get("full_name") or "",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "status": row.get("status") or "",
        "source": row.get("source") or "",
        "channel": row.get("channel") or "",
        "client_id": str(row["agency_client_id"]) if row.get("agency_client_id") else None,
        "campaign_id": row.get("campaign_id") or None,
        "external_lead_id": row.get("external_lead_id") or None,
        "owner_id": int(row["owner_id"]) if row.get("owner_id") is not None else None,
        "created_at": _fmt_ts(created),
        "received_at": _fmt_ts(received),
        "is_duplicate": bool(row.get("is_duplicate")),
    }


def apply_ddl_v2(*, ddl_path: Path | None = None) -> bool:
    """Apply v2 migration SQL via psycopg2 (idempotent)."""
    _apply_sql_file(ddl_path or ddl_v2_path())
    return True


def pg_v3_migration_applied() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM schema_migrations
                    WHERE version IN (%s, %s)
                    """,
                    (MIGRATION_V3_OLTP, MIGRATION_V3_PERF),
                )
                return int(cur.fetchone()[0] or 0) >= 2
    except Exception:
        return False


def pg_shadow_ready() -> bool:
    """True when Phase 2 shadow watermark table exists."""
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'crm_leads_shadow_state'
                    """
                )
                return int(cur.fetchone()[0] or 0) >= 1
    except Exception as exc:
        logger.debug("pg_shadow_ready: %s", exc)
        return False


def pg_v3_ready() -> bool:
    """True when Phase 2 OLTP + performance tables exist."""
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        required = (
            "crm_lead_assignment_log",
            "hub_campaign_map",
            "daily_performance",
            "metrics_snapshots",
        )
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = ANY(%s)
                    """,
                    (list(required),),
                )
                return int(cur.fetchone()[0] or 0) >= len(required)
    except Exception as exc:
        logger.debug("pg_v3_ready: %s", exc)
        return False


def apply_ddl_v3(*, oltp_path: Path | None = None, perf_path: Path | None = None) -> bool:
    """Apply v3 OLTP + performance migrations via psycopg2 (idempotent)."""
    _apply_sql_file(oltp_path or ddl_v3_oltp_path())
    _apply_sql_file(perf_path or ddl_v3_perf_path())
    return True


def pg_domain_events_idempotency_ready() -> bool:
    """True when domain_events.idempotency_key column exists."""
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'domain_events'
                      AND column_name = 'idempotency_key'
                    """
                )
                return int(cur.fetchone()[0] or 0) >= 1
    except Exception as exc:
        logger.debug("pg_domain_events_idempotency_ready: %s", exc)
        return False


def pg_events_idempotency_migration_applied() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s LIMIT 1",
                    (MIGRATION_V3_EVENTS_IDEM,),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def apply_ddl_v3_events_idempotency(*, ddl_path: Path | None = None) -> bool:
    """Apply domain_events idempotency migration (Phase 2 P1)."""
    _apply_sql_file(ddl_path or ddl_v3_events_idempotency_path())
    return True


def pg_sprint0_ready() -> bool:
    """True when W5 prod id sequence exists."""
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relkind = 'S' AND c.relname = 'crm_leads_prod_id_seq'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.debug("pg_sprint0_ready: %s", exc)
        return False


def pg_sprint0_migration_applied() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s LIMIT 1",
                    (MIGRATION_V3_SPRINT0,),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def apply_ddl_v3_sprint0(*, ddl_path: Path | None = None) -> bool:
    """Apply Sprint 0 DDL — W5 prod id seq + portal_client_users."""
    _apply_sql_file(ddl_path or ddl_v3_sprint0_path())
    return True


def pg_ingest_rules_migration_applied() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s LIMIT 1",
                    (MIGRATION_V3_INGEST_CONFIG,),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def apply_ddl_v3_leads_ingest_config(*, ddl_path: Path | None = None) -> bool:
    """Apply PG snapshot table for lead ingest rules (Phase 2 cutover)."""
    _apply_sql_file(ddl_path or ddl_v3_leads_ingest_config_path())
    return True


def pg_creatives_ready() -> bool:
    """True when creative_submissions table exists."""
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'creative_submissions'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.debug("pg_creatives_ready: %s", exc)
        return False


def pg_creatives_migration_applied() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s LIMIT 1",
                    (MIGRATION_V3_CREATIVES,),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def apply_ddl_v3_creatives(*, ddl_path: Path | None = None) -> bool:
    """Apply Phase 3 P4 creative_submissions DDL."""
    _apply_sql_file(ddl_path or ddl_v3_creatives_path())
    return True


def pg_launch_qa_ready() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'launch_qa_runs'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.debug("pg_launch_qa_ready: %s", exc)
        return False


def apply_ddl_v3_launch_qa(*, ddl_path: Path | None = None) -> bool:
    _apply_sql_file(ddl_path or ddl_v3_launch_qa_path())
    return True


def pg_google_sync_ready() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'google_insights_sync_state'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.debug("pg_google_sync_ready: %s", exc)
        return False


def apply_ddl_v3_google_sync(*, ddl_path: Path | None = None) -> bool:
    _apply_sql_file(ddl_path or ddl_v3_google_sync_path())
    return True


def pg_hub_sop_ready() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN ('hub_campaigns', 'sop_templates', 'sop_runs')
                    """
                )
                return int(cur.fetchone()[0] or 0) >= 3
    except Exception as exc:
        logger.debug("pg_hub_sop_ready: %s", exc)
        return False


def apply_ddl_v4_hub_sop(*, ddl_path: Path | None = None) -> bool:
    _apply_sql_file(ddl_path or ddl_v4_hub_sop_path())
    return True


def pg_campaign_writes_ready() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'campaign_write_requests'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.debug("pg_campaign_writes_ready: %s", exc)
        return False


def apply_ddl_v5_campaign_writes(*, ddl_path: Path | None = None) -> bool:
    _apply_sql_file(ddl_path or ddl_v5_campaign_writes_path())
    return True


def pg_kpi_definitions_ready(*, min_rows: int = 12) -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'kpi_definitions'
                    """
                )
                if int(cur.fetchone()[0] or 0) == 0:
                    return False
                cur.execute("SELECT COUNT(*)::int FROM kpi_definitions")
                return int(cur.fetchone()[0] or 0) >= min_rows
    except Exception as exc:
        logger.debug("pg_kpi_definitions_ready: %s", exc)
        return False


def apply_kpi_dictionary_seed(*, ddl_path: Path | None = None) -> bool:
    path = ddl_path or (Path(__file__).resolve().parents[1] / KPI_DICTIONARY_SEED_REL)
    _apply_sql_file(path)
    return True
