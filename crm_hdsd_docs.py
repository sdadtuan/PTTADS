"""HDSD — danh mục tài liệu Markdown trong docs/ (phục vụ /crm/hdsd)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DOCS_ROOT = BASE_DIR / "docs"

HDSD_SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "crm",
        "label": "CRM — Quy trình & vận hành",
        "description": "Lead → Retain, nguồn lead, checklist pilot.",
        "path": DOCS_ROOT / "crm",
    },
    {
        "key": "runbooks",
        "label": "Runbook — Consult & triển khai",
        "description": "SOP AM, training, task 12 dịch vụ, BANT sign-off.",
        "path": DOCS_ROOT / "runbooks",
    },
)

_DOC_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _slug_from_filename(name: str) -> str:
    base = Path(name).stem
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", base).strip("-").lower() or "doc"


def _title_from_markdown(text: str, fallback: str) -> str:
    m = _DOC_TITLE_RE.search(text)
    if m:
        return m.group(1).strip()[:200]
    return fallback.replace("-", " ").replace("_", " ").title()[:200]


def _scan_section(section: dict[str, Any]) -> list[dict[str, Any]]:
    root: Path = section["path"]
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.md")):
        if not path.is_file():
            continue
        slug = _slug_from_filename(path.name)
        try:
            preview = path.read_text(encoding="utf-8")[:4000]
        except OSError:
            preview = ""
        title = _title_from_markdown(preview, slug)
        items.append(
            {
                "section": section["key"],
                "slug": slug,
                "filename": path.name,
                "title": title,
                "size_bytes": path.stat().st_size,
            }
        )
    return items


def list_hdsd_catalog() -> list[dict[str, Any]]:
    """Trả danh mục theo section — mỗi doc có section, slug, title, filename."""
    out: list[dict[str, Any]] = []
    for sec in HDSD_SECTIONS:
        docs = _scan_section(sec)
        out.append(
            {
                "key": sec["key"],
                "label": sec["label"],
                "description": sec.get("description", ""),
                "docs": docs,
            }
        )
    return out


def resolve_hdsd_doc(section_key: str, slug: str) -> tuple[Path, dict[str, Any]] | None:
    """Tìm file .md an toàn — không cho path traversal."""
    key = str(section_key or "").strip().lower()
    slug_clean = str(slug or "").strip().lower()
    if not key or not slug_clean or ".." in slug_clean or "/" in slug_clean:
        return None
    sec = next((s for s in HDSD_SECTIONS if s["key"] == key), None)
    if sec is None:
        return None
    root: Path = sec["path"]
    if not root.is_dir():
        return None
    for path in root.glob("*.md"):
        if _slug_from_filename(path.name) == slug_clean:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                return None
            meta = {
                "section": key,
                "slug": slug_clean,
                "filename": path.name,
                "title": _title_from_markdown(text, slug_clean),
                "section_label": sec["label"],
            }
            return path, meta
    return None


def read_hdsd_doc(section_key: str, slug: str) -> tuple[str, dict[str, Any]] | None:
    resolved = resolve_hdsd_doc(section_key, slug)
    if resolved is None:
        return None
    path, meta = resolved
    try:
        return path.read_text(encoding="utf-8"), meta
    except OSError:
        return None
