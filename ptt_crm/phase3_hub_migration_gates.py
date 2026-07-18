"""Phase 3 Hub PG migration gate pack (Track D1–D4)."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"
DEFAULT_CAMPAIGN_CODE = "HUB-GATE-DEMO"


def _artifacts_dir() -> Path:
    return Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sqlite_path() -> Path:
    raw = (os.environ.get("PTT_SQLITE_PATH") or "ptt.db").strip()
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _run_unittest(module: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", module],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
    }


def verify_d1_ddl_and_read() -> dict[str, Any]:
    from ptt_crm.hub_pg_read import list_hub_campaigns, pg_hub_campaigns_ready
    from ptt_crm.pg_schema import pg_hub_sop_ready

    ddl_ok = pg_hub_sop_ready() and pg_hub_campaigns_ready()
    os.environ["PTT_HUB_READ_SOURCE"] = "1"
    campaigns = list_hub_campaigns(active_only=True, limit=50)
    demo = next((c for c in campaigns if c.get("code") == DEFAULT_CAMPAIGN_CODE), None)
    ok = ddl_ok and len(campaigns) >= 1 and demo is not None
    return {
        "id": "D3-D01",
        "ok": ok,
        "label": "D1 Hub PG read API (DDL + list_hub_campaigns)",
        "ddl_ready": ddl_ok,
        "campaign_count": len(campaigns),
        "demo_campaign": demo,
    }


def verify_d1_dual_write() -> dict[str, Any]:
    os.environ["PTT_HUB_PG_PRIMARY"] = "1"
    db = _sqlite_path()
    if not db.is_file():
        return {"id": "D3-D02", "ok": False, "label": "D1 Hub PG dual-write", "error": "sqlite_missing"}

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM crm_campaigns WHERE lower(trim(code)) = lower(trim(?))",
            (DEFAULT_CAMPAIGN_CODE,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"id": "D3-D02", "ok": False, "label": "D1 Hub PG dual-write", "error": "seed_campaign_missing"}

    from ptt_crm.hub_pg_write import upsert_hub_campaign_from_sqlite

    out = upsert_hub_campaign_from_sqlite(dict(row))
    ok = bool(out and out.get("pg_id") and out.get("sqlite_campaign_id") == int(row["id"]))
    return {
        "id": "D3-D02",
        "ok": ok,
        "label": "D1 Hub PG dual-write (upsert_hub_campaign_from_sqlite)",
        "upsert": out,
    }


def verify_d2_migrate_parity() -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    db = _sqlite_path()
    if not db.is_file():
        return {"id": "D3-D03", "ok": False, "label": "D2 SQLite → PG backfill parity", "error": "sqlite_missing"}

    conn = sqlite3.connect(str(db))
    try:
        sqlite_hub = int(conn.execute("SELECT COUNT(*) FROM crm_campaigns").fetchone()[0])
        sqlite_tpl = int(conn.execute("SELECT COUNT(*) FROM crm_sop_templates").fetchone()[0])
        sqlite_runs = int(conn.execute("SELECT COUNT(*) FROM crm_sop_runs").fetchone()[0])
    finally:
        conn.close()

    with pg_connection() as pg:
        with pg.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM hub_campaigns")
            pg_hub = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM sop_templates")
            pg_tpl = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM sop_runs")
            pg_runs = int(cur.fetchone()[0])

    ok = pg_hub >= sqlite_hub >= 1 and pg_tpl >= sqlite_tpl >= 1 and pg_runs >= sqlite_runs
    return {
        "id": "D3-D03",
        "ok": ok,
        "label": "D2 SQLite → PG backfill parity",
        "sqlite": {"hub_campaigns": sqlite_hub, "sop_templates": sqlite_tpl, "sop_runs": sqlite_runs},
        "postgres": {"hub_campaigns": pg_hub, "sop_templates": pg_tpl, "sop_runs": pg_runs},
    }


def verify_d3_sop_read() -> dict[str, Any]:
    os.environ["PTT_SOP_READ_SOURCE"] = "1"
    from ptt_crm.sop_pg_read import list_sop_runs, list_sop_templates, pg_sop_ready

    if not pg_sop_ready():
        return {"id": "D3-D04", "ok": False, "label": "D3 SOP PG read", "error": "sop_ddl_not_ready"}

    templates = list_sop_templates(active_only=True)
    runs = list_sop_runs(limit=20)
    ok = len(templates) >= 1
    return {
        "id": "D3-D04",
        "ok": ok,
        "label": "D3 SOP PG read (templates + runs)",
        "template_count": len(templates),
        "run_count": len(runs),
        "sample_template": templates[0] if templates else None,
    }


def verify_d1_hub_map_pg(client_id: str) -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int FROM hub_campaign_map
                WHERE client_id = %s::uuid AND active IS TRUE
                """,
                (client_id,),
            )
            count = int(cur.fetchone()[0] or 0)
    ok = count >= 1
    return {
        "id": "D3-D05",
        "ok": ok,
        "label": "D1 hub_campaign_map PG CRUD (existing rows)",
        "active_map_rows": count,
        "client_id": client_id,
    }


