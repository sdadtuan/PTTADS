"""AI Qualify Brief — tự động sinh tóm tắt ngách + câu hỏi qualify khi lead mới vào CRM.

Dùng Claude Haiku (nhanh, rẻ ~$0.001/lead). Non-blocking: chạy background thread.
Kết quả lưu vào meta_json["ai_qualify_brief"], hiện trong lead detail.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"

# Bản đồ ngách → gợi ý tài liệu gửi khách
_NICHE_MATERIALS: dict[str, list[str]] = {
    "shophouse_sme": [
        "Case study F&B / salon đang kinh doanh thành công tại shophouse dự án",
        "So sánh chi phí thuê 10 năm vs sở hữu shophouse",
        "Bảng giá shophouse + chính sách cho thuê lại",
    ],
    "doi_nha": [
        "So sánh giá/m² Hóc Môn vs Q12 / Bình Dương hiện tại",
        "Quy trình đổi nhà: bán nhà cũ → đặt cọc liền kề (kết nối đối tác thu mua)",
        "Video tour thực tế liền kề đã hoàn thiện",
    ],
    "da_the_he": [
        "Sơ đồ mặt bằng cụm liền kề 2-3 căn liền nhau",
        "Case study gia đình 3 thế hệ sống tại dự án",
        "Chính sách đặt cọc ưu tiên cụm (book trước khi ra mắt chính thức)",
    ],
    "viet_kieu": [
        "Hướng dẫn người Việt hải ngoại mua BĐS tại Việt Nam (pháp lý, ủy quyền)",
        "Video 360° dự án + bản đồ hạ tầng khu vực",
        "Gói dịch vụ quản lý tài sản cho khách không ở tại chỗ",
    ],
    "legacy": [
        "Phân tích tăng giá BĐS khu Hóc Môn 5-10 năm (data RSES)",
        "Biệt thự: thiết kế + vật liệu + đẳng cấp",
        "Chính sách thanh toán dài hạn, hỗ trợ vay",
    ],
    "doanh_nhan": [
        "Biệt thự: không gian làm việc tại gia, đại sảnh tiếp khách",
        "So sánh ROI mua BĐS vs gửi ngân hàng trong 10 năm",
        "Chính sách VIP: tư vấn 1-1, đặt cọc ưu tiên",
    ],
}

_SYSTEM_PROMPT = """Bạn là chuyên gia qualify lead BĐS cao cấp tại Việt Nam.
Nhiệm vụ: phân tích thông tin lead và trả về JSON với cấu trúc chính xác.
Chỉ trả về JSON hợp lệ, không giải thích thêm."""

_USER_TEMPLATE = """Phân tích lead BĐS sau và trả về JSON:

Tên: {full_name}
Sản phẩm quan tâm: {product_interest}
Nguồn: {source}
Ghi chú / nhu cầu: {need}
Ngân sách (VND): {budget}
Dự án: {project_name}

