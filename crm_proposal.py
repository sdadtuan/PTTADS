from __future__ import annotations
import json
import re
import sqlite3
from datetime import datetime
from typing import Any


SERVICE_NAMES: dict[str, str] = {
    "dich-vu-seo-tong-the": "SEO Tổng thể",
    "dich-vu-seo-local": "SEO Local",
    "dich-vu-seo-audit": "SEO Audit",
    "dich-vu-aeo": "AEO (Answer Engine Optimization)",
    "dich-vu-quan-tri-website": "Quản trị Website",
    "thiet-ke-website": "Thiết kế Website",
    "thiet-ke-website-tron-goi": "Thiết kế Website Trọn gói",
    "thiet-ke-landing-page": "Thiết kế Landing Page",
    "quang-cao-facebook": "Quảng cáo Facebook",
    "quang-cao-google": "Quảng cáo Google",
    "thue-tai-khoan-quang-cao": "Thuê tài khoản Quảng cáo",
    "tiep-thi-noi-dung": "Tiếp thị Nội dung",
}


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _extract_section(text: str, header: str) -> str:
    pattern = rf"## {re.escape(header)}\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS crm_proposals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            lifecycle_id    INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE SET NULL,
            service_slugs   TEXT NOT NULL DEFAULT '[]',
            total_vnd       INTEGER NOT NULL DEFAULT 0,
            timeline_months INTEGER NOT NULL DEFAULT 1,
            notes           TEXT NOT NULL DEFAULT '',
            ai_output       TEXT NOT NULL DEFAULT '{}',
            created_at      TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_crm_proposals_customer ON crm_proposals (customer_id);
    """)


def create_proposal(
    conn: sqlite3.Connection,
    customer_id: int,
    service_slugs: list[str],
    total_vnd: int,
    timeline_months: int,
    notes: str,
    *,
    lifecycle_id: int | None = None,
) -> int:
    ts = _ts()
    cur = conn.execute(
        """INSERT INTO crm_proposals
           (customer_id, lifecycle_id, service_slugs, total_vnd, timeline_months, notes, ai_output, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (customer_id, lifecycle_id, json.dumps(service_slugs), total_vnd, timeline_months, notes, "{}", ts, ts),
    )
    conn.commit()
    return cur.lastrowid