def verify_d4_shadow_sunset() -> dict[str, Any]:
    runbook = ROOT / "docs/runbooks/lead-shadow-sunset.md"
    os.environ["PTT_LEAD_SHADOW_SYNC"] = "0"
    from ptt_crm.config import lead_shadow_sync_enabled
    from ptt_crm.lead_shadow_sync import sync_shadow_full, sync_shadow_incremental

    disabled = not lead_shadow_sync_enabled()
    inc = sync_shadow_incremental()
    full = sync_shadow_full(max_batches=1)
    skipped = bool(inc.get("skipped")) and bool(full.get("skipped"))
    ok = disabled and skipped and runbook.is_file()
    return {
        "id": "D3-D06",
        "ok": ok,
        "label": "D4 Lead shadow off (flag + runbook)",
        "shadow_sync_enabled": lead_shadow_sync_enabled(),
        "incremental": {k: inc[k] for k in ("ok", "skipped", "reason") if k in inc},
        "full": {k: full[k] for k in ("ok", "skipped", "reason") if k in full},
        "runbook": str(runbook.relative_to(ROOT)),
    }


def verify_flask_hub_api_smoke() -> dict[str, Any]:
    base = (os.environ.get("PTT_FLASK_URL") or os.environ.get("FLASK_URL") or "").rstrip("/")
    if not base:
        return {
            "id": "D3-D07",
            "ok": True,
            "label": "Flask Hub API smoke (optional)",
            "skipped": True,
            "reason": "PTT_FLASK_URL not set",
        }

    def http_json(url: str) -> tuple[int, dict]:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                return exc.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return exc.code, {"error": raw}

    os.environ["PTT_HUB_READ_SOURCE"] = "1"
    os.environ["PTT_SOP_READ_SOURCE"] = "1"
    camp_status, camp = http_json(f"{base}/api/crm/campaigns")
    sop_status, sop = http_json(f"{base}/api/crm/sop/templates")
    camps = camp.get("campaigns") or []
    tpls = sop.get("templates") or []
    ok = (
        camp_status == 200
        and sop_status == 200
        and camp.get("read_source") == "pg"
        and sop.get("read_source") == "pg"
        and len(camps) >= 1
        and len(tpls) >= 1
    )
    return {
        "id": "D3-D07",
        "ok": ok,
        "label": "Flask Hub + SOP API read_source=pg",
        "campaigns_status": camp_status,
        "sop_status": sop_status,
        "campaign_count": len(camps),
        "template_count": len(tpls),
    }


def run_hub_migration_gate_pack(*, client_id: str | None = None) -> dict[str, Any]:
    cid = client_id or os.environ.get("HUB_GATE_CLIENT_ID", DEFAULT_CLIENT)
    artifacts = _artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)

    steps: dict[str, Any] = {
        "unit_tests": {
            "id": "D3-D00",
            "label": "Hub PG migration unit tests",
            **_run_unittest("tests.test_hub_pg_migration"),
        },
        "d1_read_api": verify_d1_ddl_and_read(),
        "d1_dual_write": verify_d1_dual_write(),
        "d2_migrate_parity": verify_d2_migrate_parity(),
        "d3_sop_read": verify_d3_sop_read(),
        "d1_hub_map": verify_d1_hub_map_pg(cid),
        "d4_shadow_sunset": verify_d4_shadow_sunset(),
        "flask_smoke": verify_flask_hub_api_smoke(),
    }
    required = [k for k in steps if k != "flask_smoke"]
    all_ok = all(bool(steps[k].get("ok")) for k in required)
    report = {
        "phase": "phase3_hub_pg_migration",
        "generated_at": _now_iso(),
        "client_id": cid,
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "total": len(required),
            "passed": sum(1 for k in required if steps[k].get("ok")),
            "failed": [k for k in required if not steps[k].get("ok")],
        },
    }
    out = artifacts / "phase3-hub-migration-gate-report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main() -> int:
    report = run_hub_migration_gate_pack()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