Trả về JSON với cấu trúc:
{{
  "niche": "<một trong: shophouse_sme | doi_nha | da_the_he | viet_kieu | legacy | doanh_nhan | dau_tu | khac>",
  "niche_label": "<tên ngách dễ đọc>",
  "niche_confidence": <0.0-1.0>,
  "summary": "<1 câu tóm tắt ngắn gọn về khách>",
  "qualify_questions": [
    "<câu hỏi qualify 1 phù hợp ngách>",
    "<câu hỏi qualify 2>",
    "<câu hỏi qualify 3>",
    "<câu hỏi qualify 4>",
    "<câu hỏi qualify 5>"
  ],
  "key_risks": [
    "<rủi ro / lo ngại chính 1 của khách ngách này>",
    "<rủi ro 2>"
  ],
  "opening_line": "<câu mở đầu cuộc gọi đầu tiên, tự nhiên, không sáo rỗng>"
}}"""


def _get_client():
    """Lấy Anthropic client, trả về None nếu chưa cấu hình API key."""
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except Exception as exc:
        logger.warning("Không khởi tạo được Anthropic client: %s", exc)
        return None


def generate_qualify_brief(
    *,
    full_name: str,
    product_interest: str,
    source: str,
    need: str,
    budget_vnd: int | None = None,
    project_name: str = "",
) -> dict[str, Any] | None:
    """Gọi Claude API, trả về qualify brief dict. Trả về None nếu lỗi."""
    client = _get_client()
    if client is None:
        logger.debug("AI qualify bị bỏ qua: chưa có ANTHROPIC_API_KEY")
        return None

    budget_str = f"{budget_vnd:,} VND" if budget_vnd else "chưa khai báo"
    prompt = _USER_TEMPLATE.format(
        full_name=full_name or "Chưa có tên",
        product_interest=product_interest or "chưa rõ",
        source=source or "chưa rõ",
        need=(need or "").strip()[:1000] or "chưa có ghi chú",
        budget=budget_str,
        project_name=project_name or "chưa rõ",
    )

    try:
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=800,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Xử lý trường hợp Claude bọc trong ```json ... ```
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        brief = json.loads(raw)
        # Thêm tài liệu gợi ý dựa trên ngách
        niche = str(brief.get("niche") or "khac")
        brief["recommended_materials"] = _NICHE_MATERIALS.get(niche, [])
        brief["generated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        brief["model"] = _HAIKU
        return brief
    except json.JSONDecodeError as exc:
        logger.warning("AI qualify: JSON parse lỗi — %s | raw=%s", exc, raw[:200])
        return None
    except Exception as exc:
        logger.warning("AI qualify API lỗi: %s", exc)
        return None


def save_qualify_brief(
    conn: sqlite3.Connection,
    lead_id: int,
    brief: dict[str, Any],
    ts: str,
) -> None:
    """Ghi brief vào meta_json["ai_qualify_brief"] của lead."""
    row = conn.execute(
        "SELECT meta_json FROM crm_leads WHERE id = ?", (lead_id,)
    ).fetchone()
    if row is None:
        return
    try:
        meta = json.loads(row["meta_json"] or "{}") if isinstance(row["meta_json"], str) else {}
    except json.JSONDecodeError:
        meta = {}
    meta["ai_qualify_brief"] = brief
    conn.execute(
        "UPDATE crm_leads SET meta_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(meta, ensure_ascii=False), ts, lead_id),
    )
    conn.commit()


def trigger_qualify_brief_async(
    lead_id: int,
    *,
    full_name: str,
    product_interest: str,
    source: str,
    need: str,
    budget_vnd: int | None = None,
    project_name: str = "",
    db_path: str,
) -> None:
    """Chạy generate + save trong background thread — không block request."""

    def _run() -> None:
        brief = generate_qualify_brief(
            full_name=full_name,
            product_interest=product_interest,
            source=source,
            need=need,
            budget_vnd=budget_vnd,
            project_name=project_name,
        )
        if brief is None:
            return
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            save_qualify_brief(conn, lead_id, brief, ts)
            logger.info("AI qualify brief saved: lead_id=%s niche=%s", lead_id, brief.get("niche"))
            # Wire: tạo draft lifecycle từ AI qualify
            try:
                from crm_service_lifecycle import (
                    _suggest_service_slug,
                    create_draft_lifecycle,
                    get_by_lead,
                )
                if get_by_lead(conn, lead_id) is None:
                    slug = _suggest_service_slug(
                        niche=str(brief.get("niche") or ""),
                        pain_points=str(brief.get("pain_points") or ""),
                        lead_message=str(brief.get("need") or ""),
                    )
                    create_draft_lifecycle(conn, lead_id=lead_id, service_slug=slug)
                    logger.info("Draft lifecycle created: lead_id=%s slug=%s", lead_id, slug)
            except Exception as _lc_exc:
                logger.warning("Lifecycle draft tạo lỗi: %s", _lc_exc)
            conn.close()
        except Exception as exc:
            logger.warning("AI qualify save lỗi: %s", exc)

    t = threading.Thread(target=_run, daemon=True, name=f"ai-qualify-{lead_id}")
    t.start()
