#!/usr/bin/env python3
"""Generate markdown appendix: Consult task per 12 dịch vụ (from CRM templates)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crm_svc_tasks import SERVICE_LABELS
from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS

OUTPUT = ROOT / "docs" / "runbooks" / "consult-stage-service-tasks.md"

GROUPS = {
    "dich-vu-seo-tong-the": "Tìm kiếm tự nhiên",
    "dich-vu-aeo": "Tìm kiếm tự nhiên",
    "dich-vu-seo-local": "Tìm kiếm tự nhiên",
    "dich-vu-seo-audit": "Tìm kiếm tự nhiên",
    "dich-vu-quan-tri-website": "Thiết kế & web",
    "thiet-ke-website": "Thiết kế & web",
    "thiet-ke-website-tron-goi": "Thiết kế & web",
    "thiet-ke-landing-page": "Thiết kế & web",
    "quang-cao-facebook": "Quảng cáo",
    "quang-cao-google": "Quảng cáo",
    "thue-tai-khoan-quang-cao": "Quảng cáo",
    "tiep-thi-noi-dung": "Nội dung",
}


def build() -> str:
    lines = [
        "# Phụ lục: Task Consult theo 12 dịch vụ",
        "",
        "> **Auto-generated** từ `crm_svc_workflow_steps.py`. Không sửa tay — chạy lại:",
        "> `python3 scripts/generate_consult_runbook_appendix.py`",
        "",
        "---",
        "",
    ]
    idx = 0
    for slug in sorted(SERVICE_WORKFLOW_STEPS.keys()):
        steps = SERVICE_WORKFLOW_STEPS[slug].get("consult") or []
        if not steps:
            continue
        idx += 1
        step = steps[0]
        label = SERVICE_LABELS.get(slug, slug)
        group = GROUPS.get(slug, "Khác")
        lines.append(f"## {idx}. {label}")
        lines.append("")
        lines.append(f"- **Slug CRM:** `{slug}`")
        lines.append(f"- **Nhóm:** {group}")
        lines.append(f"- **Task:** {step.get('title', '')}")
        lines.append("")
        desc = str(step.get("description") or "").strip()
        if desc:
            lines.append(f"**Mô tả:** {desc}")
            lines.append("")
        lines.append("**Form CRM (bắt buộc điền trước khi tick ✓):**")
        lines.append("")
        lines.append("| Field key | Label | Loại |")
        lines.append("|-----------|-------|------|")
        for field in step.get("form_fields") or []:
            lines.append(
                f"| `{field.get('key', '')}` | {field.get('label', '')} | {field.get('type', 'text')} |"
            )
        lines.append("")
        lines.append("**AI:** prompt `consult_analysis` trên task card workflow.")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
