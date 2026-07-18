# crm_customer_brief.py
from __future__ import annotations
import sqlite3
from datetime import datetime


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS crm_customer_brief_scans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            meeting_purpose TEXT NOT NULL DEFAULT '',
            ai_output       TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_brief_scans_customer
            ON crm_customer_brief_scans (customer_id);
    """)


def get_customer_snapshot(conn: sqlite3.Connection, customer_id: int) -> dict:
    customer = conn.execute(
        "SELECT id, name, company, occupation, lead_source, created_at FROM crm_customers WHERE id = ?",
        (customer_id,),
    ).fetchone()
    if customer is None:
        return {"customer": {}, "contracts": [], "total_contract_vnd": 0, "active_lifecycles": [], "open_issues": 0}

    now = datetime.utcnow()
    try:
        created = datetime.strptime(customer["created_at"][:10], "%Y-%m-%d")
        months = (now.year - created.year) * 12 + (now.month - created.month)
    except Exception:
        months = 0

    contracts = [
        dict(r) for r in conn.execute(
            "SELECT id, amount_vnd, status FROM crm_contracts WHERE customer_id = ?",
            (customer_id,),
        ).fetchall()
    ]
    total_contract_vnd = sum(c["amount_vnd"] for c in contracts)

    # Try to fetch contract_id column; fall back gracefully if column doesn't exist
    try:
        lifecycles = conn.execute(
            """SELECT id, service_slug, stage, assigned_am, assigned_sp, contract_id
               FROM crm_service_lifecycle
               WHERE customer_id = ? AND status = 'active'""",
            (customer_id,),
        ).fetchall()
    except Exception:
        lifecycles = conn.execute(
            """SELECT id, service_slug, stage, assigned_am, assigned_sp
               FROM crm_service_lifecycle
               WHERE customer_id = ? AND status = 'active'""",
            (customer_id,),
        ).fetchall()

    try:
        from crm_svc_tasks import SERVICE_LABELS as _svc_labels
    except Exception:
        _svc_labels = {}

    active_lifecycles = []
    for lc in lifecycles:
        lc_id = lc["id"]

        received = conn.execute(
            "SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_payments WHERE lifecycle_id = ? AND status = 'received'",
            (lc_id,),
        ).fetchone()[0]
        expenses = conn.execute(
            "SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses WHERE lifecycle_id = ?",
            (lc_id,),
        ).fetchone()[0]
        margin_pct = ((received - expenses) / received * 100.0) if received > 0 else 0.0

        # contract_id may not exist in schema (graceful fallback)
        contract_id = None
        try:
            contract_id = lc["contract_id"]
        except (IndexError, KeyError):
            pass

        contract_amount = 0
        if contract_id:
            row = conn.execute("SELECT amount_vnd FROM crm_contracts WHERE id = ?", (contract_id,)).fetchone()
            if row:
                contract_amount = row["amount_vnd"]
        outstanding = max(0, contract_amount - received)

        last_payment = conn.execute(
            "SELECT received_on FROM crm_svc_payments WHERE lifecycle_id = ? AND status = 'received' ORDER BY id DESC LIMIT 1",
            (lc_id,),
        ).fetchone()

        active_risks = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_risks WHERE lifecycle_id = ? AND is_active = 1",
            (lc_id,),
        ).fetchone()[0]
        pending_tasks = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = ? AND is_done = 0",
            (lc_id,),
        ).fetchone()[0]

        am_name = ""
        sp_name = ""
        if lc["assigned_am"]:
            row = conn.execute("SELECT name FROM crm_staff WHERE id = ?", (lc["assigned_am"],)).fetchone()
            if row:
                am_name = row["name"]
        if lc["assigned_sp"]:
            row = conn.execute("SELECT name FROM crm_staff WHERE id = ?", (lc["assigned_sp"],)).fetchone()
            if row:
                sp_name = row["name"]

        active_lifecycles.append({
            "id": lc_id,
            "service_slug": lc["service_slug"],
            "service_label": _svc_labels.get(lc["service_slug"], lc["service_slug"]),
            "stage": lc["stage"],
            "am_name": am_name,
            "sp_name": sp_name,
            "margin_pct": round(margin_pct, 1),
            "outstanding": outstanding,
            "last_payment_date": last_payment["received_on"] if last_payment else "",
            "active_risks": active_risks,
            "pending_tasks": pending_tasks,
        })

    open_issues = 0
    try:
        from crm_customer_360 import fetch_customer_issues
        issues = fetch_customer_issues(conn, customer_id)
        open_statuses = {"moi", "dang_xu_ly", "cho_khach", "cho_xu_ly"}
        open_issues = sum(1 for i in issues if i.get("status") in open_statuses)
    except Exception:
        pass

    return {
        "customer": {
            "id": customer["id"],
            "name": customer["name"],
            "company": customer["company"],
            "occupation": customer["occupation"],
            "lead_source": customer["lead_source"],
            "created_at": customer["created_at"],
            "months_as_customer": months,
        },
        "contracts": contracts,
        "total_contract_vnd": total_contract_vnd,
        "active_lifecycles": active_lifecycles,
        "open_issues": open_issues,
    }


def run_brief_ai(
    conn: sqlite3.Connection,
    customer_id: int,
    meeting_purpose: str,
    snapshot: dict,
) -> str:
    try:
        import anthropic
        c = snapshot["customer"]
        purpose_str = meeting_purpose.strip() or "Không xác định — tạo brief tổng quát"
        lc_lines = ""
        for lc in snapshot.get("active_lifecycles", []):
            lc_lines += (
                f"- {lc['service_label']}: stage={lc['stage']}, "
                f"margin={lc['margin_pct']:.1f}%, công nợ={lc['outstanding']:,} VND, "
                f"AM={lc['am_name'] or 'chưa phân công'}, SP={lc['sp_name'] or 'chưa phân công'}, "
                f"risks active={lc['active_risks']}, tasks chưa xong={lc['pending_tasks']}\n"
            )
        if not lc_lines:
            lc_lines = "  (không có dịch vụ đang triển khai)\n"

        prompt = f"""Bạn là chuyên gia tư vấn chiến lược khách hàng B2B.

