"""AI-assisted content brief generation (Flow F1 — Gate B)."""
from __future__ import annotations

import json
import os
import re
from typing import Any


def ai_brief_available() -> bool:
    return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())


def generate_brief_ai(*, primary: str, intent: str = "", audience: str = "") -> dict[str, Any]:
    """Call Anthropic for a structured brief; raises if API unavailable."""
    import anthropic

    primary = primary.strip()
    if not primary:
        raise ValueError("Thiếu primary topic")
    intent = intent.strip() or "informational"
    audience = audience.strip() or "Người tìm kiếm có intent liên quan"
    prompt = f"""Bạn là SEO/AEO strategist. Tạo content brief JSON cho topic sau.

Topic: "{primary}"
Intent: {intent}
Audience: {audience}

Trả về JSON thuần (không markdown) với keys:
- primary_topic (string)
- objective (string, 1 câu)
- target_audience (string)
- sections (array of strings, 5-7 mục outline)
- checklist (array of strings, 5-8 mục QA)
- meta_title (string, ≤60 ký tự)
- meta_description (string, ≤160 ký tự)
- suggested_content_type (string: blog|pillar|faq|howto|service)"""

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("AI không trả về JSON brief")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Brief JSON không hợp lệ")
    data["brief_source"] = "ai"
    return data