def list_proposals(conn: sqlite3.Connection, customer_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM crm_proposals WHERE customer_id = ? ORDER BY id DESC",
        (customer_id,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["service_slugs"] = json.loads(d.get("service_slugs") or "[]")
        _ao = d.get("ai_output", "{}")
        try:
            d["generated"] = any(json.loads(_ao).values())
        except Exception:
            d["generated"] = False
        result.append(d)
    return result


def get_proposal(conn: sqlite3.Connection, proposal_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM crm_proposals WHERE id = ?",
        (proposal_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["service_slugs"] = json.loads(d.get("service_slugs") or "[]")
    d["ai_output"] = json.loads(d.get("ai_output") or "{}")
    return d


def delete_proposal(conn: sqlite3.Connection, proposal_id: int) -> None:
    conn.execute("DELETE FROM crm_proposals WHERE id = ?", (proposal_id,))
    conn.commit()


def _resolve_lifecycle_for_consult(
    conn: sqlite3.Connection,
    customer_id: int,
    lifecycle_id: int | None = None,
) -> int | None:
    if lifecycle_id:
        row = conn.execute(
            """
            SELECT id FROM crm_service_lifecycle
            WHERE id = ? AND customer_id = ?
            """,
            (int(lifecycle_id), int(customer_id)),
        ).fetchone()
        return int(row[0]) if row else None
    row = conn.execute(
        """
        SELECT lc.id
        FROM crm_service_lifecycle lc
        JOIN crm_svc_tasks t ON t.lifecycle_id = lc.id AND t.stage = 'consult'
        WHERE lc.customer_id = ?
        ORDER BY lc.id DESC
        LIMIT 1
        """,
        (int(customer_id),),
    ).fetchone()
    return int(row[0]) if row else None


def _load_consult_task_context(
    conn: sqlite3.Connection,
    lifecycle_id: int,
) -> dict[str, Any] | None:
    from crm_svc_tasks import list_tasks

    tasks_by_stage = list_tasks(conn, int(lifecycle_id))
    consult_tasks = tasks_by_stage.get("consult") or []
    if not consult_tasks:
        return None
    task = consult_tasks[0]
    ctx: dict[str, Any] = {
        "lifecycle_id": int(lifecycle_id),
        "task_id": int(task["id"]),
        "title": str(task.get("title") or ""),
        "form_data": dict(task.get("form_data") or {}),
        "ai_output": str(task.get("ai_output") or ""),
        "notes": str(task.get("notes") or ""),
        "is_done": bool(task.get("is_done")),
    }
    try:
        from crm_svc_consult_bridge import get_consult_brief

        brief = get_consult_brief(conn, int(lifecycle_id))
        readiness = brief.get("readiness") or {}
        ctx["intake_summary"] = str(brief.get("latest_intake_summary") or "")[:2500]
        ctx["bant_total"] = int(readiness.get("bant_total") or 0)
        ctx["decision"] = str(readiness.get("decision") or "")
        ctx["highlights"] = brief.get("highlights") or {}
    except Exception:
        ctx.setdefault("intake_summary", "")
        ctx.setdefault("bant_total", 0)
        ctx.setdefault("decision", "")
        ctx.setdefault("highlights", {})
    return ctx


def get_customer_context(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    lifecycle_id: int | None = None,
) -> dict:
    customer_row = conn.execute(
        "SELECT name, company, address, phone, email FROM crm_customers WHERE id = ?",
        (customer_id,),
    ).fetchone()
    customer = dict(customer_row) if customer_row else {
        "name": "", "company": "", "address": "", "phone": "", "email": "",
    }

    lead_row = conn.execute(
        "SELECT product_interest, need FROM crm_leads WHERE converted_customer_id = ? ORDER BY id DESC LIMIT 1",
        (customer_id,),
    ).fetchone()
    lead = dict(lead_row) if lead_row else None

    contract_row = conn.execute(
        "SELECT COUNT(*) as count, COALESCE(SUM(amount_vnd), 0) as total_vnd FROM crm_contracts WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    contracts = {
        "count": contract_row["count"] if contract_row else 0,
        "total_vnd": contract_row["total_vnd"] if contract_row else 0,
    }

    past_rows = conn.execute(
        "SELECT DISTINCT service_slug FROM crm_service_lifecycle WHERE customer_id = ?",
        (customer_id,),
    ).fetchall()
    past_service_slugs = [r["service_slug"] for r in past_rows]

    active_rows = conn.execute(
        "SELECT service_slug FROM crm_service_lifecycle WHERE customer_id = ? AND status = 'active'",
        (customer_id,),
    ).fetchall()
    active_lifecycles = [r["service_slug"] for r in active_rows]

    consult: dict[str, Any] | None = None
    resolved_lifecycle_id = _resolve_lifecycle_for_consult(
        conn, int(customer_id), lifecycle_id
    )
    if resolved_lifecycle_id:
        consult = _load_consult_task_context(conn, resolved_lifecycle_id)

    return {
        "customer": customer,
        "lead": lead,
        "contracts": contracts,
        "past_service_slugs": past_service_slugs,
        "active_lifecycles": active_lifecycles,
        "consult": consult,
        "lifecycle_id": resolved_lifecycle_id,
    }


def run_proposal_ai(conn: sqlite3.Connection, proposal_id: int) -> dict:
    try:
        import anthropic
        proposal = get_proposal(conn, proposal_id)
        if proposal is None:
            return {}
        ctx = get_customer_context(
            conn,
            proposal["customer_id"],
            lifecycle_id=proposal.get("lifecycle_id"),
        )

        service_names_str = ", ".join(
            SERVICE_NAMES.get(s, s) for s in proposal["service_slugs"]
        ) or "Chưa chọn dịch vụ"
        past_services_str = ", ".join(
            SERVICE_NAMES.get(s, s) for s in ctx["past_service_slugs"]
        ) or "Chưa có"
        lead = ctx["lead"] or {}
        product_interest = lead.get("product_interest") or "Không rõ"
        need = lead.get("need") or "Không rõ"

        consult_block = ""
        consult = ctx.get("consult")
        if consult and (
            consult.get("form_data")
            or consult.get("ai_output")
            or consult.get("notes")
        ):
            form_json = json.dumps(
                consult.get("form_data") or {},
                ensure_ascii=False,
            )[:3500]
            consult_block = (
                "\nKết quả audit Consult (bắt buộc tham chiếu khi viết đề xuất):\n"
                f"- Task: {consult.get('title') or 'Consult'}\n"
                f"- Form audit (JSON): {form_json}\n"
                f"- Ghi chú AM Consult: {consult.get('notes') or '—'}\n"
                f"- AI phân tích Consult:\n{consult.get('ai_output') or '—'}\n"
            )
            if consult.get("intake_summary"):
                consult_block += (
                    f"- Tóm tắt Lead Intake (BANT {consult.get('bant_total', 0)}/30, "
                    f"decision={consult.get('decision') or '—'}):\n"
                    f"{consult['intake_summary'][:2000]}\n"
                )

        prompt = (
            f"Bạn là chuyên gia tư vấn marketing digital, viết đề xuất dịch vụ cho khách hàng doanh nghiệp.\n\n"
            f"Thông tin khách hàng:\n"
            f"- Tên: {ctx['customer']['name']}\n"
            f"- Công ty: {ctx['customer']['company'] or 'Cá nhân'}\n"
            f"- Ngành/Nhu cầu: {product_interest} — {need}\n"
            f"- Lịch sử: {ctx['contracts']['count']} hợp đồng trước "
            f"(tổng {ctx['contracts']['total_vnd']:,} VNĐ), đã dùng: {past_services_str}\n\n"
            f"Dịch vụ đề xuất lần này: {service_names_str}\n"
            f"Tổng giá trị: {proposal['total_vnd']:,} VNĐ / {proposal['timeline_months']} tháng\n"
            f"Ghi chú từ chuyên viên: {proposal['notes'] or 'Không có'}\n"
            f"{consult_block}\n"
            f"Viết đề xuất theo đúng 5 header ## sau (không thêm header khác):\n\n"
            f"## Phân tích vấn đề\n"
            f"[Pain points của khách dựa trên ngành/nhu cầu. 3-5 câu.]\n\n"
            f"## Giải pháp đề xuất\n"
            f"[Cách các dịch vụ được chọn giải quyết vấn đề. Đề cập tên từng dịch vụ. 4-6 câu.]\n\n"
            f"## Tại sao chọn PTTCOM\n"
            f"[USP tailored theo context khách: kinh nghiệm, kết quả, sự phù hợp. 3-4 câu.]\n\n"
            f"## Kết quả kỳ vọng\n"
            f"[KPIs cụ thể theo từng dịch vụ được chọn. Format danh sách bullet. 4-6 items.]\n\n"
            f"## Tóm tắt báo giá\n"
            f"[Diễn giải mức giá thành văn thuyết phục: tại sao mức giá này xứng đáng. 2-3 câu.]"
        )

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        output = resp.content[0].text.strip()

        sections = {
            "problem": _extract_section(output, "Phân tích vấn đề"),
            "solution": _extract_section(output, "Giải pháp đề xuất"),
            "usp": _extract_section(output, "Tại sao chọn PTTCOM"),
            "kpi": _extract_section(output, "Kết quả kỳ vọng"),
            "pricing_narrative": _extract_section(output, "Tóm tắt báo giá"),
        }

        ts = _ts()
        conn.execute(
            "UPDATE crm_proposals SET ai_output = ?, updated_at = ? WHERE id = ?",
            (json.dumps(sections), ts, proposal_id),
        )
        conn.commit()
        return sections
    except Exception:
        return {}
