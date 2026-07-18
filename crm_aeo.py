# crm_aeo.py
from __future__ import annotations
import re
import sqlite3
from datetime import datetime


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS crm_aeo_queries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id  INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            lifecycle_id INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE SET NULL,
            query_text   TEXT NOT NULL DEFAULT '',
            brand_name   TEXT NOT NULL DEFAULT '',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_queries_customer ON crm_aeo_queries (customer_id);

        CREATE TABLE IF NOT EXISTS crm_aeo_scans (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id      INTEGER NOT NULL REFERENCES crm_aeo_queries(id) ON DELETE CASCADE,
            ai_response   TEXT NOT NULL DEFAULT '',
            brand_visible INTEGER NOT NULL DEFAULT 0,
            gap_notes     TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_scans_query ON crm_aeo_scans (query_id);

        CREATE TABLE IF NOT EXISTS crm_aeo_content (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id    INTEGER NOT NULL REFERENCES crm_aeo_queries(id) ON DELETE CASCADE,
            qa_text     TEXT NOT NULL DEFAULT '',
            schema_json TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_content_query ON crm_aeo_content (query_id);
    """)


def add_query(
    conn: sqlite3.Connection,
    customer_id: int,
    query_text: str,
    brand_name: str,
    *,
    lifecycle_id: int | None = None,
    notes: str = "",
) -> int:
    cur = conn.execute(
        "INSERT INTO crm_aeo_queries (customer_id, lifecycle_id, query_text, brand_name, notes, created_at) VALUES (?,?,?,?,?,?)",
        (customer_id, lifecycle_id, query_text, brand_name, notes, _ts()),
    )
    conn.commit()
    return cur.lastrowid


def list_queries(conn: sqlite3.Connection, customer_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT q.id, q.query_text, q.brand_name, q.notes, q.lifecycle_id, q.created_at,
               s.created_at AS last_scan_date,
               s.brand_visible
        FROM crm_aeo_queries q
        LEFT JOIN crm_aeo_scans s ON s.id = (
            SELECT id FROM crm_aeo_scans WHERE query_id = q.id ORDER BY id DESC LIMIT 1
        )
        WHERE q.customer_id = ?
        ORDER BY q.id
        """,
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_query(conn: sqlite3.Connection, query_id: int) -> None:
    conn.execute("DELETE FROM crm_aeo_queries WHERE id = ?", (query_id,))
    conn.commit()


def _extract_section(text: str, header: str) -> str:
    pattern = rf"## {re.escape(header)}\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def run_scan(conn: sqlite3.Connection, query_id: int) -> str:
    try:
        import anthropic
        row = conn.execute(
            "SELECT query_text, brand_name, notes FROM crm_aeo_queries WHERE id = ?",
            (query_id,),
        ).fetchone()
        if row is None:
            return ""
        query_text = row["query_text"]
        brand_name = row["brand_name"]
        notes = row["notes"] or "Không có thêm thông tin"

        prompt = f"""Bạn là chuyên gia AEO phân tích cách AI engine trả lời câu hỏi.

Query: "{query_text}"
Brand cần monitor: "{brand_name}"
Thông tin brand: "{notes}"

Hãy thực hiện 3 bước sau, dùng đúng header ##:

## Câu trả lời AI điển hình
[Viết câu trả lời mà ChatGPT hoặc Perplexity thường trả lời cho query này, dựa trên kiến thức phổ biến. 3-5 câu.]

## Phân tích Brand Visibility
brand_visible: [yes/no]
[Giải thích: {brand_name} có xuất hiện trong câu trả lời trên không, và tại sao. 2-3 câu.]

## Content Gap
[Liệt kê 2-3 loại nội dung/tín hiệu mà {brand_name} đang thiếu để AI engine đề cập đến khi trả lời query này.]"""

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        output = resp.content[0].text.strip()

        visibility_section = _extract_section(output, "Phân tích Brand Visibility")
        brand_visible = 1 if re.search(r"brand_visible\s*:\s*yes", visibility_section, re.IGNORECASE) else 0
        gap_notes = _extract_section(output, "Content Gap")

        conn.execute(
            "INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)",
            (query_id, output, brand_visible, gap_notes, _ts()),
        )
        conn.commit()
        return output
    except Exception:
        return ""


def get_scan_history(conn: sqlite3.Connection, query_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, ai_response, brand_visible, gap_notes, created_at FROM crm_aeo_scans WHERE query_id = ? ORDER BY id DESC",
        (query_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def generate_content(conn: sqlite3.Connection, query_id: int) -> dict:
    try:
        import anthropic
        q_row = conn.execute(
            "SELECT query_text, brand_name FROM crm_aeo_queries WHERE id = ?",
            (query_id,),
        ).fetchone()
        if q_row is None:
            return {}
        query_text = q_row["query_text"]
        brand_name = q_row["brand_name"]

        scan = conn.execute(
            "SELECT gap_notes FROM crm_aeo_scans WHERE query_id = ? ORDER BY id DESC LIMIT 1",
            (query_id,),
        ).fetchone()
        gap_notes = scan["gap_notes"] if scan else "Không có phân tích gap"

        prompt = f"""Bạn là chuyên gia viết content AEO.

Query: "{query_text}"
Brand: "{brand_name}"
Content gap cần fill: "{gap_notes}"

Hãy tạo:

## Q&A Pairs
[3-5 cặp câu hỏi – câu trả lời, mỗi cặp giúp {brand_name} xuất hiện khi AI engine trả lời câu hỏi liên quan. Format:
Q: [câu hỏi]
A: [câu trả lời 2-3 câu, tự nhiên, có đề cập {brand_name}]]

## FAQ Schema JSON-LD
[JSON-LD hợp lệ dùng schema.org/FAQPage, bao gồm tất cả Q&A pairs ở trên. Chỉ trả về JSON thuần, không thêm markdown code block.]"""

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        output = resp.content[0].text.strip()

        qa_text = _extract_section(output, "Q&A Pairs")
        schema_json = _extract_section(output, "FAQ Schema JSON-LD")

        ts = _ts()
        conn.execute(
            "INSERT INTO crm_aeo_content (query_id, qa_text, schema_json, created_at) VALUES (?,?,?,?)",
            (query_id, qa_text, schema_json, ts),
        )
        conn.commit()
        return {"qa_text": qa_text, "schema_json": schema_json, "created_at": ts}
    except Exception:
        return {}


def get_latest_content(conn: sqlite3.Connection, query_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, qa_text, schema_json, created_at FROM crm_aeo_content WHERE query_id = ? ORDER BY id DESC LIMIT 1",
        (query_id,),
    ).fetchone()
    return dict(row) if row else None
