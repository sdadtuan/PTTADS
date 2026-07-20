"""AEO Anthropic scan + content generation (no DB I/O)."""
from __future__ import annotations

import re
from typing import Any


def extract_section(text: str, header: str) -> str:
    pattern = rf"## {re.escape(header)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def run_aeo_scan_prompt(query_text: str, brand_name: str, notes: str = "") -> dict[str, Any]:
    """Call Anthropic to simulate AI-engine response; returns parsed scan fields."""
    import anthropic

    brand_notes = notes or "Không có thêm thông tin"
    prompt = f"""Bạn là chuyên gia AEO phân tích cách AI engine trả lời câu hỏi.

Query: "{query_text}"
Brand cần monitor: "{brand_name}"
Thông tin brand: "{brand_notes}"

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
    visibility_section = extract_section(output, "Phân tích Brand Visibility")
    brand_visible = bool(
        re.search(r"brand_visible\s*:\s*yes", visibility_section, re.IGNORECASE)
    )
    gap_notes = extract_section(output, "Content Gap")
    return {
        "ai_response": output,
        "brand_visible": brand_visible,
        "gap_notes": gap_notes,
    }


def run_aeo_content_prompt(query_text: str, brand_name: str, gap_notes: str) -> dict[str, str]:
    """Generate Q&A pairs + FAQ schema JSON-LD via Anthropic."""
    import anthropic

    gap = gap_notes or "Không có phân tích gap"
    prompt = f"""Bạn là chuyên gia viết content AEO.

Query: "{query_text}"
Brand: "{brand_name}"
Content gap cần fill: "{gap}"

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
    return {
        "qa_text": extract_section(output, "Q&A Pairs"),
        "schema_json": extract_section(output, "FAQ Schema JSON-LD"),
    }


def stub_scan_result(query_text: str) -> dict[str, Any]:
    output = (
        f"## Câu trả lời AI điển hình\nStub response for {query_text}\n\n"
        f"## Phân tích Brand Visibility\nbrand_visible: yes\n\n"
        f"## Content Gap\nStub gap notes."
    )
    return {
        "ai_response": output,
        "brand_visible": True,
        "gap_notes": "Stub gap",
    }
