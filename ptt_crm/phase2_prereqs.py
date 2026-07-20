"""Phase 2 gate prerequisites — auto-fix common blockers before cutover checks."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def ensure_domain_events_idempotency(*, apply: bool = True) -> dict[str, Any]:
    """Ensure domain_events.idempotency_key exists (Nest LeadCreated/LeadAssigned)."""
    from ptt_crm.pg_schema import (
        apply_ddl_v3_events_idempotency,
        pg_domain_events_idempotency_ready,
        pg_events_idempotency_migration_applied,
    )

    if pg_domain_events_idempotency_ready() and pg_events_idempotency_migration_applied():
        return {"ok": True, "applied": False, "reason": "already_ready"}

    if not apply:
        return {"ok": False, "applied": False, "reason": "idempotency_missing"}

    try:
        apply_ddl_v3_events_idempotency()
    except Exception as exc:
        logger.exception("apply idempotency ddl failed: %s", exc)
        return {"ok": False, "applied": False, "error": str(exc)}

    ready = pg_domain_events_idempotency_ready() and pg_events_idempotency_migration_applied()
    return {"ok": ready, "applied": True, "reason": "applied" if ready else "apply_failed"}


def ensure_shadow_sync_repair(*, limit: int = 500) -> dict[str, Any]:
    """Backfill PG nest/staging writes missing from SQLite shadow."""
    from ptt_crm.lead_shadow_sync import sync_shadow_repair_gaps

    return sync_shadow_repair_gaps(limit=limit)


def ensure_ingest_rules_snapshot(*, sync_from_sqlite: bool = True) -> dict[str, Any]:
    """Ensure PG ingest rules snapshot exists and is populated."""
    from ptt_crm.lead_ingest_config import (
        fetch_pg_ingest_rules_snapshot,
        pg_ingest_rules_ready,
        snapshot_has_rules,
        sync_ingest_rules_from_sqlite,
    )
    from ptt_crm.pg_schema import apply_ddl_v3_leads_ingest_config, pg_ingest_rules_migration_applied

    if not pg_ingest_rules_ready():
        apply_ddl_v3_leads_ingest_config()
    snap = fetch_pg_ingest_rules_snapshot()
    if sync_from_sqlite and not snapshot_has_rules(snap):
        out = sync_ingest_rules_from_sqlite()
        out["applied_ddl"] = not pg_ingest_rules_migration_applied()
        return out
    return {
        "ok": True,
        "populated": snapshot_has_rules(snap),
        "migration_applied": pg_ingest_rules_migration_applied(),
    }


def ensure_phase2_write_gates(*, repair_shadow: bool = True) -> dict[str, Any]:
    """Run all automated fixes before write dual-run / UAT gates."""
    steps: dict[str, Any] = {}
    steps["domain_events_idempotency"] = ensure_domain_events_idempotency(apply=True)
    steps["ingest_rules_snapshot"] = ensure_ingest_rules_snapshot(sync_from_sqlite=True)
    if repair_shadow:
        steps["shadow_repair"] = ensure_shadow_sync_repair()
    failed = [name for name, result in steps.items() if not result.get("ok")]
    return {"ok": len(failed) == 0, "failed_steps": failed, "steps": steps}