Mục đích cuộc họp: {purpose_str}

=== DATA KHÁCH HÀNG ===
Tên: {c['name']} | Công ty: {c['company']} | Vị trí: {c['occupation']} | Gắn bó: {c['months_as_customer']} tháng
Tổng giá trị hợp đồng: {snapshot['total_contract_vnd']:,} VND

Dịch vụ đang triển khai:
{lc_lines}
Issues/khiếu nại đang mở: {snapshot['open_issues']}

=== YÊU CẦU ===
Tạo Meeting Brief ngắn gọn với đúng 3 phần sau (dùng header ##):

## Tóm tắt khách hàng
[3-4 dòng: profile, thời gian gắn bó, dịch vụ đang dùng, tổng giá trị]

## Điểm cần chú ý
[Tối đa 3 bullet, mỗi bullet 1 vấn đề nổi bật nhất dựa trên data: margin thấp, risk active, task trễ, công nợ cao, khiếu nại mở]

## Câu hỏi gợi ý
[3-4 câu AM nên hỏi khách trong buổi họp này, phù hợp với mục đích và tình trạng thực tế]"""

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        output = resp.content[0].text.strip()
        ts = _ts()
        conn.execute(
            "INSERT INTO crm_customer_brief_scans (customer_id, meeting_purpose, ai_output, created_at) VALUES (?,?,?,?)",
            (customer_id, meeting_purpose, output, ts),
        )
        conn.commit()
        return output
    except Exception:
        return ""


def get_latest_brief(conn: sqlite3.Connection, customer_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, meeting_purpose, ai_output, created_at FROM crm_customer_brief_scans WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
        (customer_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)
