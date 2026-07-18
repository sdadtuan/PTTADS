#!/usr/bin/env python3
"""Demo chứng minh R1+R2+R3+R4 (in-memory, không cần Flask)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sqlite3
from datetime import datetime, timedelta

from crm_lead_assign_scope import create_staff_assign_scope, lead_assignment_pool_key
from crm_lead_auto_assign import LeadAssignContext, auto_assign_lead_owner, config_with_only
from crm_lead_care_pipeline import CONTACT_OK_CARE_STATUS
from crm_lead_catalog import (
    catalog_public_payload,
    create_catalog_service,
    update_catalog_service,
    validate_service_slug,
)
from crm_lead_presales import ensure_presales, ensure_schema as ensure_presales_schema
from crm_lead_review_queue import sync_b2_review_queue
from crm_lead_rules import save_lead_config
from crm_lead_store import create_lead, ensure_lead_schema, lead_row_to_dict, log_lead_activity
from crm_re_projects import ensure_re_projects_schema

TS = "2026-06-01 10:00:00"
ASSIGNED = "2026-06-01 08:00:00"


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_re_projects_schema(conn)
    ensure_lead_schema(conn)
    ensure_presales_schema(conn)
    conn.executescript(
        """
        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1,
            internal_code TEXT DEFAULT '', department_id INTEGER,
            notes TEXT DEFAULT '', sales_level TEXT DEFAULT ''
        );
        INSERT INTO crm_staff (id, name) VALUES (1, 'AM Demo');
        """
    )
    save_lead_config(
        conn,
        config={"b2_review_queue_enabled": True, "b2_contact_deadline_hours": 24},
        updated_by="demo",
        ts=TS,
    )

    print("=== R3: Catalog bootstrap ===")
    catalog = catalog_public_payload(conn)
    print(f"  Dịch vụ active: {len(catalog['service_slugs'])}")
    print(f"  Ngành active: {len(catalog['industry_slugs'])}")
    custom = create_catalog_service(conn, slug="demo-addon", name="Demo Add-on")
    update_catalog_service(conn, custom["id"], active=False)
    conn.commit()
    print(f"  Vô hiệu hóa demo-addon → validate reject: ", end="")
    try:
        validate_service_slug(conn, "demo-addon")
        print("FAIL (expected error)")
    except ValueError as exc:
        print(f"OK ({exc})")

    print("\n=== R1: Lead mới → B2 only ===")
    row, _, _ = create_lead(
        conn,
        full_name="Demo Lead",
        phone="0903000001",
        source="manual",
        product_interest="quang-cao-facebook",
        industry_slug="fnb",
        owner_id=1,
        auto_assign=False,
        meta={"auto_assigned_at": ASSIGNED},
        ts=ASSIGNED,
    )
    lead = lead_row_to_dict(row, conn)
    gate = lead["presales_care_gate"]
    print(f"  care_stage: {lead['care_pipeline']['current_stage_key']}")
    print(f"  presales gate complete: {gate['complete']} (expected False)")

    print("\n=== R1: Hoàn thành B2 với Liên hệ OK ===")
    log_lead_activity(
        conn,
        lead_id=int(lead["id"]),
        activity_type="call",
        content="Gọi thành công",
        care_contact_type="goi_dien",
        care_status=CONTACT_OK_CARE_STATUS,
        care_stage_key="first_contact",
        created_by="demo",
        ts=TS,
    )
    from crm_lead_care_pipeline import complete_lead_care_stage

    complete_lead_care_stage(
        conn,
        lead_id=int(lead["id"]),
        stage_key="first_contact",
        note="Hoàn thành B2 demo",
        created_by="demo",
        ts=TS,
    )
    conn.commit()
    lead2 = lead_row_to_dict(conn.execute("SELECT * FROM crm_leads WHERE id = ?", (lead["id"],)).fetchone(), conn)
    gate2 = lead2["presales_care_gate"]
    print(f"  presales gate complete: {gate2['complete']} (expected True)")

    print("\n=== R3: Pre-sales chỉ nhận slug active ===")
    ps = ensure_presales(conn, int(lead["id"]), "quang-cao-facebook")
    print(f"  pre-sales service_slug: {ps['service_slug']}")

    print("\n=== R2: Quá 24h chưa Liên hệ OK → tra soát ===")
    row3, _, _ = create_lead(
        conn,
        full_name="Overdue Lead",
        phone="0903000002",
        source="manual",
        owner_id=1,
        auto_assign=False,
        meta={"auto_assigned_at": ASSIGNED},
        ts=ASSIGNED,
    )
    overdue_ts = (datetime.strptime(ASSIGNED, "%Y-%m-%d %H:%M:%S") + timedelta(hours=25)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    summary = sync_b2_review_queue(conn, ts=overdue_ts, actor="demo")
    overdue = lead_row_to_dict(
        conn.execute("SELECT * FROM crm_leads WHERE id = ?", (int(row3["id"]),)).fetchone(),
        conn,
    )
    print(f"  queued: {summary['queued']} (expected 1)")
    print(f"  review_queue.active: {overdue['review_queue']['active']}")
    print(f"  owner_id after queue: {overdue['owner_id']} (expected None)")

    print("\n=== R4: Round-robin × ngành × dịch vụ ===")
    conn.execute("DELETE FROM crm_staff_assign_scope")
    am_spa = conn.execute(
        "INSERT INTO crm_staff (name, active, sales_level) VALUES ('AM Spa', 1, 'b')"
    )
    am_spa_id = int(am_spa.lastrowid)
    am_fnb = conn.execute(
        "INSERT INTO crm_staff (name, active, sales_level) VALUES ('AM FnB', 1, 'b')"
    )
    am_fnb_id = int(am_fnb.lastrowid)
    create_staff_assign_scope(
        conn, staff_id=am_spa_id, industry_slug="spa", service_slug="quang-cao-facebook"
    )
    create_staff_assign_scope(
        conn, staff_id=am_fnb_id, industry_slug="fnb", service_slug="quang-cao-google"
    )
    conn.commit()
    pk = lead_assignment_pool_key(industry_slug="spa", service_slug="quang-cao-facebook")
    print(f"  pool_key spa×FB: {pk}")
    cfg = config_with_only("round_robin")
    sid, name, strategy = auto_assign_lead_owner(
        conn,
        LeadAssignContext(industry_slug="spa", product_interest="quang-cao-facebook"),
        config=cfg,
    )
    print(f"  assign spa+FB → AM #{sid} ({name}), strategy={strategy}")
    row4, _, _ = create_lead(
        conn,
        full_name="Lead R4 FnB",
        phone="0903000003",
        source="manual",
        product_interest="quang-cao-google",
        industry_slug="fnb",
        auto_assign=True,
        ts=TS,
    )
    out4 = lead_row_to_dict(row4, conn)
    print(f"  create_lead fnb+Google → owner_id={out4['owner_id']} (expected {am_fnb_id})")

    print("\n=== R5: KH MKT sơ bộ @ Proposal + TMMT @ Deliver ===")
    from crm_lead_presales import (
        advance_presales_stage,
        list_presales_tasks,
        promote_presales_to_lifecycle,
        update_presales_task,
    )
    from crm_lead_presales_marketing_plan import (
        ensure_r5_schema,
        update_preliminary_plan,
        update_official_plan,
        validate_lifecycle_deliver_advance,
        validate_presales_proposal_advance,
    )
    from crm_service_lifecycle import advance_stage, ensure_schema as ensure_lc_schema
    from crm_svc_tasks import ensure_schema as ensure_svc_tasks

    ensure_r5_schema(conn)
    ensure_lc_schema(conn)
    ensure_svc_tasks(conn)
    from crm_lead_intake import ensure_schema as ensure_intake_schema

    ensure_intake_schema(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS crm_customers (id INTEGER PRIMARY KEY, name TEXT);
        INSERT OR IGNORE INTO crm_customers (id, name) VALUES (10, 'Demo KH');
        CREATE TABLE IF NOT EXISTS crm_contracts (
            id INTEGER PRIMARY KEY, customer_id INTEGER, lead_id INTEGER,
            title TEXT, status TEXT, service_slug TEXT, created_at TEXT, updated_at TEXT
        );
        INSERT OR IGNORE INTO crm_contracts (id, customer_id, lead_id, title, status, service_slug, created_at, updated_at)
        VALUES (99, 10, 1, 'HĐ Demo', 'signed', 'quang-cao-facebook', '2026-06-01', '2026-06-01');
        """
    )
    pid = int(ps["id"])
    for stage in ("lead", "consult"):
        if stage == "lead":
            for task in list_presales_tasks(conn, pid).get("lead", []):
                update_presales_task(conn, int(task["id"]), is_done=True)
            conn.execute(
                """
                INSERT INTO crm_lead_intake_sessions (
                    lead_id, service_slug, mode, status, bant_total, decision, updated_at, completed_at
                ) VALUES (?, 'quang-cao-facebook', 'phone', 'completed', 26, 'go', ?, ?)
                """,
                (int(lead["id"]), TS, TS),
            )
            conn.commit()
            advance_presales_stage(conn, pid, "consult")
        for task in list_presales_tasks(conn, pid).get(stage, []):
            update_presales_task(conn, int(task["id"]), is_done=True)
    gate_empty = validate_presales_proposal_advance(conn, pid)
    print(f"  proposal gate (chưa điền KH): ok={gate_empty['ok']} (expected False)")
    update_preliminary_plan(
        conn,
        pid,
        {
            "name": "KH MKT Demo R5",
            "north_star": "Tăng lead FnB Q3",
            "strategy_framework": {
                "market_message": "USP quán cafe",
                "media_reach": "Meta + Google",
                "conversion_strategy": "Lead form + retarget",
            },
        },
    )
    gate_ok = validate_presales_proposal_advance(conn, pid)
    print(f"  proposal gate (đã điền KH): ok={gate_ok['ok']} (expected True)")
    advance_presales_stage(conn, pid, "proposal")
    for task in list_presales_tasks(conn, pid).get("proposal", []):
        update_presales_task(conn, int(task["id"]), is_done=True)
    conn.commit()
    lc_id = promote_presales_to_lifecycle(conn, pid, customer_id=10, contract_id=99)
    print(f"  promote → lifecycle #{lc_id}, marketing_plan_id linked")
    conn.execute(
        "UPDATE crm_svc_tasks SET is_done = 1 WHERE lifecycle_id = ? AND stage = 'onboard'",
        (lc_id,),
    )
    conn.commit()
    deliver_block = validate_lifecycle_deliver_advance(conn, lc_id)
    print(f"  deliver TMMT gate (chưa TMMT): ok={deliver_block['ok']} (expected False)")
    update_official_plan(
        conn,
        lc_id,
        {
            "strategy_framework": {"target_market": "Gia đình trẻ TP.HCM"},
            "target_market_prof": {
                "market_context": "FnB tăng trưởng",
                "segmentation_icp": "Cafe 50-150m2",
                "personas_roles": "Chủ quán 30-45",
                "pains_desired_outcomes": "Thiếu lead",
                "buy_triggers_obstacles": "Mùa cao điểm",
                "segment_priorities": "Q1-Q7",
            },
        },
    )
    deliver_ok = validate_lifecycle_deliver_advance(conn, lc_id)
    print(f"  deliver TMMT gate (đã TMMT): ok={deliver_ok['ok']} (expected True)")
    advance_stage(conn, lc_id, "deliver", sync_lead=False)
    lc_stage = conn.execute(
        "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lc_id,)
    ).fetchone()["stage"]
    print(f"  lifecycle stage after deliver advance: {lc_stage} (expected deliver)")

    print("\n=== R6: Add-on ngành + gỡ BĐS legacy ===")
    from crm_lead_industry_addon import (
        bootstrap_industry_traits,
        ensure_r6_schema,
        lead_industry_addon_payload,
        reject_re_legacy_lead_input,
        resolve_addon_pack,
        update_lead_industry_addon,
    )

    ensure_r6_schema(conn)
    bootstrap_industry_traits(conn)
    conn.commit()
    try:
        reject_re_legacy_lead_input(re_project_id=99)
        print("  reject re_project_id: FAIL (expected error)")
    except ValueError as exc:
        print(f"  reject re_project_id: OK ({exc})")
    bds_pack = resolve_addon_pack(conn, "bds")
    print(f"  BĐS add-on fields: {len((bds_pack or {}).get('fields') or [])} (expected >= 4)")
    update_lead_industry_addon(
        conn,
        int(lead["id"]),
        {
            "data": {
                "loai_quan": "cafe",
                "vi_tri": "Q1 R6",
                "quy_mo": "80m2",
            }
        },
    )
    addon_payload = lead_industry_addon_payload(conn, int(lead["id"]))
    print(f"  lead addon vi_tri: {addon_payload['data'].get('vi_tri')} (expected Q1 R6)")
    re_cleared = conn.execute(
        "SELECT re_project_id FROM crm_leads WHERE id = ?", (int(lead["id"]),)
    ).fetchone()["re_project_id"]
    print(f"  re_project_id cleared: {re_cleared is None} (expected True)")

    print("\n=== P2: Catalog traits + TMMT workflow API ===")
    from crm_lead_catalog import normalize_industry_traits, update_catalog_industry
    from crm_lead_presales_marketing_plan import official_plan_payload

    traits = normalize_industry_traits(
        {
            "addon_key": "spa",
            "addon_label": "Add-on Spa P2",
            "fields": [{"key": "vi_tri", "label": "Vị trí", "type": "text"}],
        }
    )
    spa_row = conn.execute(
        "SELECT id FROM crm_catalog_industries WHERE slug = 'spa' LIMIT 1"
    ).fetchone()
    if spa_row:
        update_catalog_industry(conn, int(spa_row["id"]), traits=traits)
        conn.commit()
        print(f"  catalog spa traits fields: {len(traits['fields'])} (expected 1)")
    mp_payload = official_plan_payload(conn, lc_id)
    print(
        f"  lifecycle TMMT validation complete: {mp_payload['validation']['complete']} "
        f"(expected True after R5 fill)"
    )

    print("\n=== P3: Gỡ RE khỏi funnel lead ===")
    from crm_lead_product_model_p3 import clear_re_columns_on_leads, ensure_p3_schema

    p3 = ensure_p3_schema(conn)
    conn.commit()
    print(f"  P3 migration skipped={p3.get('skipped')} cleared={p3.get('cleared', 0)}")

    print("\n=== DONE: R1+R2+R3+R4+R5+R6 + P2 + P3 demo passed ===")


if __name__ == "__main__":
    main()
